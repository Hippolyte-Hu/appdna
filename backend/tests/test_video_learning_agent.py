"""Deterministic unit doubles only; these are NOT real video-learning receipts."""
import asyncio
import json
from copy import deepcopy
import pytest
from app.agents import video_learning as module


def proposal(value='0.24', citation='frame-1'):
    return {'title':'Unit fixture workflow','objective':'Set a demonstrated width',
            'prerequisites':['Selected object'], 'limitations':['Unit fixture only'],
            'steps':[{'id':'s1','start':1.0,'end':3.0,'instruction':f'Set width to {value} m',
                      'expected':f'Width shows {value} m','uncertainty':'',
                      'evidence_ids':[citation]}]}


def setup(tmp_path, monkeypatch):
    source=tmp_path/'source.mp4'; source.write_bytes(b'unit video fixture')
    media={'duration':10,'source_sha256':'unit-fixture','frames':[{'timestamp':0,'image':'f.jpg'}]}
    reads=[]
    def extract(source, folder, timestamp, crop):
        reads.append((timestamp,crop));path=folder/f'{len(reads)}.jpg';path.parent.mkdir(exist_ok=True)
        path.write_bytes(b'unit frame fixture');return path
    monkeypatch.setattr(module,'extract_frame',extract)
    return source,media,reads


class Model:
    model='unit-double'
    def __init__(self, decisions, audits=None):self.decisions=iter(decisions);self.audits=iter(audits or []);self.contexts=[]
    async def video_learning_turn(self, **kw):
        self.contexts.append(deepcopy(kw));return next(self.decisions)
    async def inspect_video_frames(self, **kw):
        return {'frames':[{'evidence_id':f['id'],'observations':['Width field visible'],
                          'uncertainties':[]} for f in kw['frames']]}
    async def check_video_step(self, **kw):return next(self.audits)


def read():return {'action':'read_transcript','start':0,'end':10,'reason':'Find demonstrated sequence'}
def inspect(t: float=2):return {'action':'inspect_frames','timestamps':[t],'crop':[], 'question':'Read width and active mode','reason':'Check source value'}
def submit(p):return {'action':'submit_plan','plan':p,'reason':'Check proposed knowledge against source'}


def test_agent_revisits_source_after_rejected_parameter_without_human_selection(tmp_path,monkeypatch):
    source,media,reads=setup(tmp_path,monkeypatch)
    model=Model([read(),inspect(),submit(proposal()),inspect(2.5),submit(proposal('0.22','frame-2'))],
                [{'supported':False,'issues':['Proposed value conflicts with source']},
                 {'supported':True,'issues':[]}])
    result=asyncio.run(module.VideoLearningAgent(model).run(media,tmp_path,[{'start':0,'end':3,'text':'Adjust width'}],source=source,objective='Follow source'))
    assert result['status']=='source_checked'
    assert result['verification']=='not_executed'
    assert '0.22' in result['steps'][0]['instruction']
    assert len(reads)==2
    assert 'conflicts' in json.dumps(model.contexts[3])
    trace=json.loads((tmp_path/'agent.json').read_text())
    assert trace['status']=='completed' and len(trace['events'])==5
    assert json.loads((tmp_path/'plan.json').read_text())['steps']==result['steps']
    assert len(result['source_checks'])==1 and result['source_checks'][0]['supported']


def test_fabricated_evidence_never_creates_executable_plan(tmp_path,monkeypatch):
    source,media,_=setup(tmp_path,monkeypatch)
    model=Model([read(),submit(proposal(citation='invented')),{'action':'needs_input','reason':'No inspected frame supports this value'}])
    result=asyncio.run(module.VideoLearningAgent(model).run(media,tmp_path,[],source=source,objective='Follow source'))
    assert result['status']=='needs_input' and not (tmp_path/'plan.json').exists()
    assert 'inspected frame' in result['reason']
    assert 'citation' in json.dumps(model.contexts[-1]).lower()


