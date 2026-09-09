import importlib.util
from pathlib import Path

import pytest


def load():
    path = Path(__file__).resolve().parents[1] / "scripts/complete_prediction_learning_v1_analysis.py"
    spec = importlib.util.spec_from_file_location("learning_payout_normalization", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_remote_field_aliases_preserve_raw_payload_and_prizes():
    adapter = load()
    raw = {"issue": "2009096", "frontWinningNum": "01 26 27 31 32 33", "backWinningNum": "03",
           "winnerDetails": [{"awardEtc": "1", "baseBetWinner": {"awardMoney": "10000000"}}]}
    original = adapter.core.raw(raw)
    row = {"issue": "2009096", "red": [1,26,27,31,32,33], "blue": 3}
    canonical = adapter.normalize(raw, row)
    assert canonical["red"] == row["red"] and canonical["blue"] == 3
    assert canonical["winnerDetails"] == raw["winnerDetails"]
    assert adapter.core.raw(raw) == original
    assert set(canonical) - set(raw) == {"red", "blue"}


@pytest.mark.parametrize("changed", ({"issue": "2009097"}, {"blue": 4}, {"red": [1,2,3,4,5,6]}))
def test_normalization_rejects_mismatched_labels(changed):
    adapter = load()
    raw = {"issue": "2009096", "frontWinningNum": "01 26 27 31 32 33", "backWinningNum": "03"}
    row = {"issue": "2009096", "red": [1,26,27,31,32,33], "blue": 3, **changed}
    with pytest.raises(AssertionError):
        adapter.normalize(raw, row)
