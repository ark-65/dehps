"""Fixed estimators and descriptive diagnostics; no runtime or database access."""
from collections import Counter
from functools import lru_cache
from itertools import combinations
import math

import numpy as np

from dehps.input_contracts.candidate_abi import candidate_rank, candidate_unrank
from dehps.prediction.frozen_learning import calculation as retained
from dehps.prediction.frozen_learning.analysis import paired_interval
from dehps.prediction.frozen_p3.sampling import _sample_lex_ids, UNIVERSE
from dehps.prediction.frozen_p3.calculation import _blue_numbers
from .contract import digest, require


def probabilities(counts, count):
    require(type(count) is int and count >= 900 and len(counts) == 33
            and all(type(c) is int and 0 <= c <= count for c in counts) and sum(counts) == 6 * count,
            'invalid sufficient statistics')
    values = {'shrink900': [(c + 900 * (6/33)) / (count + 900) for c in counts],
              'old': list(map(float, retained.formal.estimate_legal_marginals(counts, training_issue_count=count))),
              'uniform': [6/33] * 33}
    require(all(all(math.isfinite(p) and 0 < p < 1 for p in q) and abs(sum(q)-6) < 1e-12
                for q in values.values()), 'invalid probabilities')
    return values


def fit_checkpoint(counts, count):
    """The one fitting entry; recovery/replay use independent formula checks."""
    return probabilities(counts, count)


@lru_cache(maxsize=8)
def proposal(contract_sha, issue):
    seed = bytes.fromhex(digest({'contract': contract_sha, 'issue': issue, 'seed': 20260905}))
    ids = _sample_lex_ids(seed_material=seed, count=10000)
    rows = [list(candidate_unrank(i, universe=UNIVERSE)) for i in ids]
    return tuple(ids), tuple(tuple(row) for row in rows)


def portfolio(q, contract_sha, issue):
    ids, rows = proposal(contract_sha, issue)
    scores = retained.scores(np.asarray(q), np.asarray(rows)-1)
    order = np.lexsort((ids, -scores))[:100]
    blues = _blue_numbers(preregistration_digest=contract_sha, target_issue=issue)
    return [{'rank': rank+1, 'lex_id': ids[int(i)], 'red': list(rows[int(i)]),
             'blue': blues[rank], 'score_bits': float(scores[int(i)])} for rank, i in enumerate(order)]


def score(seal, label, contract_sha):
    if seal['status'] != 'SEALED_BEFORE_DRAW':
        return {**label_record(label), 'status': 'GAP', 'probability': {}, 'diagnostics': {}}
    return score_probabilities(seal['probabilities'], seal['tickets'], label, contract_sha)


def label_record(label):
    red = [int(i in label['red']) for i in range(1, 34)]
    blue = [int(i == label['blue']) for i in range(1, 17)]
    return {'red_labels': red, 'blue_labels': blue, 'label': label,
              'learnable_cause': '证据不足', 'interim_aggregate': 'NOT_COMPUTED',
              'payout': 'NOT_REQUIRED_FOR_PROBABILITY_SCORING'}


