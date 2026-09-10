"""Scientific definition preservation and explicit-input learning equivalence."""
import ast
from copy import deepcopy
from pathlib import Path
import subprocess
import sys

from dehps.prediction import learning_v1 as original
from dehps.prediction.frozen_learning import calculation
from test_frozen_p3_compute import definitions
from test_prediction_learning_v1 import synthetic

WORKER = Path(__file__).resolve().parents[1]


def test_learning_definitions_preserved_except_explicit_input_interface():
    before = definitions(WORKER / 'dehps/prediction/learning_v1.py')
    after = definitions(WORKER / 'dehps/prediction/frozen_learning/calculation.py')
    assert '_INPUTS' not in after
    assert not {'immutable', 'read', 'init_worker', 'probe'} & set(after)
    for name, node in after.items():
        expected = deepcopy(before[name])
        if name == 'evaluate_issue':
            expected.args.kwonlyargs = [ast.arg(arg='snapshot'), ast.arg(arg='contract')]
            expected.args.kw_defaults = [None, None]
            assert ast.unparse(expected.body[1]) == 'snapshot, contract, y = _INPUTS'
            expected.body[1] = ast.parse('y = targets(snapshot["rows"])').body[0]
        assert ast.dump(node) == ast.dump(expected), name


def test_learning_import_does_not_select_legacy_runtime_or_configuration():
    script = '''
import importlib.abc,sys
forbidden=('dehps.config','dehps.db','dehps.agents','dehps.notifications',
 'dehps.research_os.supervisor','dehps.research_os.repository','dehps.prediction.learning_v1',
 'dehps.research_os.information_theory.measurement_system_v2.forward_prequential_confirmatory')
class Reject(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,*args):
  if any(fullname==name or fullname.startswith(name+'.') for name in forbidden):
   raise AssertionError(fullname)
sys.meta_path.insert(0,Reject())
from dehps.prediction.frozen_learning import calculation, analysis
assert not hasattr(calculation,'_INPUTS')
'''
    subprocess.run([sys.executable, '-c', script], cwd=WORKER, check=True,
                   env={'PYTHONPATH': str(WORKER), 'PYTHONDONTWRITEBYTECODE': '1'})


def test_complete_four_model_six_arm_random_baseline_result_matches_original(synthetic, tmp_path):
    snapshot = original.seal('test-snapshot', synthetic)
    contract = original.seal('test-contract', {'random_repetitions': 32})
    original.immutable(tmp_path / 'snapshot.json', snapshot)
    original.immutable(tmp_path / 'contract.json', contract)
    original.init_worker(tmp_path / 'snapshot.json', tmp_path / 'contract.json')
    expected = original.evaluate_issue(900)
    actual = calculation.evaluate_issue(900, snapshot=synthetic, contract=contract)
    assert actual == expected
    assert len(actual['body']['probabilities']) == 6
    assert len(actual['body']['arms']) == 6
    assert all(len(arm['ticket_ids']) == 100 for arm in actual['body']['arms'].values())
    assert all(len(repetitions) == 32 for repetitions in actual['body']['random'].values())
    # A second explicit index cannot overwrite the first task's input selection.
    assert calculation.evaluate_issue(901, snapshot=synthetic, contract=contract) == original.evaluate_issue(901)
    assert calculation.evaluate_issue(900, snapshot=synthetic, contract=contract) == expected
    assert calculation.combinations().flags.writeable is False


def test_analysis_numerical_bodies_preserved_while_io_is_explicit():
    before = definitions(WORKER / 'dehps/prediction/learning_v1_runtime.py')
    after = definitions(WORKER / 'dehps/prediction/frozen_learning/analysis.py')
    assert ast.dump(after['paired_interval']) == ast.dump(before['paired_interval'])
    expected = deepcopy(before['payouts'])
    expected.args.args = [ast.arg(arg='issue_values'), ast.arg(arg='payout_records')]
    expected.body[0] = ast.parse('"""Use only supplied frozen payout evidence; verify exact label identity."""').body[0]
    assert isinstance(expected.body[1], ast.ImportFrom)
    del expected.body[1]
    loop = expected.body[4]
    assert ast.unparse(loop.target) == 'value' and ast.unparse(loop.iter) == 'required'
    assert ast.unparse(loop.body[1].targets[0]) == 'path' and isinstance(loop.body[2], ast.If)
    loop.body[1:3] = ast.parse('record = core.verify(payout_records[issue])["body"]["record"]').body
    assert ast.dump(after['payouts']) == ast.dump(expected)
    expected = deepcopy(before['analyze'])
    expected.args.args = [ast.arg(arg=name) for name in ('contract', 'training', 'read_issue', 'payout_records')]
    del expected.body[:2]
    assert isinstance(expected.body[1], ast.For)
    expected.body[1].body[0] = ast.parse('value = core.verify(deepcopy(read_issue(item["artifact_digest"])))').body[0]
    expected.body[2] = ast.parse('exact_payouts = payouts(issue_values, payout_records)').body[0]
    assert 'core.immutable' in ast.unparse(expected.body[-2])
    del expected.body[-2]
    assert ast.dump(after['analyze']) == ast.dump(expected)
    training = before['run_training'].body
    start = next(i for i, node in enumerate(training) if isinstance(node, ast.Assign) and ast.unparse(node.targets[0]) == 'all_y')
    end = next(i for i, node in enumerate(training[start:], start) if isinstance(node, ast.Expr)
               and ast.unparse(node).startswith('core.immutable'))
    assert [ast.dump(node) for node in after['refit_checkpoint'].body[2:-1]] == [ast.dump(node) for node in training[start:end]]
