import copy
import json
import pytest
from app.engines.tutorial_artifact import assess_replica,inspect_replica

# Explicit unit fixture, not a real execution receipt.
def fixture_audit():
    return {'objects':[{'type':'MESH','base_vertices':8,'base_faces':6,'evaluated_vertices':152,'evaluated_smooth_faces':150,'modifiers':[{'type':'BEVEL','visible':True,'width':.22,'segments':4,'affect':'EDGES'}]}]}


def test_matching_audit_passes_all_checks():
    result=assess_replica(fixture_audit())
    assert result['verification']=='verified'
    assert all(result['checks'].values())


@pytest.mark.parametrize('field,value',[('width',.24),('segments',1),('visible',False),('affect','VERTICES')])
def test_wrong_bevel_never_passes(field,value):
    audit=fixture_audit();audit['objects'][0]['modifiers'][0][field]=value
    assert assess_replica(audit)['verification']=='failed'


def test_missing_or_duplicate_meshes_and_flat_shading_fail():
    assert assess_replica({'objects':[]})['verification']=='failed'
    audit=fixture_audit();audit['objects'].append(copy.deepcopy(audit['objects'][0]))
    assert assess_replica(audit)['verification']=='failed'
    audit=fixture_audit();audit['objects'][0]['evaluated_smooth_faces']=0
    assert assess_replica(audit)['verification']=='failed'


def test_missing_saved_artifact_is_failure(tmp_path):
    assert inspect_replica(tmp_path/'replica.blend')['verification']=='failed'


def test_old_audit_cannot_verify_an_inspector_that_produced_no_new_report(tmp_path,monkeypatch):
    from types import SimpleNamespace
    from app.engines import tutorial_artifact as module
    target=tmp_path/'replica.blend';target.write_bytes(b'explicit unit artifact')
    old=json.dumps(fixture_audit())
    target.with_suffix('.audit.json').write_text(old)
    monkeypatch.setattr(module.subprocess,'run',lambda *args,**kwargs:SimpleNamespace(returncode=0))
    result=module.inspect_replica(target)
    assert result['verification']=='failed'
    archived=list(tmp_path.glob('replica.audit-*.json'))
    assert len(archived)==1 and archived[0].read_text()==old
