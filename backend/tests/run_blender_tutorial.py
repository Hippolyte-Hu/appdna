"""Run a reviewed tutorial in a NEW, write-confined Blender process."""
import argparse
import asyncio
import json
from pathlib import Path
from app.config import get_settings
from app.drivers.blender_tutorial import BlenderTutorialDriver
from app.engines.tutorial_runner import execute_plan
from app.engines.tutorial_artifact import save_and_verify
from app.engines.tutorial_expectations import build_expectations
from app.providers.hcompany import HCompanyProvider


async def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('job',type=Path)
    parser.add_argument('--model',default='holo4-27b')
    parser.add_argument('--resume-from',type=Path)
    parser.add_argument('--save-only',action='store_true')
    args=parser.parse_args()
    if args.resume_from:raise ValueError('Cross-job resume is disabled; create a fresh sandboxed execution from the checked source')
    folder=args.job/'run'
    if folder.exists():raise RuntimeError('Refusing to overwrite execution evidence')
    plan=json.loads((args.job/'plan.json').read_text())
    settings=get_settings()
    vision=HCompanyProvider(settings.hcompany_api_key,settings.hcompany_base_url,args.model)
    expectations=None
    if (args.job/'knowledge.json').exists():
        expectations=await build_expectations(args.job,vision)
    elif plan.get('source_sha256'):
        raise ValueError('Source-bound plan requires checked video knowledge before execution')
    driver=await asyncio.to_thread(BlenderTutorialDriver.launch,folder)
    (folder/'pid.json').write_text(json.dumps({'pid':driver.pid}))
    result=({'status':'artifact_capture_only','events':[],'verification':'not_independently_verified'} if args.save_only else
        await execute_plan(plan,folder,driver,vision,lambda:(folder/'STOP').exists()))
    if args.save_only or result['status']=='observed_complete':
        verification=await save_and_verify(folder,driver,vision,lambda:(folder/'STOP').exists(),expectations=expectations,source_folder=args.job)
        (folder/'verification.json').write_text(json.dumps(verification,indent=2))
    print(json.dumps({'pid':driver.pid,'status':result['status'],'events':len(result['events']),'reason':result.get('reason'),'verification':result['verification']},indent=2),flush=True)


if __name__=='__main__':asyncio.run(main())
