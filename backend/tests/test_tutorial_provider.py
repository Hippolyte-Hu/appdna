import asyncio
import io
import pytest
from PIL import Image
from app.providers.hcompany import HCompanyProvider
from app.providers.base import ProviderError


def image_bytes():
    stream=io.BytesIO();Image.new('RGB',(40,40),'gray').save(stream,format='PNG');return stream.getvalue()


def test_vision_retries_one_server_failure(monkeypatch):
    provider=HCompanyProvider('unit-test-key','https://unit.invalid','unit-test-model');calls=[]
    async def post(body,timeout):
        calls.append(body)
        if len(calls)==1:raise ProviderError('test server error',status=500)
        return '{"action":"done","x":0,"y":0,"text":"","reason":"test fixture"}'
    monkeypatch.setattr(provider,'_post',post)
    result=asyncio.run(provider.tutorial_action(step={'id':'test','expected':'fixture'},image_bytes=image_bytes(),history=[]))
    assert result['action']=='done' and len(calls)==2


def test_authorization_error_is_not_retried(monkeypatch):
    provider=HCompanyProvider('unit-test-key','https://unit.invalid','unit-test-model');calls=[]
    async def post(body,timeout):
        calls.append(body);raise ProviderError('test auth failure',status=401)
    monkeypatch.setattr(provider,'_post',post)
    with pytest.raises(ProviderError):asyncio.run(provider.tutorial_action(step={'id':'test'},image_bytes=image_bytes(),history=[]))
    assert len(calls)==1


@pytest.mark.parametrize('step',[{'id':'normal'},{'id':'save','save_target':'/unit/replica.blend'}])
def test_desktop_inference_allows_a_bounded_slow_response(monkeypatch,step):
    provider=HCompanyProvider('unit-test-key','https://unit.invalid','unit-test-model');timeouts=[]
    async def post(body,timeout):
        timeouts.append(timeout)
        if timeout<60:raise ProviderError('H Company took too long to answer')
        return '{"action":"done","x":0,"y":0,"text":"","reason":"unit save fixture"}'
    monkeypatch.setattr(provider,'_post',post)
    result=asyncio.run(provider.tutorial_action(step=step,
                                              image_bytes=image_bytes(),history=[]))
    assert result['action']=='done' and len(timeouts)==1
    assert 60<=timeouts[0]<=120
