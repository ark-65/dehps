"""Indexed completion validation retains the original exact-match boundary."""
from types import SimpleNamespace

import pytest

from dehps.research_os.mainline import (
    completion_execution_ids, mainline_completion_fact, validate_mainline_completion_declarations,
)
from dehps.research_os.models import CompletionClassification, ResearchOSValidationError, TaskStatus


@pytest.mark.parametrize('key', ['ordinary', 'prefix:embedded', 'regex.[*]\nend'])
@pytest.mark.parametrize('successes', [0, 1, 2])
def test_index_requires_one_exact_task_digest_and_execution(key, successes):
    task = SimpleNamespace(task_key=key, artifact_digest='a'*64, requested_capability='fixture')
    valid = mainline_completion_fact(task=task, execution_id='b'*64)
    facts = {valid+'\n', valid.replace('a'*64, 'c'*64), valid.replace(key, key+'suffix'),
             valid.replace('completed', 'failed'), 'unrelated-artifact'}
    if successes:
        facts.add(valid)
    if successes == 2:
        facts.add(mainline_completion_fact(task=task, execution_id='d'*64))
    manifest = SimpleNamespace(tasks=(task,), facts=SimpleNamespace(artifacts=frozenset(facts)),
        task_state_by_digest={task.artifact_digest: SimpleNamespace(declared_status=TaskStatus.COMPLETED,
            completion_classification=CompletionClassification.COMPLETE)})
    assert len(completion_execution_ids(manifest, task=task)) == successes
    if successes == 1:
        validate_mainline_completion_declarations(manifest)
    else:
        with pytest.raises(ResearchOSValidationError, match='exactly one immutable'):
            validate_mainline_completion_declarations(manifest)