def score_probabilities(probabilities, tickets_by_model, label, contract_sha):
    """Pure scoring shared by distinct historical and prospective contracts.

    This function makes no claim about when probabilities were sealed. The
    calling capability must supply that evidence label and its own verifier.
    """
    result = label_record(label)
    red = result['red_labels']
    result.update(status='SCORED', probability={}, diagnostics={})
    for name, q in probabilities.items():
        per_number = [retained.bernoulli_log_loss_nats(y, p) for y, p in zip(red, q, strict=True)]
        result['probability'][name] = {'log_loss': math.fsum(per_number)/33,
            'brier': math.fsum((p-y)**2 for p, y in zip(q, red, strict=True))/33,
            'numbers': [{'number': i+1, 'probability': p, 'label': y,
                         'residual': y-p, 'log_loss': loss}
                        for i, (p, y, loss) in enumerate(zip(q, red, per_number, strict=True))]}
    ids, rows = proposal(contract_sha, label['issue'])
    winning = candidate_rank(tuple(label['red']), universe=UNIVERSE)
    for name in ('shrink900', 'old'):
        q = np.asarray(probabilities[name]); tickets = tickets_by_model[name]
        all_scores = retained.scores(q, np.asarray(rows)-1)
        winning_score = float(retained.scores(q, np.asarray([label['red']])-1)[0])
        rank = 1 + int(np.sum((all_scores > winning_score) | ((all_scores == winning_score) & (np.asarray(ids) < winning))))
        selected = {ticket['lex_id'] for ticket in tickets}
        first_loss = 'NOT_GENERATED' if winning not in ids else ('SELECTED' if winning in selected else 'BELOW_TOP100')
        frequency = Counter(n for ticket in tickets for n in ticket['red'])
        overlaps = Counter(len(set(a['red']) & set(b['red'])) for a, b in combinations(tickets, 2))
        odds = np.log2(q)-np.log2(1-q)
        detail = []
        for ticket in tickets:
            missing, extra = sorted(set(label['red'])-set(ticket['red'])), sorted(set(ticket['red'])-set(label['red']))
            detail.append({**ticket, 'missing': missing, 'extra': extra, 'red_hits': 6-len(missing),
                'blue_hit': ticket['blue'] == label['blue'],
                'hypothetical_replacements': [{'remove': a, 'add': b, 'delta_bits': float(odds[b-1]-odds[a-1])}
                                               for a in extra for b in missing]})
        result['diagnostics'][name] = {'first_loss_stage': first_loss,
            'actual_pool_rank': rank if winning in ids else None,
            'hypothetical_insertion_rank': rank if winning not in ids else None,
            'winning_score_bits': winning_score, 'top100_cutoff_bits': tickets[-1]['score_bits'],
            'extra_filter': 'NONE', 'all_100_tickets': detail,
            'number_exposures': [frequency[i] for i in range(1, 34)],
            'overlap_histogram': {str(i): overlaps[i] for i in range(7)},
            'hit_histogram': {str(i): sum(t['red_hits'] == i for t in detail) for i in range(7)}}
    return result


def final_analysis(scores, targets):
    require([row['issue'] for row in scores] == [t['issue'] for t in targets] and len(scores) == 60,
            'analysis requires all fixed 60 terminal scores')
    gaps = [row['issue'] for row in scores if row['scientific']['status'] != 'SCORED']
    result = {'targets': [t['issue'] for t in targets], 'gaps': gaps, 'promotion': False,
              'family_intervals': {}, 'conclusion': '证据不足'}
    if gaps:
        return {**result, 'status': 'INCOMPLETE_WINDOW', 'favorable_conclusion_allowed': False}
    losses = {name: np.asarray([row['scientific']['probability'][name]['log_loss'] for row in scores])
              for name in ('shrink900', 'old', 'uniform')}
    result['mean_log_loss'] = {name: float(value.mean()) for name, value in losses.items()}
    result['descriptive'] = {}
    for name in losses:
        metrics = [row['scientific']['probability'][name] for row in scores]
        numbers = [number for item in metrics for number in item['numbers']]
        bins = []
        for index in range(20):
            members = [n for n in numbers if min(19, int(n['probability']*20)) == index]
            bins.append({'lower': index/20, 'upper': (index+1)/20, 'count': len(members),
                         'mean_probability': math.fsum(n['probability'] for n in members)/len(members) if members else None,
                         'observed_fraction': math.fsum(n['label'] for n in members)/len(members) if members else None})
        result['descriptive'][name] = {'mean_brier': math.fsum(m['brier'] for m in metrics)/60,
                                      'calibration_bins': bins, 'decision_metric': False}
    for name in ('old', 'uniform'):
        result['family_intervals'][name] = paired_interval(losses['shrink900']-losses[name], seed=20260905, family=8)
    intervals = result['family_intervals'].values()
    if all(value['upper'] < 0 for value in intervals):
        result['conclusion'] = '本窗口观察到改善'
    elif any(value['lower'] >= 0 for value in intervals):
        result['conclusion'] = '未改善'
    result['status'] = 'WINDOW_ANALYZED'
    return result
