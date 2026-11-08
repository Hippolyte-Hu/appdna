import copy
import json

import pytest
from fastapi.testclient import TestClient

from app.tasks.catalog import BASE_REQUEST, criteria
from app.tasks.graph import assemble_graph


def records():
    task = {'id': 'task_graph', 'title': 'VIP routing', 'software': 'Chatwoot',
            'software_version': '4.8.0', 'criteria': criteria('vip')}
    checks = [{'id': item['id'], 'status': 'passed',
               'actual': {'team': item['team'], 'priority': item['priority']},
               'input': {'message': 'DO_NOT_EXPOSE_FIXTURE'},
               'record': {'private': 'DO_NOT_EXPOSE_RAW_RECORD'}} for item in task['criteria']]
    source = {'id': 'run_111111111111', 'task_id': task['id'], 'status': 'completed',
              'created_at': '2026-11-08T10:00:00+00:00', 'knowledge_refs': [],
              'verifications': checks, 'actions': [{'summary': 'DO_NOT_EXPOSE_ACTION_PAYLOAD'}],
              'environment': {'api_token': 'DO_NOT_EXPOSE_API_TOKEN'},
              'observation': {'image': 'step_001.png'}}
    reuse = copy.deepcopy(source)
    reuse.update(id='run_222222222222', status='failed', knowledge_refs=['knowledge_graph'])
    reuse['verifications'][-1].update(status='failed', actual={'team': 'logistics', 'priority': 'high',
                                                             'debug_token': 'DO_NOT_EXPOSE_ACTUAL_EXTRA'})
    skill = {'id': 'knowledge_graph', 'software': 'Chatwoot', 'software_version': '4.8.0',
             'operation': 'Configure routing', 'run_id': source['id'], 'validated_at': source['created_at'],
             'procedure': ['Observed UI configuration'],
             'source_refs': ['https://www.chatwoot.com/hc/user-guide/articles/1677689800-how-to-use-automation'] * 2}
    return [skill], [task], [source, reuse]


def test_graph_contains_real_validation_and_reuse_relationships_only():
    skills, tasks, runs = records()
    unrelated = {**runs[0], 'id': 'run_333333333333'}
    graph = assemble_graph(skills, tasks, [*runs, unrelated])
    nodes = {node['id']: node for node in graph['nodes']}
    assert 'run_333333333333' not in nodes
    assert nodes['knowledge_graph']['status'] == 'verified'
    assert nodes[runs[1]['id']]['status'] == 'failed'
    assert graph['counts'] == {'run': 2, 'check': 7, 'app': 1, 'skill': 1, 'source': 1}
    relationships = {(link['source'], link['target'], link['relation']) for link in graph['links']}
    assert ('knowledge_graph', runs[0]['id'], 'learned_in') in relationships
    assert ('knowledge_graph', runs[1]['id'], 'reused_in') in relationships
    assert len(relationships) == len(graph['links'])
    assert all(link['source'] in nodes and link['target'] in nodes for link in graph['links'])
    complaint = next(node for node in graph['nodes'] if node['kind'] == 'check' and node['label'] == 'VIP serious complaints')
    assert complaint['status'] == 'mixed'
    assert complaint['outcomes'] == {'passed': 1, 'failed': 1}
    failed = next(link for link in graph['links'] if link.get('status') == 'failed')
    assert failed['actual'] == {'team': 'logistics', 'priority': 'high'}


def test_graph_never_serializes_fixtures_tokens_raw_records_or_action_payloads():
    graph = assemble_graph(*records())
    assert 'DO_NOT_EXPOSE' not in json.dumps(graph)
    assert all('/api/task-runs/' in node['image_url'] for node in graph['nodes'] if 'image_url' in node)


def test_superseded_skills_and_unsafe_source_urls_are_not_presented():
    skills, tasks, runs = records()
    superseded = {**skills[0], 'id': 'old_skill', 'superseded_by': 'knowledge_graph'}
    runs.append({**runs[0], 'id': 'run_444444444444', 'knowledge_refs': ['old_skill']})
    skills[0]['source_refs'] += ['javascript:alert(1)', 'https://example.invalid/doc?token=DO_NOT_EXPOSE_QUERY', 'http://[bad']
    graph = assemble_graph([*skills, superseded], tasks, runs)
    assert not any(node['id'] in {'old_skill', 'run_444444444444'} for node in graph['nodes'])
    assert graph['counts']['source'] == 1
    assert 'DO_NOT_EXPOSE' not in json.dumps(graph)


def test_missing_verification_is_not_promoted_to_verified_knowledge():
    skills, tasks, runs = records()
    runs[0]['verifications'] = runs[0]['verifications'][:-1]
    graph = assemble_graph(skills, tasks, runs)
    assert next(node for node in graph['nodes'] if node['kind'] == 'skill')['status'] == 'unverified'


def test_empty_library_produces_no_decorative_or_seeded_graph_nodes():
    graph = assemble_graph([], [], [])
    assert graph['nodes'] == graph['links'] == []
    assert graph['counts'] == {}


def test_graph_api_is_available_without_exposing_internal_run_state(monkeypatch):
    from app.main import app
    monkeypatch.setattr('app.main.init_db', lambda: None)
    monkeypatch.setattr('app.main.recover_interrupted_runs', lambda: None)
    expected = assemble_graph(*records())
    monkeypatch.setattr('app.tasks.graph.knowledge_graph', lambda: expected)
    with TestClient(app) as client:
        response = client.get('/api/knowledge/graph')
    assert response.status_code == 200
    assert response.json() == expected
    assert 'DO_NOT_EXPOSE' not in response.text
