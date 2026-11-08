"""Source-only Agent: private context, bounded tools, no desktop/shell access."""
import asyncio
import json
import math
from pathlib import Path
from PIL import Image
from app.engines.media import _run
from app.engines.tutorial import validate_plan
from app.providers.base import ProviderError


def write_json(path, value):
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value,indent=2,allow_nan=False),encoding='utf-8')
    temporary.replace(path)


def extract_frame(source: Path, folder: Path, timestamp: float, crop: list) -> Path:
    folder.mkdir(parents=True,exist_ok=True)
    path=folder/f'view-{len(list(folder.glob("view-*.jpg")))+1:03d}.jpg'
    _run(['ffmpeg','-v','error','-y','-protocol_whitelist','file,pipe','-ss',str(timestamp),
          '-i',str(source),'-frames:v','1','-vf','scale=1920:-2','-q:v','2',str(path)])
    if not path.is_file():raise ValueError('Requested video frame was not produced')
    if crop:
        with Image.open(path) as image:
            box=tuple(round(v*(image.width if i%2==0 else image.height)/1000) for i,v in enumerate(crop))
            image.crop(box).save(path,quality=94)
    return path


def valid_time(value, duration, *, inclusive=False):
    return type(value) in (int,float) and math.isfinite(value) and 0<=value and (value<=duration if inclusive else value<duration)


