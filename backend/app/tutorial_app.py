"""Isolated video-learning workspace. Does not restart the existing AppDNA app."""
import asyncio
import json
import os
import shutil
import subprocess
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse
from fastapi import FastAPI,File,Form,HTTPException,Query,Request,UploadFile
from fastapi.responses import FileResponse,JSONResponse,HTMLResponse
from pydantic import BaseModel
from app.config import get_settings
from app.engines.media import prepare_media
from app.engines.captions import read_captions,MAX_CAPTION_BYTES
from app.agents.video_learning import learn_video_source,write_json
from app.engines.tutorial_expectations import build_expectations
from app.engines.tutorial_runner import execute_plan,youtube_url,resumable_failure
from app.drivers.blender_tutorial import BlenderTutorialDriver,guard
from app.providers.gladia import GladiaProvider
from app.providers.hcompany import HCompanyProvider

ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'tasks/video-agent/evidence/jobs'
DATA.mkdir(parents=True,exist_ok=True)
stops={}
active=None
running_tasks=set()
executions={}
IN_PROGRESS={'queued','fetching_video','separating_media','learning','checking_artifact_targets',
             'starting_blender','running','saving_artifact','paused','resuming'}


def recover_jobs():
    for path in DATA.glob('*/job.json'):
        job=json.loads(path.read_text())
        if job.get('status') in IN_PROGRESS:
            job.update(status='blocked',error='Controller restarted before completion. Evidence is retained; start a fresh tutorial to retry.')
            save(path.parent,job)


@asynccontextmanager
async def lifespan(_app):
    global active
    recover_jobs()
    try:yield
    finally:
        pending=list(running_tasks)
        for task in pending:task.cancel()
        if pending:await asyncio.gather(*pending,return_exceptions=True)
        try:
            for context in list(executions.values()):
                await asyncio.to_thread(context['driver'].close)
        finally:executions.clear();active=None


app=FastAPI(title='AppDNA — Learn by watching',docs_url=None,redoc_url=None,lifespan=lifespan)

@app.middleware('http')
async def same_origin(request:Request,call_next):
    if request.method not in {'GET','HEAD'}:
        origin=request.headers.get('origin')
        hosts={request.headers.get('host')}
        if request.client and request.client.host in {'127.0.0.1','::1'}:
            hosts.add(request.headers.get('x-forwarded-host'))
        if origin and urlparse(origin).netloc not in hosts:
            return JSONResponse({'detail':'Cross-origin control is not allowed'},status_code=403)
    return await call_next(request)


def folder(job_id):
    if not isinstance(job_id,str) or len(job_id)!=32 or any(c not in '0123456789abcdef' for c in job_id):raise HTTPException(404,'Tutorial not found')
    path=DATA/job_id
    if not path.is_dir():raise HTTPException(404,'Tutorial not found')
    return path


def read(job_id):return json.loads((folder(job_id)/'job.json').read_text())
def save(path,data):
    write_json(path/'job.json',data)


def providers():
    s=get_settings()
    return GladiaProvider(s.gladia_api_key,s.gladia_base_url),HCompanyProvider(s.hcompany_api_key,s.hcompany_base_url,
        os.environ.get('APPDNA_LEARNING_MODEL',getattr(s,'appdna_learning_model','') or s.hcompany_model))


def action_provider():
    s=get_settings()
    return HCompanyProvider(s.hcompany_api_key,s.hcompany_base_url,
        os.environ.get('APPDNA_ACTION_MODEL',getattr(s,'appdna_action_model','') or s.hcompany_model))


def spawn(coro):
    task=asyncio.create_task(coro);running_tasks.add(task);task.add_done_callback(running_tasks.discard)


