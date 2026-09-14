"""Fixed score-before-update arithmetic; reports cannot change an estimator."""
import math

from dehps.prediction.forward_learning import calculation as fixed
from .contract import digest, require


def initial(records):
    rows = [r['label'] for r in records[:900]]
    return {'count': 900, 'counts': [sum(n in r['red'] for r in rows) for n in range(1, 34)],
        'blue_counts': [sum(n == r['blue'] for r in rows) for n in range(1, 17)],
        'training_end_issue': rows[-1]['issue'], 'last_input_sha256': digest(records[899])}


def update(before, record, contract_sha, *, fitting=False):
    label = record['label']
    require(before['training_end_issue'] < label['issue'], 'score-before-update boundary violated')
    require(len(before['blue_counts']) == 16 and sum(before['blue_counts']) == before['count'], 'blue label counts invalid')
    q = (fixed.fit_checkpoint if fitting else fixed.probabilities)(before['counts'], before['count'])
    tickets = {name: fixed.portfolio(q[name], contract_sha, label['issue']) for name in ('old', 'shrink900')}
    score = fixed.score_probabilities(q, tickets, label, contract_sha)
    score['status'] = 'HISTORICAL_RECONSTRUCTION'
    after = {'count': before['count']+1,
        'counts': [c+y for c, y in zip(before['counts'], score['red_labels'], strict=True)],
        'blue_counts': [c+y for c, y in zip(before['blue_counts'], score['blue_labels'], strict=True)],
        'training_end_issue': label['issue'], 'last_input_sha256': digest(record)}
    require(sum(after['counts'])-sum(before['counts']) == 6 and sum(after['blue_counts'])-sum(before['blue_counts']) == 1,
            'label count conservation failed')
    return {'issue': label['issue'], 'input_sha256': digest(record), 'training_cutoff': before['training_end_issue'],
        'before': before, 'before_sha256': digest(before), 'after': after, 'after_sha256': digest(after),
        'probabilities': q, 'score': score, 'original_references': record['references'],
        'original_prediction_status': 'REFERENCED' if any(r['kind'] == 'ORIGINAL_PREDICTION' for r in record['references']) else 'REPORT_GAP',
        'evidence': 'EXPLORATORY_HISTORICAL_RECONSTRUCTION', 'blue_training': False, 'promotion': False}


def summarize(reports):
    require(reports and [r['issue'] for r in reports] == sorted(set(r['issue'] for r in reports)), 'summary order differs')
    return {'status': 'HISTORICAL_BATCH_COMPLETE', 'evaluated_count': len(reports),
        'first_issue': reports[0]['issue'], 'last_issue': reports[-1]['issue'],
        'mean_log_loss': {m: math.fsum(r['metrics'][m]['log_loss'] for r in reports)/len(reports) for m in ('old', 'shrink900', 'uniform')},
        'mean_brier': {m: math.fsum(r['metrics'][m]['brier'] for r in reports)/len(reports) for m in ('old', 'shrink900', 'uniform')},
        'original_prediction_gaps': [r['issue'] for r in reports if r['original_prediction_status'] == 'REPORT_GAP'],
        'final_checkpoint_sha256': reports[-1]['checkpoint_sha256'],
        'conclusion': '证据不足', 'evidence': 'EXPLORATORY_HISTORICAL_RECONSTRUCTION',
        'predictive_improvement_proven': False, 'promotion': False}
