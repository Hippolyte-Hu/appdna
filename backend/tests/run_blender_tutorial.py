"""Run the reviewed tutorial in a NEW scratch Blender instance, using Holo for every action."""
import argparse
import asyncio
import json
from pathlib import Path
from app.config import get_settings
from app.drivers.blender_tutorial import BlenderTutorialDriver
from app.engines.tutorial_runner import execute_plan
from app.engines.tutorial_artifact import save_and_verify
from app.providers.hcompany import HCompanyProvider

async def main():
    parser=argparse.ArgumentParser();parser.add_argument('job',type=Path);parser.add_argument('--model',default='holo4-27b');parser.add_argument('--resume-from',type=Path);parser.add_argument('--save-only',action='store_true');args=parser.parse_args()
    plan=json.loads((args.job/'plan.json').read_text())
    folder=args.job/'run'
    if folder.exists():raise RuntimeError('Refusing to overwrite execution evidence')
    if args.resume_from:
        from types import SimpleNamespace
        from app.drivers.blender_tutorial import guard
        pid=json.loads((args.resume_from/'run/pid.json').read_text())['pid']
        guard('probe',pid)
        folder.mkdir(parents=True)
        driver=BlenderTutorialDriver(SimpleNamespace(pid=pid))
        (folder/'resumed_from.json').write_text(json.dumps({'run':str(args.resume_from.resolve()),'pid':pid}))
    else:
        driver=await asyncio.to_thread(BlenderTutorialDriver.launch,folder)
    (folder/'pid.json').write_text(json.dumps({'pid':driver.pid}))
    settings=get_settings()
    vision=HCompanyProvider(settings.hcompany_api_key,settings.hcompany_base_url,args.model)
    result=({'status':'artifact_capture_only','events':[],'verification':'not_independently_verified'} if args.save_only else
            await execute_plan(plan,folder,driver,vision,lambda:(folder/'STOP').exists()))
    if args.save_only or result['status']=='observed_complete':
        verification=await save_and_verify(folder,driver,vision,lambda:(folder/'STOP').exists())
        (folder/'verification.json').write_text(json.dumps(verification,indent=2))
    print(json.dumps({'pid':driver.pid,'status':result['status'],'events':len(result['events']),'reason':result.get('reason'),'verification':result['verification']},indent=2),flush=True)

if __name__=='__main__':asyncio.run(main())