async def learn(job_id):
    path=folder(job_id);job=read(job_id)
    stops.setdefault(job_id,False)
    def checkpoint():
        if stops.get(job_id,False):raise InterruptedError('Learning stopped by caller')
    try:
        checkpoint()
        if job.get('youtube_url'):
            job['status']='fetching_video';save(path,job)
            def download():
                result=subprocess.run([sys.executable,'-m','yt_dlp','--no-playlist','--no-warnings','--socket-timeout','15','--retries','1',
                    '--max-filesize','100M','-f','bv*[height<=720]+ba/b[height<=720]', '--merge-output-format','mp4',
                    '--js-runtimes','node','--write-subs','--write-auto-subs','--sub-langs','en','--sub-format','json3',
                    '-o',str(path/'source.%(ext)s'),job['youtube_url']],capture_output=True,timeout=180)
                if result.returncode:raise ValueError('Could not obtain YouTube media. Upload an authorized local video instead.')
                files=[p for p in path.glob('source.*') if p.suffix in {'.mp4','.webm','.mkv','.mov'}]
                if len(files)!=1:raise ValueError('No single usable video was downloaded')
                return files[0]
            source=await asyncio.to_thread(download)
        else:source=path/job['source_file']
        checkpoint()
        if source.stat().st_size>100*1024*1024:raise ValueError('Video exceeds 100 MB')
        job.update(status='separating_media',source_file=source.name);save(path,job)
        media=await asyncio.to_thread(prepare_media,source,path)
        checkpoint()
        if not (path/'transcript.json').exists():
            captions=next(iter(sorted(path.glob('source.en*.json3'))),None)
            if captions:
                write_json(path/'transcript.json',read_captions(captions,media['duration']))
                job['transcript_origin']='youtube_captions'
        asr,vision=providers()
        if not (path/'transcript.json').exists() and not get_settings().gladia_api_key:
            raise ValueError('No usable captions. Configure GLADIA_API_KEY or upload a timestamped transcript with the video.')
        if not get_settings().hcompany_api_key:
            raise ValueError('Configure HCOMPANY_API_KEY before learning from video.')
        job['status']='learning';save(path,job)
        result=await learn_video_source(media,path,asr,vision,source=source,objective=job['objective'],
            source_url=job.get('youtube_url'),should_stop=lambda:stops.get(job_id,False))
        job['status']='stopped' if stops.get(job_id,False) else 'ready_for_review' if result['status']=='source_checked' else result['status']
        job['error']='' if result['status']=='source_checked' else result.get('reason','')
        if result.get('title'):job['title']=result['title']
        save(path,job)
    except InterruptedError as exc:
        job.update(status='stopped',error=str(exc));save(path,job)
    except Exception as exc:
        job.update(status='blocked',error=str(exc)[:400]);save(path,job)


def workbench_html(base=''):
    html=(ROOT/'tasks/video-agent/index.html').read_text()
    return HTMLResponse(html.replace('src="./workbench.js"',f'src="{base}/workbench.js" data-base="{base}"'))

@app.get('/')
def home(request:Request):return workbench_html(request.scope.get('root_path','').rstrip('/'))

@app.get('/workbench.js')
def workbench_script():return FileResponse(ROOT/'tasks/video-agent/workbench.js',media_type='text/javascript')

@app.get('/api/tutorials')
def listing():
    return [json.loads(p.read_text()) for p in sorted(DATA.glob('*/job.json'),key=lambda p:p.stat().st_mtime,reverse=True)]

@app.get('/api/desktop')
async def desktop():
    try:
        lock=await asyncio.to_thread(guard,'lock')
        permissions=await asyncio.to_thread(guard,'permissions')
        missing=[name for key,name in [('accessibility','Device Control and Data Access / Accessibility'),('screen_recording','Screen Recording')]
                 if permissions.get(key) is False]
        return {**lock,'available':not missing,'permissions':permissions,
                'reason':('macOS permission required: '+', '.join(missing)) if missing else ''}
    except (OSError,RuntimeError,subprocess.SubprocessError) as exc:
        return {'locked':True,'available':False,'reason':str(exc)[:300]}


