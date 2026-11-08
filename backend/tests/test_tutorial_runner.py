import asyncio
import pytest
from app.engines.tutorial_runner import execute_plan, youtube_url


@pytest.mark.parametrize('url',['http://127.0.0.1/','https://youtube.com.evil.org/watch?v=l12k19-imCY','https://youtube.com/@person','file:///etc/passwd','https://www.youtube.com/watch?v=l12k19-imCY&list=anything'])
def test_import_accepts_only_single_public_youtube_video(url):
    with pytest.raises(ValueError):youtube_url(url)


def test_import_canonicalizes_valid_youtube_links():
    assert youtube_url('https://youtu.be/l12k19-imCY')=='https://www.youtube.com/watch?v=l12k19-imCY'


def test_stop_during_model_wait_prevents_input(tmp_path):
    stopped=False
    class Driver:
        def capture(self,path):path.write_bytes(b'fixture');return path
        def perform(self,action):raise AssertionError('Input after Stop')
    class Vision:
        async def tutorial_action(self,**kw):
            nonlocal stopped
            stopped=True
            return {'action':'click','x':500,'y':500}
    result=asyncio.run(execute_plan({'steps':[{'id':'s1'}]},tmp_path,Driver(),Vision(),lambda:stopped))
    assert result['status']=='stopped'
    assert result['events']==[]


def test_model_done_does_not_mean_independently_verified(tmp_path):
    class Driver:
        def capture(self,path):path.write_bytes(b'fixture');return path
    class Vision:
        async def tutorial_action(self,**kw):return {'action':'done','reason':'Visible bevel'}
    result=asyncio.run(execute_plan({'steps':[{'id':'s1'}]},tmp_path,Driver(),Vision(),lambda:False))
    assert result['status']=='observed_complete'
    assert result['verification']=='not_independently_verified'


def test_locked_driver_becomes_explicit_pause_without_input(tmp_path):
    class Driver:
        def capture(self,path):raise RuntimeError('Mac is locked')
    result=asyncio.run(execute_plan({'steps':[{'id':'s1'}]},tmp_path,Driver(),None,lambda:False))
    assert result['status']=='paused'
    assert 'locked' in result['reason']


def test_repeated_same_action_is_blocked_before_third_input(tmp_path):
    inputs=[]
    class Driver:
        def capture(self,path):path.write_bytes(b'unchanged fixture');return path
        def perform(self,action):inputs.append(action)
    class Vision:
        async def tutorial_action(self,**kw):return {'action':'click','x':833,'y':541}
    result=asyncio.run(execute_plan({'steps':[{'id':'s1'}]},tmp_path,Driver(),Vision(),lambda:False))
    assert result['status']=='blocked'
    assert 'Repeated' in result['reason']
    assert len(inputs)==2
    assert all(event['capture_changed'] is False for event in result['events'])
