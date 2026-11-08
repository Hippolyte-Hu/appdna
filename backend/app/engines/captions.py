"""Validate timestamped narration; captions are source claims, never proof."""
import json
import math
from pathlib import Path

MAX_CAPTION_BYTES=2*1024*1024


def read_captions(path: Path, duration: float | None=None) -> list[dict]:
    if path.stat().st_size>MAX_CAPTION_BYTES:
        raise ValueError('Transcript exceeds 2 MB')
    try:
        value=json.loads(path.read_text(encoding='utf-8'))
    except (ValueError,UnicodeError) as exc:
        raise ValueError('Transcript must be timestamped JSON or YouTube JSON3') from exc
    if isinstance(value,dict) and isinstance(value.get('events'),list):
        try:
            value=[{'start':event['tStartMs']/1000,
                    'end':(event['tStartMs']+event['dDurationMs'])/1000,
                    'text':''.join(s['utf8'] for s in event['segs']).strip()}
                   for event in value['events'] if event.get('segs') and event.get('dDurationMs')]
        except (KeyError,TypeError) as exc:
            raise ValueError('Invalid YouTube caption event') from exc
    return validate_transcript(value,duration)


def validate_transcript(value, duration: float | None=None) -> list[dict]:
    if not isinstance(value,list) or not 1<=len(value)<=10000:
        raise ValueError('Transcript needs 1–10000 timestamped segments')
    result=[]
    for item in value:
        if not isinstance(item,dict):raise ValueError('Invalid transcript segment')
        start,end=item.get('start'),item.get('end')
        if any(type(n) not in (int,float) or not math.isfinite(n) for n in (start,end)) or not 0<=start<end:
            raise ValueError('Transcript timestamps must be finite, positive ordered intervals')
        if duration is not None and (start>=duration or end>duration+2):
            raise ValueError('Transcript timestamps exceed this video')
        text=item.get('text')
        if not isinstance(text,str) or not text.strip() or len(text)>10000:
            raise ValueError('Transcript segments need bounded, nonempty text')
        result.append({'start':start,'end':min(end,duration) if duration is not None else end,'text':text.strip()})
    return result