@app.get('/api/runtime')
def runtime():
    s=get_settings()
    return {'providers':{'hcompany':bool(s.hcompany_api_key),'gladia':bool(s.gladia_api_key)},
            'tools':{name:bool(shutil.which(name)) for name in ('ffmpeg','ffprobe','node')},
            'learning_model':os.environ.get('APPDNA_LEARNING_MODEL',s.appdna_learning_model or s.hcompany_model),
            'action_model':os.environ.get('APPDNA_ACTION_MODEL',s.appdna_action_model or s.hcompany_model),
            'execution_platform':'macOS' if sys.platform=='darwin' else 'unsupported',
            'max_video_bytes':100*1024*1024,'max_duration_seconds':600}

@app.post('/api/tutorials')
async def create(url:str=Form(''),objective:str=Form('Reproduce the FIRST Bevel modifier workflow only; stop before the edit-mode alternative.'),video:UploadFile|None=File(None),transcript:UploadFile|None=File(None)):
    has_video=bool(video and video.filename)
    if bool(url.strip())==has_video:raise HTTPException(400,'Provide one YouTube link OR one video file')
    objective=objective.strip()
    if not 1<=len(objective)<=1000:raise HTTPException(400,'Objective must be 1–1000 characters')
    try:canonical=youtube_url(url) if url.strip() else None
    except ValueError as exc:raise HTTPException(400,str(exc))
    if has_video and Path(video.filename).suffix.lower() not in {'.mp4','.mov','.webm','.mkv'}:raise HTTPException(400,'Upload MP4, MOV, WebM or MKV')
    job_id=uuid.uuid4().hex;path=DATA/job_id;path.mkdir()
    job={'id':job_id,'title':'Blender tutorial','objective':objective,'status':'queued','youtube_url':canonical}
    if transcript and transcript.filename:
        raw=await transcript.read(MAX_CAPTION_BYTES+1)
        if len(raw)>MAX_CAPTION_BYTES:
            shutil.rmtree(path);raise HTTPException(413,'Transcript exceeds 2 MB')
        caption=path/'uploaded-transcript.json'
        caption.write_bytes(raw)
        try:write_json(path/'transcript.json',read_captions(caption))
        except ValueError as exc:
            shutil.rmtree(path);raise HTTPException(400,str(exc)) from exc
        job['transcript_origin']='uploaded_captions'
    if has_video:
        source=path/('source'+Path(video.filename).suffix.lower());size=0
        with source.open('wb') as handle:
            while chunk:=await video.read(1024*1024):
                size+=len(chunk)
                if size>100*1024*1024:
                    shutil.rmtree(path);raise HTTPException(413,'Video exceeds 100 MB')
                handle.write(chunk)
        job['source_file']=source.name
        if not size:
            shutil.rmtree(path);raise HTTPException(400,'Uploaded video is empty')
    stops[job_id]=False
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


