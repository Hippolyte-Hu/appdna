"""Run the real FFmpeg → Gladia → H tutorial-learning slice, without GUI input."""
import argparse
import asyncio
import json
from pathlib import Path
from app.config import get_settings
from app.engines.media import prepare_media
from app.engines.tutorial import learn_tutorial
from app.providers.gladia import GladiaProvider
from app.providers.hcompany import HCompanyProvider

async def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('video',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    manifest=args.output/'manifest.json'
    media=json.loads(manifest.read_text()) if manifest.exists() else prepare_media(args.video.resolve(),args.output.resolve())
    settings=get_settings()
    result=await learn_tutorial(media,args.output,
        GladiaProvider(settings.gladia_api_key,settings.gladia_base_url),
        HCompanyProvider(settings.hcompany_api_key,settings.hcompany_base_url,settings.hcompany_model),
        objective='Reproduce ONLY the FIRST demonstrated workflow: round the default selected cube with a Bevel modifier and smooth shading. Stop before the presenter deletes modifiers and demonstrates the alternative edit-mode workflow. Do not invent a material or save step.')
    print(json.dumps({'status':result['status'],'title':result['title'],'steps':len(result['steps']),
                      'transcript_segments':len(json.loads((args.output/'transcript.json').read_text())),
                      'frames':len(media['frames']),'verification':result['verification']},indent=2),flush=True)

if __name__=='__main__':asyncio.run(main())
