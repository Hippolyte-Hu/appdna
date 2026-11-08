"""Synthetic API fixtures: reuse is not another learning or execution claim."""
import hashlib
import json
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from app import tutorial_app as module


def checked_source(tmp_path):
    source_id='b'*32;p=tmp_path/source_id;p.mkdir()
    video=b'Synthetic unit fixture; never decoded or executed';(p/'source.mp4').write_bytes(video)
    (p/'agent_frames').mkdir();Image.new('RGB',(8,8)).save(p/'agent_frames/f.jpg')
    knowledge={'status':'source_checked','source_file':'source.mp4','source_sha256':hashlib.sha256(video).hexdigest(),
        'title':'Test source','objective':'Test objective','steps':[{'id':'one','instruction':'Test step'}],
        'evidence':[{'id':'frame-1','image':'agent_frames/f.jpg'}]}
    for name,data in {'job.json':{'id':source_id,'status':'blocked','error':'Old run failed'},'knowledge.json':knowledge,
        'plan.json':{'source_sha256':knowledge['source_sha256'],'steps':knowledge['steps']},
        'manifest.json':{'duration':10,'frames':[],'audio_path':'/not/copied/audio.wav'},
        'agent.json':{'model':'holo4-27b','status':'source_checked','events':[]},'transcript.json':[]}.items():
        (p/name).write_text(json.dumps(data))
    (p/'run').mkdir();(p/'run/replica.blend').write_bytes(b'Old test artifact; must not be copied')
    return source_id,p


def test_reuse_copies_knowledge_not_runs_or_approvals(tmp_path,monkeypatch):
    source_id,source=checked_source(tmp_path);before=(source/'job.json').read_bytes()
    monkeypatch.setattr(module,'DATA',tmp_path)
    def forbidden(*args,**kwargs):pytest.fail('Reuse must not invoke learning, provider or GUI tools')
    for name in ['providers','spawn','guard']:monkeypatch.setattr(module,name,forbidden)
    c=TestClient(module.app);response=c.post(f'/api/video-sources/{source_id}/executions')
    assert response.status_code==200,response.text
    job=response.json();new=tmp_path/job['id']
    assert job['id']!=source_id and job['source_job_id']==source_id
    assert job['kind']=='video_source_execution' and job['status']=='ready_for_review'
    for name in ['source.mp4','knowledge.json','plan.json','transcript.json','agent_frames/f.jpg']:
        assert (source/name).read_bytes()==(new/name).read_bytes()
    assert not (new/'run').exists() and not job.get('reviewed') and not job.get('confirm_scratch')
    assert (source/'job.json').read_bytes()==before
    sources=c.get('/api/video-sources').json()['items']
    assert [item['id'] for item in sources]==[source_id]
    assert c.post(f'/api/tutorials/{job["id"]}/run',json={}).status_code==400


@pytest.mark.parametrize('damage',['unchecked','changed_video','changed_plan','missing_frame','traversal','invalid_targets'])
def test_reuse_rejects_damaged_source_without_creating_job(tmp_path,monkeypatch,damage):
    source_id,p=checked_source(tmp_path);monkeypatch.setattr(module,'DATA',tmp_path)
    knowledge=json.loads((p/'knowledge.json').read_text())
    if damage=='unchecked':knowledge['status']='needs_input'
    elif damage=='changed_video':(p/'source.mp4').write_bytes(b'changed')
    elif damage=='changed_plan':(p/'plan.json').write_text(json.dumps({'steps':[]}))
    elif damage=='missing_frame':(p/'agent_frames/f.jpg').unlink()
    elif damage=='traversal':knowledge['evidence'][0]['image']='../outside.jpg'
    elif damage=='invalid_targets':(p/'artifact-expectations.json').write_text('{}')
    (p/'knowledge.json').write_text(json.dumps(knowledge))
    response=TestClient(module.app).post(f'/api/video-sources/{source_id}/executions')
    assert response.status_code==409,response.text
    assert [f.name for f in tmp_path.iterdir()]==[source_id]


def test_concurrent_approvals_cannot_launch_two_desktop_executors(tmp_path,monkeypatch):
    import asyncio
    from threading import Barrier
    from fastapi import HTTPException
    source_id,_=checked_source(tmp_path)
    monkeypatch.setattr(module,'DATA',tmp_path)
    monkeypatch.setattr(module,'active',None)
    first=module.reuse_source(source_id)['id']
    second=module.reuse_source(source_id)['id']
    barrier=Barrier(2)
    def unlocked(_):
        barrier.wait(timeout=5)
        return {'locked':False}
    monkeypatch.setattr(module,'guard',unlocked)
    # Close the coroutine: this regression must never open a real app.
    monkeypatch.setattr(module,'spawn',lambda coro:coro.close())
    async def approve(job_id):
        try:
            await module.run(job_id,module.Approval(reviewed=True,confirm_scratch=True))
            return 200
        except HTTPException as exc:
            return exc.status_code
    async def together():
        return await asyncio.gather(approve(first),approve(second))
    assert sorted(asyncio.run(together()))==[200,409]