@pytest.mark.parametrize('timestamps',[[float('nan')],[-1],[11],[True],list(range(5))])
def test_frame_tool_rejects_invalid_times_before_ffmpeg(tmp_path,monkeypatch,timestamps):
    source,media,reads=setup(tmp_path,monkeypatch)
    model=Model([{'action':'inspect_frames','timestamps':timestamps,'crop':[],'question':'Read visible data'},
                 {'action':'needs_input','reason':'Invalid request'}])
    result=asyncio.run(module.VideoLearningAgent(model).run(media,tmp_path,[],source=source,objective='Follow source'))
    assert result['status']=='needs_input' and not reads


def test_budget_exhaustion_stops_without_silent_success(tmp_path,monkeypatch):
    source,media,reads=setup(tmp_path,monkeypatch)
    model=Model([inspect(),inspect(3),inspect(4)])
    result=asyncio.run(module.VideoLearningAgent(model,max_turns=2).run(media,tmp_path,[],source=source,objective='Follow source'))
    assert result['status']=='needs_input' and len(reads)==2
    assert not (tmp_path/'plan.json').exists()


def test_instance_context_is_not_shared_across_sources(tmp_path,monkeypatch):
    source,media,_=setup(tmp_path,monkeypatch)
    model=Model([{'action':'needs_input','reason':'Source is unclear'}]*2)
    agent=module.VideoLearningAgent(model)
    for name in ['one','two']:
        folder=tmp_path/name;folder.mkdir()
        asyncio.run(agent.run(media,folder,[],source=source,objective=name))
    assert model.contexts[1]['history']==[]
    assert model.contexts[0]['objective']=='one' and model.contexts[1]['objective']=='two'


def test_model_transport_failure_is_persisted_not_verified(tmp_path,monkeypatch):
    source,media,_=setup(tmp_path,monkeypatch)
    class Broken:
        model='unit-double'
        async def video_learning_turn(self,**kw):raise RuntimeError('Unit transport failure')
    result=asyncio.run(module.VideoLearningAgent(Broken()).run(media,tmp_path,[],source=source,objective='Follow source'))
    assert result['status']=='blocked'
    assert json.loads((tmp_path/'agent.json').read_text())['status']=='blocked'
    assert not (tmp_path/'plan.json').exists()


def test_out_of_interval_citation_is_rejected_without_model_audit(tmp_path,monkeypatch):
    source,media,_=setup(tmp_path,monkeypatch)
    model=Model([read(),inspect(7),submit(proposal()),{'action':'needs_input','reason':'Need matching evidence'}])
    result=asyncio.run(module.VideoLearningAgent(model).run(media,tmp_path,[],source=source,objective='Follow source'))
    assert result['status']=='needs_input'
    assert 'interval' in json.dumps(model.contexts[-1])
    feedback=model.contexts[-1]['history'][-1]['result']['error']
    assert 's1' in feedback and '7' in feedback
    assert not (tmp_path/'plan.json').exists()


def test_source_only_agent_rejects_desktop_tool_and_honors_stop(tmp_path,monkeypatch):
    source,media,_=setup(tmp_path,monkeypatch)
    model=Model([{'action':'click','x':1,'y':2}, {'action':'needs_input','reason':'No desktop tool'}])
    result=asyncio.run(module.VideoLearningAgent(model).run(media,tmp_path,[],source=source,objective='Follow source'))
    assert result['status']=='needs_input' and 'not allowed' in json.dumps(model.contexts[-1])
    folder=tmp_path/'stopped';folder.mkdir()
    result=asyncio.run(module.VideoLearningAgent(model).run(media,folder,[],source=source,objective='Follow source',should_stop=lambda:True))
    assert result['status']=='stopped'


