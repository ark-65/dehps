"""Use only the exact adjacent publisher source staged in the reviewed package."""
from pathlib import Path
import sys

source = Path(__file__).resolve().parent/'source/apps/worker-python'
sys.path.insert(0, str(source))
from dehps.prediction.historical_learning import operations

if Path(operations.__file__).resolve() != source/'dehps/prediction/historical_learning/operations.py':
    raise SystemExit('Fixed publisher source binding differs')
operations.main()
