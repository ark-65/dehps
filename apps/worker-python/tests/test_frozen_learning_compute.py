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
from dehps.prediction.frozen_learning import calculation
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
