"""Video-derived, timestamp-grounded Blender plans; observations are not proof."""
import json
import math
import re
from pathlib import Path

FIELDS=('id','instruction','expected','uncertainty')
KEYS={'return','escape','tab','space','up','down','left','right','f3','shift+tab'}


def validate_plan(value: dict, duration: float) -> dict:
    if not isinstance(value,dict) or not math.isfinite(duration) or duration<=0:
        raise ValueError('Invalid tutorial plan')
    for key in ('title','objective'):
        if not isinstance(value.get(key),str) or not value[key].strip():raise ValueError('Missing '+key)
    for key in ('prerequisites','limitations'):
        if not isinstance(value.get(key),list) or any(not isinstance(x,str) for x in value[key]):raise ValueError('Invalid '+key)
    steps=value.get('steps')
    if not isinstance(steps,list) or not 1<=len(steps)<=24:raise ValueError('Expected 1–24 grounded steps')
    seen=set();previous=-1
    for step in steps:
        if not isinstance(step,dict):raise ValueError('Invalid step')
        for key in FIELDS:
            if not isinstance(step.get(key),str) or (key!='uncertainty' and not step[key].strip()):raise ValueError('Missing step '+key)
        if step['id'] in seen:raise ValueError('Duplicate step id')
        seen.add(step['id'])
        start,end=step.get('start'),step.get('end')
        if any(type(x) not in (int,float) or not math.isfinite(x) for x in (start,end)):
            raise ValueError('Invalid timestamps')
        if not 0<=start<=end<=duration or start<previous:raise ValueError('Step outside ordered source timeline')
        previous=start
    return {**value,'status':'ready_for_review','verification':'not_executed'}


async def learn_tutorial(media: dict, folder: Path, asr, vision, *, objective: str) -> dict:
    if not media.get('has_video') or not media.get('has_audio'):raise ValueError('Tutorial needs video and spoken audio')
    transcript_path=folder/'transcript.json'
    if transcript_path.exists():
        transcript=json.loads(transcript_path.read_text())
    else:
        transcript=await asr.transcribe_file(Path(media['audio_path']))
        transcript_path.write_text(json.dumps(transcript,indent=2))
    if not transcript:raise ValueError('No usable spoken instructions')
    frames=media['frames']
    if not frames:raise ValueError('No video frames')
    raw=await vision.learn_tutorial(objective=objective,duration=media['duration'],transcript=transcript,
                                  frames=frames,images=[(folder/f['image']).read_bytes() for f in frames])
    result=validate_plan(raw,media['duration'])
    result['source_sha256']=media['source_sha256']
    (folder/'plan.json').write_text(json.dumps(result,indent=2))
    return result


def validate_action(value: dict, *, save_target: Path | None = None) -> dict:
    if not isinstance(value,dict):raise ValueError('Invalid action')
    save_text=set()
    if save_target is not None:
        if not save_target.is_absolute() or save_target.suffix!='.blend':raise ValueError('Invalid save target')
        save_text={str(save_target.parent)+'/',save_target.name}
    keys=KEYS | ({'ctrl+shift+s','ctrl+a'} if save_target else set())
    kind=value.get('action')
    if kind not in {'click','double_click','right_click','set_number','set_text','key','type','wait','done','blocked'}:raise ValueError('Action not allowed')
    if kind in {'click','double_click','right_click','set_number','set_text'}:
        for key in ('x','y'):
            if type(value.get(key)) is not int or not 0<=value[key]<=1000:raise ValueError('Invalid normalized coordinate')
        if kind=='set_text' and (not save_target or value.get('text') not in save_text):raise ValueError('Only the fixed save destination may be edited')
        if kind=='set_number':
            text=value.get('text','')
            if not isinstance(text,str) or not re.fullmatch(r'\d+(?:\.\d+)?',text) or not 0<=float(text)<=1000:raise ValueError('Invalid numeric replacement')
    elif kind=='key':
        if value.get('text') not in keys:raise ValueError('Shortcut not allowed')
    elif kind=='type':
        text=value.get('text','')
        if isinstance(text,str) and text in save_text:return value
        if not isinstance(text,str) or not re.fullmatch(r'[A-Za-z0-9 ._\-]{1,100}',text):raise ValueError('Unsafe text')
        allowed={'bevel','add bevel modifier','shade auto smooth','shade smooth by angle','shade smooth','shade flat'}
        if text.casefold() not in allowed and not re.fullmatch(r'-?\d+(?:\.\d+)?(?: m)?',text):raise ValueError('Only reviewed Blender operations or numeric parameters may be typed')
    return value
