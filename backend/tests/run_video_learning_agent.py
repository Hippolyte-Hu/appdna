"""Run the real learning Agent alone. Reuses media/ASR, NEVER a previous plan."""
import argparse
import asyncio
import json
import shutil
import uuid
from pathlib import Path
from app.agents.video_learning import learn_video_source,write_json
from app.tutorial_app import DATA,providers,save


async def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-job',required=True)
    parser.add_argument('--objective',default='Reproduce the first Bevel modifier workflow: round the selected cube, adjust demonstrated parameters and smooth shading. Stop before the edit-mode alternative.')
    args=parser.parse_args()
    if len(args.input_job)!=32 or any(c not in '0123456789abcdef' for c in args.input_job):raise ValueError('Invalid source job id')
    original=DATA/args.input_job
    previous=json.loads((original/'job.json').read_text())
    job_id=uuid.uuid4().hex;folder=DATA/job_id;folder.mkdir()
    source=original/previous['source_file']
    shutil.copy2(source,folder/source.name)
    for name in ['manifest.json','transcript.json']:
        shutil.copy2(original/name,folder/name)
    job={'id':job_id,'title':'Video learning Agent — fresh reasoning','objective':args.objective,
         'source_file':source.name,'youtube_url':previous.get('youtube_url'),'status':'learning',
         'reuse':'Existing video bytes and ASR only; no previous plan, observations or review supplied.'}
    save(folder,job)
    (DATA.parent/'source-agent-id.txt').write_text(job_id)
    print(json.dumps({'id':job_id,'status':'learning','reuse':job['reuse']}),flush=True)
    media=json.loads((folder/'manifest.json').read_text())
    asr,vision=providers()
    result=await learn_video_source(media,folder,asr,vision,source=folder/source.name,
        objective=args.objective,source_url=job['youtube_url'])
    job['status']='ready_for_review' if result['status']=='source_checked' else result['status']
    job['error']='' if result['status']=='source_checked' else result.get('reason','')
    if result.get('title'):job['title']=result['title']
    save(folder,job)
    print(json.dumps({'id':job_id,'status':job['status'],'steps':result['steps'],
        'reason':result.get('reason'),'source_checks':result.get('source_checks',[])}),flush=True)


if __name__=='__main__':asyncio.run(main())