def test_model_cannot_override_source_provenance_or_verification(tmp_path,monkeypatch):
    source,media,_=setup(tmp_path,monkeypatch)
    plan=proposal();plan.update(source_url='https://untrusted.invalid',source_sha256='forged',source_type='document',verification='verified')
    model=Model([read(),inspect(),submit(plan)],[{'supported':True,'issues':[]}])
    result=asyncio.run(module.VideoLearningAgent(model).run(media,tmp_path,[],source=source,objective='Follow source'))
    assert result['source_type']=='video' and result['source_url'] is None
    assert result['source_sha256']=='unit-fixture' and result['verification']=='not_executed'


def test_plan_with_unresolved_uncertainty_does_not_pass(tmp_path,monkeypatch):
    source,media,_=setup(tmp_path,monkeypatch)
    plan=proposal();plan['steps'][0]['uncertainty']='Width may be unreadable'
    model=Model([read(),inspect(),submit(plan),{'action':'needs_input','reason':'Width is unclear'}],[{'supported':True,'issues':[]}])
    result=asyncio.run(module.VideoLearningAgent(model).run(media,tmp_path,[],source=source,objective='Follow source'))
    assert result['status']=='needs_input' and not (tmp_path/'plan.json').exists()


def test_repeated_rejected_proposal_stops_before_reissuing_tool(tmp_path,monkeypatch):
    source,media,_=setup(tmp_path,monkeypatch)
    bad=proposal(citation='invented')
    model=Model([read(),submit(bad),submit(bad),submit(bad)])
    result=asyncio.run(module.VideoLearningAgent(model).run(media,tmp_path,[],source=source,objective='Follow source'))
    assert result['status']=='needs_input' and 'Repeated' in result['reason']


def test_all_step_citation_errors_return_in_one_tool_result(tmp_path,monkeypatch):
    source,media,_=setup(tmp_path,monkeypatch)
    plan=proposal();second=deepcopy(plan['steps'][0]);second['id']='s2';plan['steps'].append(second)
    model=Model([read(),inspect(7),submit(plan),{'action':'needs_input','reason':'Need better evidence'}])
    result=asyncio.run(module.VideoLearningAgent(model).run(media,tmp_path,[],source=source,objective='Follow source'))
    feedback=model.contexts[-1]['history'][-1]['result']['error']
    assert 's1' in feedback and 's2' in feedback and '7' in feedback
    assert result['status']=='needs_input' and not (tmp_path/'plan.json').exists()


def test_transient_audit_failure_resumes_with_completed_checks_cached(tmp_path,monkeypatch):
    from app.providers.base import ProviderError
    source,media,_=setup(tmp_path,monkeypatch)
    plan=proposal();second=deepcopy(plan['steps'][0]);second['id']='s2';plan['steps'].append(second)
    class Flaky(Model):
        def __init__(self):
            super().__init__([read(),inspect(),submit(plan),submit(plan)]);self.calls=[]
        async def check_video_step(self,**kw):
            self.calls.append(kw['step']['id'])
            if len(self.calls)==2:raise ProviderError('Unit source timeout')
            return {'supported':True,'issues':[]}
    model=Flaky()
    result=asyncio.run(module.VideoLearningAgent(model).run(media,tmp_path,[],source=source,objective='Follow source'))
    assert result['status']=='source_checked'
    assert model.calls==['s1','s2','s2']
    trace=json.loads((tmp_path/'agent.json').read_text())
    assert trace['events'][2]['source_checks'][0]['step_id']=='s1'
    assert trace['events'][2]['result']['retryable'] is True
    assert len(result['source_checks'])==2


def test_persistent_source_tool_failure_is_bounded_and_never_accepted(tmp_path,monkeypatch):
    from app.providers.base import ProviderError
    source,media,_=setup(tmp_path,monkeypatch)
    class BrokenAudit(Model):
        async def check_video_step(self,**kw):raise ProviderError('Unit persistent source timeout')
    model=BrokenAudit([read(),inspect(),submit(proposal()),submit(proposal())])
    result=asyncio.run(module.VideoLearningAgent(model).run(media,tmp_path,[],source=source,objective='Follow source'))
    assert result['status']=='blocked' and 'Repeated source-tool' in result['reason']
    assert not (tmp_path/'plan.json').exists()
