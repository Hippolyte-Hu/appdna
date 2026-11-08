"""Bounded screenshot → H Company action → input loop, with durable receipts."""
import asyncio
import json
import re
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from app.engines.tutorial import validate_action


def youtube_url(value: str) -> str:
    url=urlparse(value.strip())
    if url.scheme!='https' or url.username or url.password or url.port not in (None,443):raise ValueError('Use an HTTPS YouTube video link')
    query=parse_qs(url.query)
    if any(k not in {'v','t','si'} for k in query):raise ValueError('Single videos only; remove playlist parameters')
    if url.hostname in {'youtube.com','www.youtube.com','m.youtube.com'} and url.path=='/watch':
        video=query.get('v',[''])[0]
    elif url.hostname=='youtu.be':video=url.path.lstrip('/')
    else:raise ValueError('Use a youtube.com/watch or youtu.be video link')
    if not re.fullmatch(r'[A-Za-z0-9_-]{11}',video):raise ValueError('Invalid YouTube video ID')
    return 'https://www.youtube.com/watch?v='+video


async def execute_plan(plan: dict, folder: Path, driver, vision, stopped, *, max_actions=12, save_target: Path | None=None) -> dict:
    folder.mkdir(parents=True,exist_ok=True)
    events=[]
    result={'status':'running','verification':'not_independently_verified','events':events}
    def persist():
        (folder/'run.json').write_text(json.dumps(result,indent=2))
    persist()
    try:
        for step in plan['steps']:
            result['current_step']=step['id']
            for _ in range(max_actions):
                if stopped():result['status']='stopped';return result
                before=folder/f'before-{len(events):03d}.png'
                await asyncio.to_thread(driver.capture,before)
                action=await vision.tutorial_action(step=step,image_bytes=before.read_bytes(),history=events)
                if stopped():result['status']='stopped';return result
                action=validate_action(action,save_target=save_target)
                event={'step':step['id'],'before':before.name,'action':action}
                signature=lambda a:tuple(a.get(k) for k in ('action','x','y','text'))
                recent=events[-2:]
                if action['action'] not in {'done','blocked','wait'} and len(recent)==2 and all(
                    e['step']==step['id'] and signature(e['action'])==signature(action) for e in recent
                ):
                    result.update(status='blocked',reason='Repeated identical action; inspect the current screen before retrying')
                    return result
                if action['action']=='blocked':
                    events.append(event);result.update(status='blocked',reason=action.get('reason','Model blocked'));return result
                if action['action']=='done':
                    events.append(event);persist();break
                if save_target is None:
                    await asyncio.to_thread(driver.perform,action)
                else:
                    await asyncio.to_thread(driver.perform,action,save_target=save_target)
                await asyncio.sleep(.6)
                after=folder/f'after-{len(events):03d}.png'
                await asyncio.to_thread(driver.capture,after)
                event['after']=after.name
                events.append(event);persist()
            else:
                result.update(status='blocked',reason='Action budget exhausted; step not confirmed');return result
        result['status']='observed_complete'
        return result
    except Exception as exc:
        result.update(status='blocked',reason=str(exc)[:500])
        return result
    finally:persist()
