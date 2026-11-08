"""Isolated video-learning workspace. Does not restart the existing AppDNA app."""
import asyncio
import json
import os
import shutil
import subprocess
import uuid
from pathlib import Path
from urllib.parse import urlparse
from fastapi import FastAPI,File,Form,HTTPException,Query,Request,UploadFile
from fastapi.responses import FileResponse,JSONResponse
from pydantic import BaseModel
from app.config import get_settings
from app.engines.media import prepare_media
from app.agents.video_learning import learn_video_source
from app.engines.tutorial_expectations import build_expectations,source_state,local_media,validate_binding
from app.engines.tutorial_runner import execute_plan,youtube_url
from app.drivers.blender_tutorial import BlenderTutorialDriver,guard
from app.providers.gladia import GladiaProvider
from app.providers.hcompany import HCompanyProvider

ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'tasks/video-agent/evidence/jobs'
DATA.mkdir(parents=True,exist_ok=True)
app=FastAPI(title='AppDNA — Learn by watching',docs_url=None,redoc_url=None)
stops={}
active=None
running_tasks=set()

@app.middleware('http')
async def same_origin(request:Request,call_next):
    if request.method not in {'GET','HEAD'}:
        origin=request.headers.get('origin')
        if origin and urlparse(origin).netloc!=request.headers.get('host'):
            return JSONResponse({'detail':'Cross-origin control is not allowed'},status_code=403)
    return await call_next(request)


def folder(job_id):
    if not isinstance(job_id,str) or len(job_id)!=32 or any(c not in '0123456789abcdef' for c in job_id):raise HTTPException(404,'Tutorial not found')
    path=DATA/job_id
    if not path.is_dir():raise HTTPException(404,'Tutorial not found')
    return path


def read(job_id):return json.loads((folder(job_id)/'job.json').read_text())
def save(path,data):
    temp=path/'job.tmp';temp.write_text(json.dumps(data,indent=2));temp.replace(path/'job.json')


def providers():
    s=get_settings()
    return GladiaProvider(s.gladia_api_key,s.gladia_base_url),HCompanyProvider(s.hcompany_api_key,s.hcompany_base_url,os.environ.get('APPDNA_LEARNING_MODEL',s.hcompany_model))


def spawn(coro):
    task=asyncio.create_task(coro);running_tasks.add(task);task.add_done_callback(running_tasks.discard)


async def learn(job_id):
    path=folder(job_id);job=read(job_id)
    try:
        if job.get('youtube_url'):
            job['status']='fetching_video';save(path,job)
            def download():
                result=subprocess.run(['yt-dlp','--no-playlist','--no-warnings','--socket-timeout','15','--retries','1',
                    '--max-filesize','100M','-f','bv*[height<=720]+ba/b[height<=720]', '--merge-output-format','mp4',
                    '-o',str(path/'source.%(ext)s'),job['youtube_url']],capture_output=True,timeout=180)
                if result.returncode:raise ValueError('Could not obtain YouTube media. Upload an authorized local video instead.')
                files=[p for p in path.glob('source.*') if p.suffix in {'.mp4','.webm','.mkv','.mov'}]
                if len(files)!=1:raise ValueError('No single usable video was downloaded')
                return files[0]
            source=await asyncio.to_thread(download)
        else:source=path/job['source_file']
        job.update(status='separating_media',source_file=source.name);save(path,job)
        media=await asyncio.to_thread(prepare_media,source,path)
        job['status']='learning';save(path,job)
        asr,vision=providers()
        stops[job_id]=False
        result=await learn_video_source(media,path,asr,vision,source=source,objective=job['objective'],
            source_url=job.get('youtube_url'),should_stop=lambda:stops.get(job_id,False))
        job['status']='ready_for_review' if result['status']=='source_checked' else result['status']
        job['error']='' if result['status']=='source_checked' else result.get('reason','')
        if result.get('title'):job['title']=result['title']
        save(path,job)
    except Exception as exc:
        job.update(status='blocked',error=str(exc)[:400]);save(path,job)


@app.get('/')
def home():return FileResponse(ROOT/'tasks/video-agent/index.html')

@app.get('/api/tutorials')
def listing():
    return [json.loads(p.read_text()) for p in sorted(DATA.glob('*/job.json'),key=lambda p:p.stat().st_mtime,reverse=True)]

@app.get('/api/desktop')
async def desktop():return await asyncio.to_thread(guard,'lock')

