import json

import pytest

from app.providers.base import ProviderError
from app.tasks.knowledge import grounded_knowledge


def trace():
    actions = []
    for index, (kind, label, text) in enumerate([
        ('click', 'Settings', ''), ('type', 'Enter value', 'refund'),
        ('select', 'Event', 'Message Created'), ('click', 'Update', ''),
    ]):
        actions.append({'kind': kind, 'target': 1, 'target_label': label, 'text': text,
                        'summary': 'Observed UI operation', 'outcome': 'executed',
                        'observation': {'step': index + 1, 'controls': [{'id': 1, 'tag': 'input' if kind == 'type' else 'button'}]}})
    return {'id': 'run_test', 'actions': actions,
            'sources': [{'url': 'https://www.chatwoot.com/guide', 'finding': 'Unexecuted example: Send an Email.'}]}


TASK = {'request': 'Route refund messages', 'software_version': '4.8.0',
        'criteria': [{'requirement': 'Refund requests', 'team': 'Billing', 'priority': 'default'}]}


def test_skill_steps_are_reconstructed_locally_from_actual_action_references():
    result = grounded_knowledge(TASK, trace())
    assert result['grounding_version'] == 2
    assert result['action_references'] == [0, 1, 2, 3]
    assert result['evidence_steps'] == [1, 2, 3, 4]
    assert 'Message Created' in ' '.join(result['procedure'])
    assert 'refund' in ' '.join(result['procedure'])
    assert 'Send an Email' not in json.dumps(result)


def test_unexecuted_and_research_operations_never_become_skill_steps():
    run = trace()
    run['actions'].extend([
        {'kind': 'type', 'outcome': 'blocked', 'text': 'unexecuted secret'},
        {'kind': 'research', 'outcome': 'executed', 'text': 'unexecuted example'},
    ])
    result = grounded_knowledge(TASK, run)
    assert result['action_references'] == [0, 1, 2, 3]
    assert 'unexecuted' not in json.dumps(result)


def test_skill_requires_an_observed_mutation():
    run = trace()
    run['actions'] = [run['actions'][0], run['actions'][3]]
    with pytest.raises(ProviderError, match='configuration'):
        grounded_knowledge(TASK, run)