@app.post('/api/video-sources/{job_id}/reuse')
async def reuse_video_source(job_id:str):
    """Transfer the checked procedure, never a prior scene or run receipt."""
    original=folder(job_id)
    from app.engines.tutorial_expectations import source_state,validate_binding
    try:knowledge,_=await asyncio.to_thread(source_state,original)
    except (ValueError,KeyError,FileNotFoundError) as exc:raise HTTPException(409,str(exc)) from exc
    job_id=uuid.uuid4().hex;destination=DATA/job_id
    def clone():
        destination.mkdir()
        try:
            for name in ('plan.json','knowledge.json','agent.json','transcript.json','manifest.json',knowledge['source_file']):
                source=original/name
                if source.is_file():shutil.copy2(source,destination/name)
            for media_file in [*original.glob('frame_*.jpg'),original/'audio.wav']:
                if media_file.is_file():shutil.copy2(media_file,destination/media_file.name)
            if (destination/'manifest.json').is_file():
                manifest=json.loads((destination/'manifest.json').read_text())
                manifest['audio_path']=str(destination/'audio.wav') if (destination/'audio.wav').exists() else None
                manifest['frames']=[frame for frame in manifest.get('frames',[]) if (destination/Path(frame['image']).name).is_file()]
                write_json(destination/'manifest.json',manifest)
            if (original/'agent_frames').is_dir():shutil.copytree(original/'agent_frames',destination/'agent_frames')
            if (original/'artifact-expectations.json').is_file():
                target=json.loads((original/'artifact-expectations.json').read_text())
                validate_binding(target,original)
                write_json(destination/'artifact-expectations.json',target)
        except BaseException:
            shutil.rmtree(destination);raise
    await asyncio.to_thread(clone)
    job={'id':job_id,'title':knowledge['title'],'objective':knowledge['objective'],
         'source_file':knowledge['source_file'],'youtube_url':knowledge.get('source_url'),
         'status':'ready_for_review','reused_from':original.name,
         'reuse':'Reusing checked source knowledge only; no previous scene or execution receipt.'}
    save(destination,job);stops[job_id]=False
    return job


@app.post('/api/tutorials/{job_id}/project')
def project_from_video(job_id:str):
    from app.db import init_db
    from app.engines.video_projects import import_video_project
    init_db()
    try:project_id=import_video_project(folder(job_id))
    except (ValueError,KeyError,FileNotFoundError) as exc:raise HTTPException(409,str(exc)) from exc
    return {'project_id':project_id,'url':f'/projects/{project_id}'}


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
    permission=await desktop()
    if not permission['available']:raise HTTPException(409,permission.get('reason','Desktop unavailable'))
    if active:raise HTTPException(409,'Another Blender execution is active')
    if (path/'run').exists():raise HTTPException(409,'This tutorial already has a run receipt; import again for a fresh run')
    # Reserve after preflight and before the next await, so simultaneous
    # requests cannot launch two desktop controllers.
    active=job_id;stops[job_id]=False
    try:
        if await asyncio.to_thread(lambda:guard('lock')['locked']):raise HTTPException(409,'Mac is locked. Unlock the Mac before running Blender actions.')
    except HTTPException:
        active=None;raise
    except (OSError,RuntimeError,subprocess.SubprocessError) as exc:
        active=None;raise HTTPException(409,str(exc)[:300]) from exc
    if stops.get(job_id,False):
        active=None;job['status']='stopped';save(path,job);return {'status':'stopped'}
    job['status']='starting_blender';save(path,job)
    spawn(execute(job_id));return {'status':'starting_blender'}

def paused_job(path,job,stage,reason):
    global active
    active=job['id']
    job.update(status='paused',resume_stage=stage,error=str(reason)[:400]);save(path,job)


@app.post('/api/tutorials/{job_id}/resume')
async def resume_execution(job_id:str,approval:Approval):
    global active
    job=read(job_id);path=folder(job_id)
    if not approval.reviewed or not approval.confirm_scratch:raise HTTPException(400,'Review the same scratch workflow before resuming')
    if job['status']!='paused' or job_id not in executions:
        raise HTTPException(409,'No live sandbox-attested execution to resume; reuse the knowledge in a new scratch run')
    if active not in (None,job_id):raise HTTPException(409,'Another Blender execution is active')
    active=job_id;stops[job_id]=False
    job['status']='resuming';save(path,job)
    spawn(execute(job_id,resume=True));return {'status':'resuming'}