@app.post('/api/tutorials')
async def create(url:str=Form(''),objective:str=Form('Reproduce the FIRST Bevel modifier workflow only; stop before the edit-mode alternative.'),video:UploadFile|None=File(None)):
    if bool(url.strip())==bool(video and video.filename):raise HTTPException(400,'Provide one YouTube link OR one video file')
    if not 1<=len(objective)<=1000:raise HTTPException(400,'Objective must be 1–1000 characters')
    try:canonical=youtube_url(url) if url.strip() else None
    except ValueError as exc:raise HTTPException(400,str(exc))
    if video and Path(video.filename or '').suffix.lower() not in {'.mp4','.mov','.webm','.mkv'}:raise HTTPException(400,'Upload MP4, MOV, WebM or MKV')
    job_id=uuid.uuid4().hex;path=DATA/job_id;path.mkdir()
    job={'id':job_id,'title':'Blender tutorial','objective':objective,'status':'queued','youtube_url':canonical}
    if video:
        source=path/('source'+Path(video.filename).suffix.lower());size=0
        with source.open('wb') as handle:
            while chunk:=await video.read(1024*1024):
                size+=len(chunk)
                if size>100*1024*1024:
                    shutil.rmtree(path);raise HTTPException(413,'Video exceeds 100 MB')
                handle.write(chunk)
        job['source_file']=source.name
    save(path,job);spawn(learn(job_id));return job

@app.get('/api/tutorials/{job_id}')
def detail(job_id:str):
    path=folder(job_id);job=read(job_id)
    for key,file in [('plan','plan.json'),('run','run/run.json'),('media','manifest.json'),('transcript','transcript.json'),('verification','run/verification.json'),('agent','agent.json'),('knowledge','knowledge.json'),('artifact_targets','artifact-expectations.json')]:
        if (path/file).exists():job[key]=json.loads((path/file).read_text())
    if 'media' in job:job['media'].pop('audio_path',None)
    return job

@app.get('/api/video-sources')
def video_sources(q:str=Query('',max_length=200),limit:int=Query(20,ge=1,le=100),offset:int=Query(0,ge=0)):
    """Parent-agent retrieval: only source-checked knowledge, never execution proof."""
    matches=[]
    for path in sorted(DATA.glob('*/knowledge.json'),key=lambda p:p.stat().st_mtime,reverse=True):
        job_file=path.parent/'job.json'
        if job_file.exists() and json.loads(job_file.read_text()).get('kind')=='video_source_execution':continue
        knowledge=json.loads(path.read_text())
        if knowledge.get('status')!='source_checked':continue
        text=' '.join(str(knowledge.get(k,'')) for k in ('title','objective','steps'))
        if q.casefold() not in text.casefold():continue
        matches.append({'id':path.parent.name,'title':knowledge.get('title'),'objective':knowledge.get('objective'),
            'source_type':'video','source_url':knowledge.get('source_url'),'status':'source_checked',
            'verification':knowledge.get('verification'),'knowledge_url':'/api/video-sources/'+path.parent.name})
    return {'items':matches[offset:offset+limit],'has_more':len(matches)>offset+limit}


@app.get('/api/video-sources/{job_id}')
def video_source(job_id:str):
    path=folder(job_id)/'knowledge.json'
    if not path.is_file():raise HTTPException(404,'Video source knowledge is not available')
    return FileResponse(path,media_type='application/json',filename='video-knowledge-'+job_id+'.json')


@app.post('/api/video-sources/{job_id}/executions')
def reuse_source(job_id:str):
    """Reuse accepted knowledge, never its run, artifact, approval or PID."""
    original=folder(job_id);source_job=read(job_id)
    if source_job.get('kind')=='video_source_execution':raise HTTPException(409,'Select the original video source to create a new run')
    try:
        knowledge,_=source_state(original)
        if not knowledge.get('evidence'):raise ValueError('Checked video evidence is missing')
        names={'knowledge.json','plan.json',knowledge['source_file']}
        for evidence in knowledge['evidence']:
            local_media(original,evidence['image'],{'.jpg','.png'});names.add(evidence['image'])
        manifest=json.loads((original/'manifest.json').read_text()) if (original/'manifest.json').exists() else {'frames':[]}
        available=[]
        for frame in manifest.get('frames',[]):
            if not (original/frame['image']).exists():continue
            local_media(original,frame['image'],{'.jpg','.png'});names.add(frame['image']);available.append(frame)
        manifest['frames']=available;manifest.pop('audio_path',None)
        for name in ['transcript.json','agent.json','artifact-expectations.json']:
            if (original/name).exists():names.add(name)
        for name in names:
            if Path(name).is_absolute() or '..' in Path(name).parts:raise ValueError('Source paths must remain relative to their own receipt')
            local_media(original,name,{'.json','.jpg','.png','.mp4','.mov','.webm','.mkv'})
        if 'artifact-expectations.json' in names:
            validate_binding(json.loads((original/'artifact-expectations.json').read_text()),original)
    except (ValueError,KeyError,TypeError,OSError) as exc:
        raise HTTPException(409,'Cannot reuse source: '+str(exc)[:250])
    new_id=uuid.uuid4().hex;path=DATA/new_id;path.mkdir()
    job={'id':new_id,'kind':'video_source_execution','source_job_id':job_id,'title':knowledge.get('title','Blender tutorial'),
        'objective':knowledge['objective'],'status':'ready_for_review','source_file':knowledge['source_file'],
        'youtube_url':knowledge.get('source_url'),'reuse_note':'Reused checked knowledge and media; no new download, transcription or learning.'}
    try:
        for name in sorted(names):
            target=path/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(original/name,target)
        (path/'manifest.json').write_text(json.dumps(manifest,indent=2))
        source_state(path)
    except (ValueError,OSError) as exc:
        job.update(status='blocked',error='Source copy failed');save(path,job)
        raise HTTPException(500,'Could not create an intact source copy') from exc
    save(path,job);return job


