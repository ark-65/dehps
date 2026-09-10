"""Preserved source bodies and complete old/new scientific output equality."""
import ast
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import subprocess
import sys

import pytest

from dehps.prediction import error_learning as legacy
from dehps.prediction.frozen_p3 import calculation, observation, report
from test_prediction_error_learning import inputs, record, outcome

ROOT = Path(__file__).resolve().parents[3]
WORKER = ROOT / 'apps/worker-python'
ORIGINS = {
    'calculation': 'dehps/research_os/information_theory/measurement_system_v2/forward_prequential_confirmatory.py',
    'history': 'dehps/research_os/information_theory/measurement_system_v2/bounded_operational_forward.py',
    'sampling': 'dehps/prediction/v2/generator.py',
    'report': 'dehps/notifications/p3_top100.py',
    'observation': 'dehps/prediction/error_learning.py',
}


def definitions(path):
    result = {}
    for node in ast.parse(path.read_text()).body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            result[node.name] = node
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            for target in node.targets if isinstance(node, ast.Assign) else [node.target]:
                for name in ast.walk(target):
                    if isinstance(name, ast.Name):
                        result[name.id] = node
    return result


@pytest.mark.parametrize('module', ORIGINS)
def test_frozen_definition_bodies_and_constants_are_unchanged(module):
    original = definitions(WORKER / ORIGINS[module])
    extracted = definitions(WORKER / 'dehps/prediction/frozen_p3' / (module + '.py'))
    assert extracted
    for name, node in extracted.items():
        expected = deepcopy(original[name])
        if module == 'calculation' and name == 'load_source_contract':
            # Explicit caller root replaces a production default, preserving every
            # source-file hash/contract check in the original verifier body.
            assert ast.unparse(expected.args.kw_defaults[0]) == 'ROOT_DIR'
            expected.args.kw_defaults[0] = None
        assert ast.dump(node) == ast.dump(expected), name


def test_calculation_imports_cannot_load_runtime_authority_or_mail():
    script = '''
import importlib.abc, sys
forbidden=('dehps.config','dehps.db','dehps.agents','dehps.notifications','dehps.research_os.supervisor','dehps.research_os.repository')
class Reject(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,*args):
        if any(fullname==name or fullname.startswith(name+'.') for name in forbidden):
            raise AssertionError(fullname)
sys.meta_path.insert(0,Reject())
from dehps.prediction.frozen_p3 import observation, calculation, report
assert not any(name in sys.modules for name in forbidden)
'''
    subprocess.run([sys.executable, '-c', script], cwd=WORKER, check=True,
                   env={'PYTHONPATH': str(WORKER), 'PYTHONDONTWRITEBYTECODE': '1'})


@pytest.mark.parametrize('success', [False, True])
def test_complete_prediction_settlement_and_all_100_diagnostics_match_original(inputs, record, success):
    old_bundle, payout = outcome(inputs, success=success)
    restored = observation.restore_decision(record, code_root=ROOT)
    assert asdict(restored) == asdict(inputs)
    bundle = report.PostdrawBundle(restored.predraw, old_bundle.settlement, old_bundle.settlement_replay)
    expected = legacy.build_preview(record, old_bundle, payout, code_root=ROOT,
                                    available_at='2026-09-03T22:00:00+08:00')
    actual = observation.build_preview(record, bundle, payout, code_root=ROOT,
                                       available_at='2026-09-03T22:00:00+08:00')
    assert actual == expected
    assert len(actual['diagnosis']['all_100_tickets']) == 100
    assert len(actual['sample']['body']['red_labels_1_to_33']) == 33
    assert len(actual['sample']['body']['blue_labels_1_to_16']) == 16
    assert actual['sample']['body']['training_status'] == 'RECORDED_NOT_INGESTED_BY_NEW_LEARNER'


def test_explicit_source_validation_remains_required(inputs, record, tmp_path):
    with pytest.raises(TypeError):
        calculation.load_source_contract()
    with pytest.raises(observation.DecisionIntegrityError):
        observation.restore_decision(record, code_root=tmp_path)
    changed = deepcopy(record)
    changed['body']['frozen_inputs']['model']['body']['probabilities_q_1_to_33'][0] += 0.01
    with pytest.raises(observation.DecisionIntegrityError):
        observation.restore_decision(changed, code_root=ROOT)