class VideoLearningAgent:
    """One invocable Agent; all memory/receipts are local to a run, not global."""
    def __init__(self, vision, *, max_turns=20, max_frames=48):
        self.vision=vision
        self.max_turns=max_turns
        self.max_frames=max_frames

    async def run(self, media, folder, transcript, *, source, objective, source_url=None, should_stop=lambda:False):
        folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
        if (folder/'agent.json').exists() or (folder/'plan.json').exists():
            raise ValueError('Use a fresh learning folder; existing evidence is immutable')
        if not source.is_file():raise ValueError('Video source is missing')
        duration=media['duration']
        if not valid_time(duration,600,inclusive=True) or duration==0:raise ValueError('Invalid source duration')
        history=[];evidence={};transcript_read=False;rejected_decisions={};check_cache={};tool_failures={}
        trace={'role':'video_learning','model':getattr(self.vision,'model','unknown'),'status':'running','events':[]}
        knowledge={'source_type':'video','source_sha256':media['source_sha256'],'source_file':source.name,
                   'source_url':source_url,'objective':objective,'verification':'not_executed',
                   'status':'learning','steps':[],'limitations':['Video/model observations are not independent artifact verification.']}

        def persist():
            write_json(folder/'agent.json',trace)
            write_json(folder/'knowledge.json',knowledge)

        def terminate(status,reason):
            trace['status']='completed' if status=='source_checked' else status
            knowledge.update(status=status,reason=reason,evidence=list(evidence.values()))
            persist()
            return knowledge

        persist()
        try:
            for turn in range(self.max_turns):
                if should_stop():return terminate('stopped','Learning stopped by caller')
                decision=await self.vision.video_learning_turn(
                    objective=objective,duration=duration,
                    available_frames=[f['timestamp'] for f in media.get('frames',[])],
                    history=history,budget={'decisions_left':self.max_turns-turn,'frames_left':self.max_frames-len(evidence)})
                if not isinstance(decision,dict):raise ValueError('Invalid Agent response')
                action=decision.get('action')
                event={'turn':turn+1,'action':action,'reason':str(decision.get('reason',''))[:1000]}
                # Keep tool arguments, not hidden reasoning. Invalid non-finite data
                # is rejected by the tool and must not poison JSON persistence.
                try:
                    json.dumps(decision,allow_nan=False)
                    event['request']={k:v for k,v in decision.items() if k!='reason'}
                except (TypeError,ValueError):
                    event['request']={'action':action}
                trace['events'].append(event)
                try:
                    if action=='read_transcript':
                        start,end=decision.get('start'),decision.get('end')
                        if type(start) not in (int,float) or type(end) not in (int,float) or not valid_time(start,duration) or not valid_time(end,duration,inclusive=True) or not start<end or end-start>120:
                            raise ValueError('Transcript interval must be within source and at most 120 seconds')
                        result={'segments':[s for s in transcript if s['end']>=start and s['start']<=end], 'start':start,'end':end}
                        transcript_read=True
                    elif action=='inspect_frames':
                        times=decision.get('timestamps');crop=decision.get('crop') or []
                        if not isinstance(times,list) or not 1<=len(times)<=4 or any(not valid_time(t,duration) for t in times):
                            raise ValueError('Request 1–4 finite timestamps within the video')
                        if len(evidence)+len(times)>self.max_frames:raise ValueError('Frame budget exhausted')
                        if crop and (not isinstance(crop,list) or len(crop)!=4 or any(type(v) is not int or not 0<=v<=1000 for v in crop)
                                     or crop[2]-crop[0]<20 or crop[3]-crop[1]<20):
                            raise ValueError('Crop must be [left,top,right,bottom] on the 0–1000 grid, minimum 20 units wide/high')
                        question=decision.get('question')
                        if not isinstance(question,str) or not 1<=len(question)<=2000:raise ValueError('A bounded source question is required')
                        frames=[];images=[]
                        for t in times:
                            path=await asyncio.to_thread(extract_frame,source,folder/'agent_frames',t,crop)
                            frame={'id':f'frame-{len(evidence)+1}','timestamp':t,'crop':crop,'image':str(path.relative_to(folder))}
                            evidence[frame['id']]=frame
                            frames.append(frame);images.append(path.read_bytes())
                        nearby=[s for s in transcript if any(s['end']>=t-5 and s['start']<=t+5 for t in times)]
                        observed=await self.vision.inspect_video_frames(objective=objective,question=question,frames=frames,images=images,transcript=nearby)
                        items=observed.get('frames',[])
                        if len(items)!=len(frames) or {i.get('evidence_id') for i in items}!={f['id'] for f in frames}:
                            raise ValueError('Frame observations must match exact requested evidence IDs')
                        for item in items:
                            for key in ('observations','uncertainties'):
                                if not isinstance(item.get(key),list) or any(not isinstance(x,str) for x in item[key]):
                                    raise ValueError('Invalid frame observation')
                            evidence[item['evidence_id']].update(observations=item['observations'],uncertainties=item['uncertainties'])
                        result={'evidence':[evidence[f['id']] for f in frames]}
                    elif action=='submit_plan':
                        if not transcript_read:raise ValueError('Read the transcript before submitting knowledge')
                        proposal=decision.get('plan')
                        if not isinstance(proposal,dict):raise ValueError('A plan object is required')
                        plan=validate_plan({k:proposal[k] for k in ('title','objective','prerequisites','steps','limitations') if k in proposal},duration)
                        errors=[]
                        for step in plan['steps']:
                            if step['uncertainty'].strip().casefold() not in {'','none'}:
                                errors.append(f"Step {step['id']}: resolve uncertainty or return needs_input")
                            ids=step.get('evidence_ids')
                            if not isinstance(ids,list) or not 1<=len(ids)<=4 or any(not isinstance(i,str) or i not in evidence or 'observations' not in evidence[i] for i in ids):
                                errors.append(f"Step {step['id']}: needs 1–4 real inspected frame citations")
                                continue
                            if step['end']-step['start']>120 or any(not step['start']<=evidence[i]['timestamp']<=step['end'] for i in ids):
                                cited_times={i:evidence[i]['timestamp'] for i in ids}
                                errors.append(f"Step {step['id']} interval [{step['start']}, {step['end']}] must contain citations {cited_times} and span at most 120 seconds")
                        if errors:
                            raise ValueError('Fix ALL source validation issues before resubmitting. Inspect better evidence if needed; do not invent support. '+ '; '.join(errors))
                        checks=[];event['source_checks']=checks
                        for step in plan['steps']:
                            if should_stop():return terminate('stopped','Learning stopped by caller')
                            event['checking_step']=step['id'];persist()
                            cited=[evidence[i] for i in step['evidence_ids']]
                            nearby=[s for s in transcript if s['end']>=step['start']-5 and s['start']<=step['end']+5]
                            # Cache is private to THIS run and exact step/citations.
                            # New evidence or revised instructions trigger a new audit.
                            key=json.dumps(step,sort_keys=True)
                            check=check_cache.get(key)
                            if check is None:
                                check=await self.vision.check_video_step(objective=objective,step=step,frames=cited,
                                    images=[(folder/f['image']).read_bytes() for f in cited],transcript=nearby)
                                if type(check.get('supported')) is not bool or not isinstance(check.get('issues'),list) or any(not isinstance(i,str) for i in check['issues']):
                                    raise ValueError('Invalid source-check response')
                                check_cache[key]=check
                            checks.append({'step_id':step['id'],**check});persist()
                        supported=all(c['supported'] and not c['issues'] for c in checks)
                        result={'accepted':supported,'source_checks':checks}
                        if supported:
                            plan['source_sha256']=media['source_sha256']
                            knowledge.update({k:plan[k] for k in ('title','objective','prerequisites','steps','limitations')})
                            knowledge['source_checks']=checks
                            event['result']=result
                            write_json(folder/'plan.json',plan)
                            return terminate('source_checked','All proposed steps passed model source checks; not executed')
                    elif action=='needs_input':
                        return terminate('needs_input',event['reason'] or 'Source ambiguity needs clarification')
                    else:raise ValueError('Tool not allowed; no desktop, network, code or shell tool is available')
                except ProviderError as exc:
                    if exc.status is not None and exc.status!=429 and exc.status<500:raise
                    signature=json.dumps(event['request'],sort_keys=True,ensure_ascii=False)
                    tool_failures[signature]=tool_failures.get(signature,0)+1
                    result={'error':str(exc)[:400],'retryable':True,
                            'completed_source_checks':event.get('source_checks',[]),
                            'guidance':'Transient source-tool failure. Retry the same proposal once; completed exact-step audits are retained in this run.'}
                    if tool_failures[signature]>=2:
                        event['result']=result;persist()
                        return terminate('blocked','Repeated source-tool provider failure: '+str(exc)[:300])
                except ValueError as exc:
                    result={'error':str(exc)}
                    signature=json.dumps({'action':action,'request':event['request']},sort_keys=True,ensure_ascii=False)
                    rejected_decisions[signature]=rejected_decisions.get(signature,0)+1
                    if rejected_decisions[signature]>=2:
                        event['result']=result
                        persist()
                        return terminate('needs_input','Repeated rejected source-tool request; revise evidence or ask for clarification')
                event['result']=result
                history.append({'action':action,'request':event['request'],'result':result})
                persist()
            return terminate('needs_input','Decision budget exhausted; no executable plan accepted')
        except Exception as exc:
            return terminate('blocked',str(exc)[:400])


async def learn_video_source(media, folder, asr, vision, *, source, objective, source_url=None, should_stop=lambda:False):
    if not media.get('has_video') or not media.get('has_audio'):raise ValueError('Tutorial needs video and spoken audio')
    transcript_path=folder/'transcript.json'
    if transcript_path.exists():transcript=json.loads(transcript_path.read_text())
    else:
        transcript=await asr.transcribe_file(Path(media['audio_path']))
        write_json(transcript_path,transcript)
    if not transcript:raise ValueError('No usable spoken instructions')
    return await VideoLearningAgent(vision).run(media,folder,transcript,source=source,objective=objective,
        source_url=source_url,should_stop=should_stop)