class Approval(BaseModel):
    confirm_scratch:bool=False
    reviewed:bool=False

@app.post('/api/tutorials/{job_id}/run')
async def run(job_id:str,approval:Approval):
    global active
    job=read(job_id);path=folder(job_id)
    if not approval.confirm_scratch or not approval.reviewed:raise HTTPException(400,'Review the steps and approve a new scratch Blender scene')
    if (path/'knowledge.json').exists() and json.loads((path/'knowledge.json').read_text()).get('status')!='source_checked':
        raise HTTPException(409,'Video source has unresolved learning issues; execution is blocked')
    if active:raise HTTPException(409,'Another Blender execution is active')
    if not (path/'plan.json').exists():raise HTTPException(409,'Learn the tutorial first')
    if await asyncio.to_thread(lambda:guard('lock')['locked']):raise HTTPException(409,'Mac is locked. Unlock the Mac before running Blender actions.')
    if (path/'run').exists():raise HTTPException(409,'This tutorial already has a run receipt; create a new run from the checked source')
    # The desktop check yielded to other requests; claim only after rechecking.
    if active:raise HTTPException(409,'Another Blender execution is active')
    active=job_id;stops[job_id]=False
    job['status']='starting_blender';save(path,job)
    spawn(execute(job_id));return {'status':'starting_blender'}

async def execute(job_id):
    global active
    path=folder(job_id);job=read(job_id)
    try:
        _,vision=providers()
        expectations=None
        if (path/'knowledge.json').exists():
            job['status']='checking_artifact_targets';save(path,job)
            expectations=await build_expectations(path,vision)
        if stops.get(job_id,True):
            job['status']='stopped';save(path,job);return
        driver=await asyncio.to_thread(BlenderTutorialDriver.launch,path/'run')
        (path/'run/pid.json').write_text(json.dumps({'pid':driver.pid}))
        job['status']='running';save(path,job)
        _,vision=providers()
        vision.model=os.environ.get('APPDNA_ACTION_MODEL',vision.model)
        job['action_model']=vision.model;save(path,job)
        result=await execute_plan(json.loads((path/'plan.json').read_text()),path/'run',driver,vision,lambda:stops.get(job_id,True))
        job['status']=result['status'];job['error']=result.get('reason','');save(path,job)
        if result['status']=='observed_complete' and not stops.get(job_id,True):
            from app.engines.tutorial_artifact import save_and_verify
            job['status']='saving_artifact';save(path,job)
            verification=await save_and_verify(path/'run',driver,vision,lambda:stops.get(job_id,True),expectations=expectations,source_folder=path)
            bound=bool(expectations and verification.get('scope')=='blender_bevel_v1'
                and verification.get('target_binding_sha256')==expectations['binding_sha256']
                and verification.get('source_sha256')==expectations['source_sha256']
                and verification.get('artifact') and verification.get('read_only_hash_unchanged') is True
                and len(verification.get('sha256',''))==64)
            if (path/'knowledge.json').exists() and not bound and verification.get('artifact'):
                # Legacy or unbound checks cannot verify this learned goal.
                verification={
                    'verification':'not_assessed','artifact':verification['artifact'],
                    'reason':'Saved artifact; verification is not bound to the pre-execution source targets.',
                    'reference_check':verification,
                }
            if (path/'knowledge.json').exists() and not bound and not verification.get('artifact'):
                verification={'verification':'failed','reason':'No saved source-bound artifact proof','reference_check':verification}
            (path/'run/verification.json').write_text(json.dumps(verification,indent=2))
            job['status']=('saved_unverified' if verification['verification']=='not_assessed' else
                           'verified' if verification['verification']=='verified' else 'artifact_failed')
            if bound:job['verification_scope']=verification['scope']
            save(path,job)
    except Exception as exc:
        job.update(status='blocked',error=str(exc)[:400]);save(path,job)
    finally:active=None

@app.post('/api/tutorials/{job_id}/stop')
def stop(job_id:str):
    read(job_id);stops[job_id]=True
    return {'stop_requested':True}

@app.get('/assets/{job_id}/{name:path}')
def asset(job_id:str,name:str):
    path=folder(job_id);target=(path/name).resolve()
    if not target.is_relative_to(path.resolve()) or target.suffix not in {'.mp4','.webm','.mkv','.mov','.jpg','.png','.blend'} or not target.is_file():raise HTTPException(404)
    return FileResponse(target)
