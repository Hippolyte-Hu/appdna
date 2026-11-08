import asyncio
import io
import pytest
from PIL import Image
from app.providers.hcompany import HCompanyProvider


def image_bytes():
    stream=io.BytesIO()
    Image.new('RGB',(40,40),'gray').save(stream,format='PNG')
    return stream.getvalue()


def test_learning_controller_exposes_only_source_tools(monkeypatch):
    provider=HCompanyProvider('unit-test-key','https://unit.invalid','unit-test-model');requests=[]
    async def look(prompt,images,schema,name,**kw):
        requests.append((prompt,images,schema));return {'action':'needs_input','reason':'unit fixture'}
    monkeypatch.setattr(provider,'_look',look)
    result=asyncio.run(provider.video_learning_turn(objective='Follow source',duration=10,
        available_frames=[0,5],history=[],budget={'decisions_left':3,'frames_left':4}))
    assert result['action']=='needs_input'
    prompt,images,schema=requests[0]
    assert not images and '0.22' not in prompt and '0.24' not in prompt
    assert set(schema['properties']['action']['enum'])=={'read_transcript','inspect_frames','submit_plan','needs_input'}


def test_source_check_reads_original_images_not_previous_model_observations(monkeypatch):
    provider=HCompanyProvider('unit-test-key','https://unit.invalid','unit-test-model');requests=[]
    async def look(prompt,images,schema,name,**kw):
        requests.append((prompt,images));return {'supported':False,'issues':['unit fixture unclear source']}
    monkeypatch.setattr(provider,'_look',look)
    result=asyncio.run(provider.check_video_step(objective='Follow source',step={'instruction':'Set width'},
        frames=[{'id':'frame-1','timestamp':2,'observations':['SHOULD_NOT_BE_TRUSTED']}],images=[image_bytes()],transcript=[]))
    assert not result['supported'] and requests[0][1]
    assert 'SHOULD_NOT_BE_TRUSTED' not in requests[0][0]


def test_source_requests_retry_rate_limit_once_with_cooldown(monkeypatch):
    from app.providers import video_learning as source
    from app.providers.base import ProviderError
    delays=[];calls=[]
    async def sleep(seconds):delays.append(seconds)
    async def look(*args,**kwargs):
        calls.append(True)
        if len(calls)==1:raise ProviderError('Unit rate limit',status=429)
        return {'ok':True}
    class Provider:pass
    provider=Provider();provider._look=look
    monkeypatch.setattr(source.asyncio,'sleep',sleep)
    result=asyncio.run(source.source_request(provider,'prompt',[],{},'unit'))
    assert result['ok'] and len(calls)==2 and max(delays)>=60


@pytest.mark.parametrize('persistent',[False,True])
def test_source_invalid_json_retries_once_with_schema_not_fabricated_data(monkeypatch,persistent):
    from app.providers import video_learning as source
    from app.providers.base import ProviderError
    requests=[]
    async def sleep(seconds):pass
    async def look(prompt,images,schema,name,**kwargs):
        requests.append((prompt,images,schema,kwargs))
        if len(requests)==1 or persistent:raise ProviderError('H Company did not return valid JSON')
        return {'supported':False,'issues':['Source remains unclear']}
    from types import SimpleNamespace
    provider=SimpleNamespace(_look=look)
    monkeypatch.setattr(source.asyncio,'sleep',sleep)
    if persistent:
        with pytest.raises(ProviderError,match='valid JSON'):
            asyncio.run(source.source_request(provider,'original evidence',[image_bytes()],source.CHECK,'unit',max_tokens=1200))
    else:
        result=asyncio.run(source.source_request(provider,'original evidence',[image_bytes()],source.CHECK,'unit',max_tokens=1200))
        assert result['supported'] is False
    assert len(requests)==2
    assert 'original evidence' in requests[1][0] and 'supported' in requests[1][0]
    assert requests[1][1]==requests[0][1] and requests[1][2]==source.CHECK


def test_source_auth_error_is_not_retried(monkeypatch):
    from app.providers import video_learning as source
    from app.providers.base import ProviderError
    calls=[]
    async def look(*args,**kwargs):
        calls.append(True);raise ProviderError('Unit unauthorized',status=401)
    from types import SimpleNamespace
    provider=SimpleNamespace(_look=look)
    with pytest.raises(ProviderError):asyncio.run(source.source_request(provider,'prompt',[],{},'unit'))
    assert len(calls)==1


