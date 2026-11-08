"""Typed synthetic fixtures; real Holo4/Blender evidence is separate."""
import asyncio
import copy
import hashlib
import json
import pytest
from app.engines import tutorial_expectations as module


def values():
    return dict(shape='cube',width=.24,segments=4,affect='VERTICES',width_type='OFFSET',
                limit_method='ANGLE',angle_limit_degrees=30,smooth_shading=True,smooth_by_angle=True)


def source(tmp_path):
    (tmp_path/'source.mp4').write_bytes(b'explicit unit video')
    from PIL import Image
    Image.new('RGB',(16,16),(24,24,24)).save(tmp_path/'frame.jpg')
    step=dict(id='final',start=5,end=9,instruction='Unit final state',expected='Unit state',evidence_ids=['f1'])
    knowledge=dict(status='source_checked',source_file='source.mp4',source_sha256=hashlib.sha256(b'explicit unit video').hexdigest(),
        objective='Follow unit source',steps=[step],source_checks=[dict(step_id='final',supported=True,issues=[])],
        evidence=[dict(id='f1',timestamp=7,image='frame.jpg',observations=['unit'],crop=[])])
    (tmp_path/'knowledge.json').write_text(json.dumps(knowledge))
    (tmp_path/'plan.json').write_text(json.dumps(dict(steps=knowledge['steps'],source_sha256=knowledge['source_sha256'])))
    return knowledge


def fake_provider(monkeypatch,proposal=None,supported=True):
    class Vision:
        model='holo4-unit'
        async def check_video_step(self,**kwargs):
            assert len(kwargs['images'])==1 and kwargs['images'][0].startswith(b'\xff\xd8')
            return dict(supported=supported,issues=[] if supported else ['Unit source rejection'])
    async def request(*args,**kw):return proposal or dict(values=values(),evidence_ids=['f1'])
    monkeypatch.setattr(module,'source_request',request)
    return Vision()


def test_targets_are_source_checked_bound_and_not_artifact_verification(tmp_path,monkeypatch):
    knowledge=source(tmp_path);vision=fake_provider(monkeypatch)
    target=asyncio.run(module.build_expectations(tmp_path,vision))
    assert target['values']==values() and target['source_check']['supported']
    assert target['source_sha256']==knowledge['source_sha256']
    assert target['scope']=='blender_bevel_v1'
    assert target.get('verification')!='verified'
    module.validate_binding(target,tmp_path)
    (tmp_path/'plan.json').write_text(json.dumps({'steps':[]}))
    with pytest.raises(ValueError,match='plan'):module.validate_binding(target,tmp_path)


@pytest.mark.parametrize('field,value',[('width',float('nan')),('segments',True),('segments',0),('affect','__import__'),('shape','arbitrary mesh'),('smooth_shading','true'),('angle_limit_degrees',181)])
def test_invalid_values_rejected(field,value):
    target=values();target[field]=value
    with pytest.raises(ValueError):module.validate_values(target)


def test_source_rejection_or_wrong_citation_cannot_create_target(tmp_path,monkeypatch):
    source(tmp_path);vision=fake_provider(monkeypatch,supported=False)
    with pytest.raises(ValueError,match='source'):asyncio.run(module.build_expectations(tmp_path,vision))
    assert not (tmp_path/'artifact-expectations.json').exists()
    vision=fake_provider(monkeypatch,dict(values=values(),evidence_ids=['unseen']))
    with pytest.raises(ValueError,match='citation'):asyncio.run(module.build_expectations(tmp_path,vision))


def test_intermediate_frame_cannot_bind_final_state(tmp_path,monkeypatch):
    knowledge=source(tmp_path)
    knowledge['steps'][-1]['evidence_ids']=['earlier','f1']
    knowledge['evidence'].append(dict(id='earlier',timestamp=6,image='frame.jpg',observations=['unit earlier'],crop=[]))
    (tmp_path/'knowledge.json').write_text(json.dumps(knowledge))
    (tmp_path/'plan.json').write_text(json.dumps(dict(steps=knowledge['steps'],source_sha256=knowledge['source_sha256'])))
    vision=fake_provider(monkeypatch,dict(values=values(),evidence_ids=['earlier']))
    with pytest.raises(ValueError,match='citation'):asyncio.run(module.build_expectations(tmp_path,vision))


def test_wrong_target_citation_regenerates_once_against_same_final_image(tmp_path,monkeypatch):
    source(tmp_path);vision=fake_provider(monkeypatch)
    requests=[]
    async def request(provider,prompt,images,schema,*args,**kwargs):
        requests.append((prompt,images,schema))
        return dict(values=values(),evidence_ids=['earlier'] if len(requests)==1 else ['f1'])
    monkeypatch.setattr(module,'source_request',request)
    target=asyncio.run(module.build_expectations(tmp_path,vision))
    assert len(requests)==2 and requests[0][1]==requests[1][1]
    assert requests[0][2]['properties']['evidence_ids']['items']['enum']==['f1']
    assert target['evidence_ids']==['f1']
    assert list(tmp_path.glob('artifact-target-proposal-*.json'))


def test_changed_source_or_values_invalidate_binding(tmp_path,monkeypatch):
    source(tmp_path);vision=fake_provider(monkeypatch)
    target=asyncio.run(module.build_expectations(tmp_path,vision))
    changed=copy.deepcopy(target);changed['values']['width']=.22
    with pytest.raises(ValueError):module.validate_binding(changed,tmp_path)
    (tmp_path/'source.mp4').write_bytes(b'changed input')
    with pytest.raises(ValueError,match='source'):module.validate_binding(target,tmp_path)


def test_dynamic_artifact_targets_do_not_inherit_legacy_recipe(tmp_path,monkeypatch):
    source(tmp_path);vision=fake_provider(monkeypatch)
    target=asyncio.run(module.build_expectations(tmp_path,vision))
    audit={'objects':[dict(type='MESH',base_vertices=8,base_faces=6,evaluated_vertices=80,evaluated_smooth_faces=50,
        modifiers=[dict(type='BEVEL',visible=True,width=.24,segments=4,affect='VERTICES',width_type='OFFSET',limit_method='ANGLE',angle_limit_degrees=30),
                   dict(type='NODES',node_group='Smooth by Angle',visible=True)])]}
    assert module.assess_source_replica(audit,target)['verification']=='verified'
    audit['objects'][0]['modifiers'][0].update(width=.22,affect='EDGES')
    result=module.assess_source_replica(audit,target)
    assert result['verification']=='failed'
    assert not result['checks']['width'] and not result['checks']['affect']
    assert result['expected']['width']==.24


def test_saved_artifact_uses_bound_targets_and_records_hash(tmp_path,monkeypatch):
    from app.engines import tutorial_artifact
    source(tmp_path);vision=fake_provider(monkeypatch)
    target=asyncio.run(module.build_expectations(tmp_path,vision))
    run=tmp_path/'run';run.mkdir();blend=run/'replica.blend';blend.write_bytes(b'explicit unit blend')
    def inspect(command,**kwargs):
        from types import SimpleNamespace
        audit={'objects':[]}
        assert '--disable-autoexec' in command
        Path(command[-1]).write_text(json.dumps(audit))
        return SimpleNamespace(returncode=0)
    from pathlib import Path
    monkeypatch.setattr(tutorial_artifact.subprocess,'run',inspect)
    result=tutorial_artifact.inspect_replica(blend,expectations=target,source_folder=tmp_path)
    assert result['verification']=='failed' and result['scope']=='blender_bevel_v1'
    assert result['target_binding_sha256']==target['binding_sha256']
    assert result['read_only_hash_unchanged'] is True
