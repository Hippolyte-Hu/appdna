"""Bounded screenshot → H Company action → input loop, with durable receipts."""
import asyncio
import json
import hashlib
import re
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from app.engines.tutorial import validate_action
from app.agents.video_learning import write_json
from app.providers.base import ProviderError


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


def resumable_failure(exc):
    return (isinstance(exc,ProviderError) and (exc.status is None or exc.status==429 or exc.status>=500)
            or isinstance(exc,RuntimeError) and any(text in str(exc).lower() for text in ('not foreground','locked','permission is missing')))


async def execute_plan(plan: dict, folder: Path, driver, vision, stopped, *, max_actions=12, save_target: Path | None=None, resume=False) -> dict:
    folder.mkdir(parents=True,exist_ok=True)
    receipt=folder/'run.json'
    plan_hash=hashlib.sha256(json.dumps(plan,sort_keys=True,allow_nan=False).encode()).hexdigest()
    if receipt.exists():
        if not resume:raise ValueError('Existing execution evidence requires an explicit resume')
        result=json.loads(receipt.read_text())
        ids=[step['id'] for step in plan['steps']]
        complete=result.get('completed_steps',[])
        if result.get('plan_sha256')!=plan_hash or complete!=ids[:len(complete)]:
            raise ValueError('Cannot resume a changed execution plan or invalid checkpoint')
        if result['status'] not in {'paused','observed_complete'}:raise ValueError('Execution is not resumable')
    else:
        result={'verification':'not_independently_verified','events':[], 'plan_sha256':plan_hash,
                'completed_steps':[],'captures':0,'action_attempts':{}}
    result['status']='running';result.pop('reason',None)
    events=result['events']
    def persist():
        write_json(folder/'run.json',result)
    persist()
    try:
        for step in plan['steps']:
            if step['id'] in result['completed_steps']:continue
            result['current_step']=step['id']
            remaining=max_actions-result['action_attempts'].get(step['id'],0)
            for _ in range(remaining):
                if stopped():result['status']='stopped';return result
                capture=result['captures'];result['captures']+=1;persist()
                before=folder/f'before-{capture:03d}.png'
                await asyncio.to_thread(driver.capture,before)
                result['action_attempts'][step['id']]=result['action_attempts'].get(step['id'],0)+1;persist()
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
                    events.append(event);result['completed_steps'].append(step['id']);persist();break
                if save_target is None:
                    await asyncio.to_thread(driver.perform,action)
                else:
                    await asyncio.to_thread(driver.perform,action,save_target=save_target)
                await asyncio.sleep(.6)
                after=folder/f'after-{capture:03d}.png'
                await asyncio.to_thread(driver.capture,after)
                event['after']=after.name
                event['capture_changed']=before.read_bytes()!=after.read_bytes()
                events.append(event);persist()
            else:
                result.update(status='blocked',reason='Action budget exhausted; step not confirmed');return result
        result['status']='observed_complete'
        return result
    except Exception as exc:
        result.update(status='stopped' if stopped() else 'paused' if resumable_failure(exc) else 'blocked',reason=str(exc)[:500])
        return result
    finally:persist()
