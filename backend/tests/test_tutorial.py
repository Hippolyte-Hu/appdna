import asyncio
import pytest
from app.engines.tutorial import validate_plan, learn_tutorial, validate_action


def plan():
    return {'title':'Round cube','objective':'Add a bevel modifier','prerequisites':['Default cube selected'],
            'steps':[{'id':'s1','start':3.0,'end':8.0,'instruction':'Open modifiers','expected':'Modifier properties visible','uncertainty':''}],
            'limitations':['Not yet executed']}


def test_plan_preserves_timed_steps_and_marks_unexecuted():
    result=validate_plan(plan(),20)
    assert result['steps'][0]['start']==3
    assert result['status']=='ready_for_review'
    assert result['verification']=='not_executed'


@pytest.mark.parametrize('start,end',[(9,8),(-1,3),(0,21),(float('nan'),3)])
def test_rejects_ungrounded_timestamps(start,end):
    p=plan();p['steps'][0].update(start=start,end=end)
    with pytest.raises(ValueError):validate_plan(p,20)


def test_rejects_duplicate_steps_and_empty_expectations():
    p=plan();p['steps']*=2
    with pytest.raises(ValueError):validate_plan(p,20)
    p=plan();p['steps'][0]['expected']=''
    with pytest.raises(ValueError):validate_plan(p,20)


def test_audio_and_ordered_images_are_used_and_result_persisted(tmp_path):
    (tmp_path/'audio.wav').write_bytes(b'test-only audio')
    (tmp_path/'f.jpg').write_bytes(b'test-only image')
    media={'duration':20,'has_video':True,'has_audio':True,'audio_path':str(tmp_path/'audio.wav'),
           'source_sha256':'test-fixture','frames':[{'timestamp':0,'image':'f.jpg'}]}
    class ASR:
        async def transcribe_file(self,path):return [{'start':0,'end':8,'text':'Open modifiers'}]
    class Vision:
        async def learn_tutorial(self,**kw):
            assert kw['frames'][0]['timestamp']==0
            assert kw['images']==[b'test-only image']
            assert kw['transcript'][0]['text']=='Open modifiers'
            return plan()
    result=asyncio.run(learn_tutorial(media,tmp_path,ASR(),Vision(),objective='Follow the first workflow'))
    assert result['verification']=='not_executed'
    assert (tmp_path/'plan.json').is_file()
    assert (tmp_path/'transcript.json').is_file()


@pytest.mark.parametrize('action',[
    {'action':'click','x':1001,'y':20}, {'action':'type','text':'import bpy'},
    {'action':'key','text':'cmd+q'}, {'action':'shell','text':'anything'},
    {'action':'type','text':'/etc/passwd'}, {'action':'click','x':False,'y':20},
    {'action':'type','text':'Save Startup File'}, {'action':'type','text':'Save Preferences'},
    {'action':'key','text':'x'},
])
def test_execution_rejects_unsafe_actions(action):
    with pytest.raises(ValueError):validate_action(action)


def test_execution_accepts_bounded_mouse_and_blender_keys():
    assert validate_action({'action':'click','x':500,'y':300})['x']==500
    assert validate_action({'action':'key','text':'f3'})['text']=='f3'