def test_source_check_normalizes_mixed_frame_sizes_without_changing_citations(monkeypatch):
    provider=HCompanyProvider('unit-test-key','https://unit.invalid','unit-test-model');requests=[]
    small=io.BytesIO();Image.new('RGB',(80,30),'white').save(small,format='PNG')
    originals=[image_bytes(),small.getvalue()]
    async def look(prompt,images,schema,name,**kw):
        requests.append((prompt,images));return {'supported':False,'issues':['Unit source uncertainty']}
    monkeypatch.setattr(provider,'_look',look)
    frames=[{'id':'frame-1','timestamp':1,'crop':[]},{'id':'frame-2','timestamp':2,'crop':[500,300,1000,700]}]
    result=asyncio.run(provider.check_video_step(objective='Follow source',step={'instruction':'Compare before and after'},
        frames=frames,images=originals,transcript=[]))
    sent=requests[0][1]
    assert len({Image.open(io.BytesIO(blob)).size for blob in sent})==1
    assert 'frame-1' in requests[0][0] and 'frame-2' in requests[0][0]
    assert '500' in requests[0][0] and not result['supported']
    assert Image.open(io.BytesIO(originals[0])).size==(40,40)
    assert Image.open(io.BytesIO(originals[1])).size==(80,30)


def test_learning_enables_reasoning_but_source_ocr_does_not(monkeypatch):
    provider=HCompanyProvider('unit','https://unit.invalid','holo4-27b');requests=[]
    async def look(prompt,images,schema,name,**kwargs):
        requests.append((name,kwargs));return {'action':'needs_input','reason':'unit'}
    monkeypatch.setattr(provider,'_look',look)
    asyncio.run(provider.video_learning_turn(objective='Follow source',duration=10,available_frames=[2],history=[],budget={}))
    assert requests[0][1]['reasoning_effort']=='medium'
    assert requests[0][1]['max_tokens']>=8192
    monkeypatch.setattr(provider,'_video_next_request',0,raising=False)
    asyncio.run(provider.inspect_video_frames(objective='Follow source',question='Read text',frames=[],images=[],transcript=[]))
    assert requests[1][1].get('reasoning_effort','none')=='none'


@pytest.mark.parametrize('fallback',[False,True])
def test_hcompany_reasoning_option_reaches_actual_request_and_fallback(monkeypatch,fallback):
    from app.providers.base import ProviderError
    provider=HCompanyProvider('unit','https://unit.invalid','holo4-27b');requests=[]
    async def post(body,**kw):
        requests.append(body)
        if fallback and len(requests)==1:raise ProviderError('Unit schema rejected',status=400)
        return '{"ok":true}'
    monkeypatch.setattr(provider,'_post',post)
    result=asyncio.run(provider._look('Unit source',[],{},'unit',reasoning_effort='medium',max_tokens=8192))
    assert result['ok'] and all(r['reasoning_effort']=='medium' for r in requests)
    assert all(r['max_tokens']==8192 for r in requests)
    asyncio.run(provider._look('Unit desktop',[],{},'unit'))
    assert requests[-1]['reasoning_effort']=='none'


@pytest.mark.parametrize('persistent',[False,True])
def test_source_audit_reasks_contradictory_result_without_dropping_issues(monkeypatch,persistent):
    from app.providers.base import ProviderError
    provider=HCompanyProvider('unit','https://unit.invalid','holo4-27b');requests=[]
    async def look(prompt,images,schema,name,**kwargs):
        requests.append(prompt)
        if len(requests)==1 or persistent:return {'supported':True,'issues':['The step is fully supported.']}
        return {'supported':False,'issues':['Actually the parameter is unreadable.']}
    async def sleep(seconds):pass
    from app.providers import video_learning as source
    monkeypatch.setattr(provider,'_look',look);monkeypatch.setattr(source.asyncio,'sleep',sleep)
    kwargs={'objective':'Follow source','step':{'instruction':'Set parameter'},'frames':[],'images':[],'transcript':[]}
    if persistent:
        with pytest.raises(ProviderError,match='contradictory'):asyncio.run(provider.check_video_step(**kwargs))
    else:
        result=asyncio.run(provider.check_video_step(**kwargs))
        assert not result['supported'] and result['issues']==['Actually the parameter is unreadable.']
    assert len(requests)==2
    assert 'issues=[]' in requests[-1]