async def execute(job_id, *, resume=False):
    global active
    path=folder(job_id);job=read(job_id)
    context=executions.get(job_id) if resume else None
    driver=context['driver'] if context else None
    expectations=context.get('expectations') if context else None
    stage=context.get('stage','workflow') if context else 'workflow'
    keep_alive=False
    try:
        if stops.get(job_id,True):
            job['status']='stopped';save(path,job);return
        if resume:
            if not context:raise RuntimeError('Live sandbox attestation is missing')
            if expectations:
                from app.engines.tutorial_expectations import validate_binding
                validate_binding(expectations,path)
            driver=await asyncio.to_thread(BlenderTutorialDriver.resume,driver.pid,path/'run',activate=True)
        else:
            _,vision=providers()
            if (path/'knowledge.json').exists():
                job['status']='checking_artifact_targets';save(path,job)
                expectations=await build_expectations(path,vision)
            if stops.get(job_id,True):job['status']='stopped';save(path,job);return
            driver=await asyncio.to_thread(BlenderTutorialDriver.launch,path/'run')
            (path/'run/pid.json').write_text(json.dumps({'pid':driver.pid}))
            context={'driver':driver,'expectations':expectations,'stage':'workflow'}
            executions[job_id]=context
        vision=action_provider()
        job['action_model']=vision.model;save(path,job)
        if stage=='workflow':
            job['status']='running';save(path,job)
            kwargs={'resume':True} if resume else {}
            result=await execute_plan(json.loads((path/'plan.json').read_text()),path/'run',driver,vision,lambda:stops.get(job_id,True),**kwargs)
            job['status']=result['status'];job['error']=result.get('reason','');save(path,job)
            if result['status']=='paused':
                keep_alive=True;paused_job(path,job,stage,result.get('reason','Execution paused'));return
            if result['status']!='observed_complete' or stops.get(job_id,True):return
            stage='artifact';context['stage']=stage
        if stage=='artifact' and not stops.get(job_id,True):
            from app.engines.tutorial_artifact import save_and_verify
            job['status']='saving_artifact';save(path,job)
            kwargs={'resume':True} if resume else {}
            verification=await save_and_verify(path/'run',driver,vision,lambda:stops.get(job_id,True),expectations=expectations,source_folder=path,**kwargs)
            if verification['verification']=='paused':
                keep_alive=True;paused_job(path,job,stage,verification.get('reason','Saving paused'));return
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
                verification={'verification':'failed','reason':verification.get('reason') or 'No saved source-bound artifact proof','reference_check':verification}
            (path/'run/verification.json').write_text(json.dumps(verification,indent=2))
            job['status']=('saved_unverified' if verification['verification']=='not_assessed' else
                           'verified' if verification['verification']=='verified' else 'artifact_failed')
            if bound:job['verification_scope']=verification['scope']
            job['error']='' if job['status'] in {'verified','saved_unverified'} else verification.get('reason','Saved artifact does not match the source targets')
            save(path,job)
    except Exception as exc:
        if driver is not None and resumable_failure(exc) and not stops.get(job_id,True):
            keep_alive=True;paused_job(path,job,stage,exc)
        else:
            job.update(status='stopped' if stops.get(job_id,False) else 'blocked',error=str(exc)[:400]);save(path,job)
    finally:
        if not keep_alive:
            try:
                if driver is not None and hasattr(driver,'close'):
                    await asyncio.to_thread(driver.close)
            finally:executions.pop(job_id,None);active=None

@app.post('/api/tutorials/{job_id}/stop')
async def stop(job_id:str):
    global active
    job=read(job_id);stops[job_id]=True
    if job['status']=='paused':
        context=executions.pop(job_id,None)
        if context:await asyncio.to_thread(context['driver'].close)
        job['status']='stopped';save(folder(job_id),job)
        if active==job_id:active=None
    return {'stop_requested':True}

@app.get('/assets/{job_id}/{name:path}')
def asset(job_id:str,name:str):
    path=folder(job_id);target=(path/name).resolve()
    if not target.is_relative_to(path.resolve()) or target.suffix not in {'.mp4','.webm','.mkv','.mov','.jpg','.png','.blend'} or not target.is_file():raise HTTPException(404)
    return FileResponse(target)
