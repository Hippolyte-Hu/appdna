"""Read-only live grounding diagnostic; does not post any GUI inputs."""
import asyncio,json
from pathlib import Path
from app.config import get_settings
from app.providers.hcompany import HCompanyProvider
from app.drivers.blender_tutorial import BlenderTutorialDriver
async def main():
    f=Path('../tasks/video-agent/evidence/live-replication-03')
    pid=json.loads((f/'run/pid.json').read_text())['pid']
    d=BlenderTutorialDriver(type('Process',(),{'pid':pid})())
    d.capture(f/'compare-before.png')
    s=get_settings();step=json.loads((f/'plan.json').read_text())['steps'][0]
    async def query(model):
        p=HCompanyProvider(s.hcompany_api_key,s.hcompany_base_url,model)
        try:result=await p.tutorial_action(step=step,image_bytes=(f/'compare-before.png').read_bytes(),history=[])
        except Exception as exc:result={'error':str(exc)}
        return {'model':model,'result':result}
    result=await asyncio.gather(*(query(m) for m in ['holo4-27b','holo4-35b-a3b']))
    (f/'grounding-diagnostic.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
asyncio.run(main())
