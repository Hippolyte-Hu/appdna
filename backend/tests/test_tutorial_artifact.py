import copy
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
