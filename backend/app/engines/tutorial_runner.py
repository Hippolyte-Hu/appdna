"""Bounded screenshot → H Company action → input loop, with durable receipts."""
import asyncio
import json
import re
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from app.engines.tutorial import validate_action
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


class SavePolicy:
    """Directory-first sequencing. OS write confinement remains the hard boundary."""
    def __init__(self,target: Path):
        self.target=target;self.directory_set=False;self.filename_set=False

    def check(self,action: dict) -> str | None:
        kind=action['action'];text=action.get('text','')
        if kind in {'wait','blocked'}:return None
        if kind=='done':
            return None if self.target.is_file() else 'The requested artifact does not exist; do not declare done.'
        if self.target.exists():return 'Artifact already exists. No further save input or overwrite is allowed.'
        if kind=='key' and text in {'ctrl+shift+s','escape'}:return None
        if kind=='set_text':
            if text==str(self.target.parent)+'/':return None
            if text==self.target.name and self.directory_set:return None
        if kind=='click' and self.directory_set and self.filename_set:return None
        return 'Save policy: first set_text the EXACT top directory, then set_text the filename, then click Save As. Other save inputs are rejected.'

    def context(self):
        phase=('done' if self.target.is_file() else 'confirm_save' if self.filename_set else 'filename' if self.directory_set else 'directory')
        return {'required_next':phase,'directory':str(self.target.parent)+'/','filename':self.target.name}

    def posted(self,action: dict):
        if action['action']=='key':self.directory_set=False;self.filename_set=False
        if action['action']=='set_text':
            if action['text']==str(self.target.parent)+'/':self.directory_set=True;self.filename_set=False
            elif action['text']==self.target.name:self.filename_set=True


async def execute_plan(plan: dict, folder: Path, driver, vision, stopped, *, max_actions=12, save_target: Path | None=None) -> dict:
    folder.mkdir(parents=True,exist_ok=True)
    events=[]
    save_policy=SavePolicy(save_target) if save_target is not None else None
    result={'status':'running','verification':'not_independently_verified','events':events,'provider_errors':[]}
    def persist():
        (folder/'run.json').write_text(json.dumps(result,indent=2))
    persist()
    try:
        for step in plan['steps']:
            result['current_step']=step['id']
            provider_failures=0
            for action_index in range(max_actions):
                if stopped():result['status']='stopped';return result
                before=folder/f'before-{len(events):03d}.png'
                await asyncio.to_thread(driver.capture,before)
                request_step=dict(step,save_policy=save_policy.context()) if save_policy else step
                try:
                    history=events+result['provider_errors'][-1:]
                    action=await vision.tutorial_action(step=request_step,image_bytes=before.read_bytes(),history=history)
                except (ProviderError,RuntimeError,TimeoutError) as exc:
                    if not isinstance(exc,TimeoutError) and str(exc)!='H Company took too long to answer':raise
                    retrying=provider_failures<1 and action_index+1<max_actions
                    error_frame=folder/f"provider-error-{len(result['provider_errors'])+1:03d}.png"
                    before.rename(error_frame)
                    result['provider_errors'].append({'step':step['id'],'before':error_frame.name,'provider_error':str(exc)[:500],'input_sent':False,'retrying':retrying})
                    persist();provider_failures+=1
                    if retrying:continue
                    raise
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
                if save_policy is not None:
                    rejection=save_policy.check(action)
                    if rejection:
                        event['rejected']=rejection;events.append(event);persist()
                        continue
                if action['action']=='blocked':
                    events.append(event);result.update(status='blocked',reason=action.get('reason','Model blocked'));return result
                if action['action']=='done':
                    events.append(event);persist();break
                if save_target is None:
                    await asyncio.to_thread(driver.perform,action)
                else:
                    await asyncio.to_thread(driver.perform,action,save_target=save_target)
                    if save_policy is not None:save_policy.posted(action)
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
