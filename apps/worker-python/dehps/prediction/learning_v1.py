"""Frozen first-round marginal learning. No production mutation or delivery."""
from __future__ import annotations

import hashlib
import itertools
import json
import math
import os
import resource
import time
from datetime import date
from pathlib import Path

import numpy as np

from dehps.input_contracts.candidate_abi import candidate_unrank
from dehps.notifications.p3_top100 import prize_tier
from dehps.prediction.v2.generator import UNIVERSE, _sample_lex_ids
from dehps.research_os.information_theory.measurement_system_v2 import forward_prequential_confirmatory as formal
from dehps.research_os.information_theory.metrics.log_loss import bernoulli_log_loss_nats
from dehps.research_os.information_theory.walk_forward.contracts import OuterFold
from dehps.research_os.information_theory.walk_forward.split import validate_outer_fold

GOAL = "dehps-prediction-learning-v1"
SEED = 20260905
MINIMUM = 900
CONFIGS = (
    {"name": "shrink900", "kind": "expanding", "alpha": 900},
    {"name": "shrink100", "kind": "expanding", "alpha": 100},
    {"name": "window156", "kind": "window", "window": 156, "alpha": 100},
    {"name": "decay156", "kind": "decay", "half_life": 156, "alpha": 100},
)
ARMS = ("old_original", "new_original", "old_full", "old_diverse",
        "new_full", "combined_diverse")
_COMBINATIONS = None
_INPUTS = None


def raw(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value) -> str:
    return hashlib.sha256(raw(value)).hexdigest()


def seal(kind, body):
    parents = sorted({v for k, v in body.items() if k.endswith("_digest") and isinstance(v, str) and len(v) == 64})
    result = {"schema_version": "prediction-learning.v1", "artifact_type": kind,
              "body": body, "parent_digests": parents}
    return {**result, "artifact_digest": digest(result)}


def verify(value):
    assert value == seal(value["artifact_type"], value["body"]), "artifact digest changed"
    return value


def immutable(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    content = raw(value) + b"\n"
    if path.exists():
        assert path.read_bytes() == content, f"immutable collision: {path}"
        return
    # Link is an atomic, no-overwrite publication, including across workers.
    temp = path.with_name(path.name + f".{os.getpid()}.tmp")
    with temp.open("xb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        os.link(temp, path)
    except FileExistsError:
        assert path.read_bytes() == content, f"immutable collision: {path}"
    finally:
        temp.unlink()


def read(path):
    return verify(json.loads(Path(path).read_text()))


def validate_rows(rows, *, today):
    assert len(rows) > MINIMUM and len({r["issue"] for r in rows}) == len(rows)
    previous = None
    for row in rows:
        issue, day, red, blue = row["issue"], row["draw_date"], row["red"], row["blue"]
        assert len(issue) == 7 and issue.isdigit()
        assert len(red) == 6 and red == sorted(set(red)) and 1 <= red[0] < red[-1] <= 33
        assert isinstance(blue, int) and 1 <= blue <= 16
        assert day < today, "snapshot contains an unopened or same-day draw"
        if previous:
            assert previous["issue"] < issue and previous["draw_date"] < day
            if previous["issue"][:4] == issue[:4]:
                assert int(issue) == int(previous["issue"]) + 1, "history issue gap"
            else:
                assert issue.endswith("001"), "new year starts with missing issue"
        previous = row


def targets(rows):
    y = np.zeros((len(rows), 33), dtype=np.int8)
    for i, row in enumerate(rows):
        y[i, np.asarray(row["red"]) - 1] = 1
    return y


def fit(y, config):
    n = len(y)
    assert n >= MINIMUM
    if config["kind"] == "window":
        sample = y[-config["window"]:]
        counts, mass = sample.sum(axis=0), len(sample)
    elif config["kind"] == "decay":
        weights = np.exp2(-np.arange(n - 1, -1, -1) / config["half_life"])
        counts, mass = weights @ y, float(weights.sum())
    else:
        counts, mass = y.sum(axis=0), n
    q = (counts + config["alpha"] * (6 / 33)) / (mass + config["alpha"])
    assert np.isfinite(q).all() and (q > 0).all() and (q < 1).all()
    assert abs(float(q.sum()) - 6) < 1e-12
    return q, {"config": config, "training_count": n, "weighted_event_counts": counts.tolist(),
               "effective_draw_mass": mass, "probabilities": q.tolist(),
               "formula": "(weighted_event_count + alpha * 6/33)/(effective_draw_mass + alpha)"}


def loss(y, q):
    return math.fsum(bernoulli_log_loss_nats(int(a), float(b)) for a, b in zip(y, q, strict=True)) / 33


def combinations():
    global _COMBINATIONS
    if _COMBINATIONS is None:
        _COMBINATIONS = np.asarray(list(itertools.combinations(range(33), 6)), dtype=np.int8)
        assert _COMBINATIONS.shape == (1107568, 6)
        for index in (0, 1, 555555, 1107567):
            assert tuple(_COMBINATIONS[index] + 1) == candidate_unrank(index, universe=UNIVERSE)
        _COMBINATIONS.flags.writeable = False
    return _COMBINATIONS


def scores(q, pool):
    # Composite marginal score; constant term matters for recorded swaps/scores.
    odds = np.log2(q) - np.log2(1 - q)
    return odds[pool].sum(axis=1) + np.log2(1 - q).sum()


def ordered(ids, value, count=100):
    return np.asarray(ids)[np.lexsort((ids, -value))[:count]]


def diverse(ids, value, pool, count=100):
    counts = np.zeros(33)
    available = np.ones(len(ids), dtype=bool)
    chosen = []
    for _ in range(count):
        adjusted = value - 0.01 * counts[pool].sum(axis=1)
        adjusted[~available] = -np.inf
        best = np.max(adjusted)
        ties = np.flatnonzero(adjusted == best)
        j = ties[np.argmin(ids[ties])]
        chosen.append(int(ids[j]))
        available[j] = False
        counts[pool[j]] += 1
    return np.asarray(chosen)


def seed(issue, arm, repetition=0):
    return bytes.fromhex(digest({"seed": SEED, "issue": issue, "arm": arm, "rep": repetition}))


def ticket_diagnostics(ids, blues, row, q, original_ids, actual_global_rank):
    pool = combinations()[ids]
    actual = np.asarray(row["red"]) - 1
    hits = np.isin(pool, actual).sum(axis=1)
    concentration = np.bincount(pool.ravel(), minlength=33)
    overlap = np.zeros((100, 100), dtype=np.int8)
    indicators = np.zeros((100, 33), dtype=np.int8)
    indicators[np.arange(100)[:, None], pool] = 1
    overlap = indicators @ indicators.T
    winning_id = lex_id(row["red"])
    pool_hit = bool(np.any(original_ids == winning_id))
    selected_hit = bool(np.any(ids == winning_id))
    odds = np.log2(q) - np.log2(1 - q)
    swap = []
    # All selected tickets and all missed/extra number pairs, never closest-ticket selection.
    for ticket in pool:
        missing, extra = sorted(set(actual) - set(ticket)), sorted(set(ticket) - set(actual))
        swap.append([[int(a + 1), int(b + 1), float(odds[a] - odds[b])]
                     for a in missing for b in extra])
    tiers = [prize_tier(red_hits=int(h), blue_hit=int(b) == row["blue"])
             for h, b in zip(hits, blues, strict=True)]
    fixed = {0: 0, 3: 3000, 4: 200, 5: 10, 6: 5}
    unknown = [i for i, tier in enumerate(tiers) if tier in (1, 2)]
    gross = sum(fixed.get(tier, 0) for tier in tiers)
    return {"ticket_ids": ids.tolist(), "blue_by_rank": list(map(int, blues)),
            "hit_counts_0_to_6": np.bincount(hits, minlength=7).tolist(),
            "max_red_hits": int(hits.max()), "number_counts": concentration.tolist(),
            "max_number_share": float(concentration.max() / 100),
            "mean_pairwise_red_overlap": float(overlap[np.triu_indices(100, 1)].mean()),
            "tier_counts_0_to_6": np.bincount(tiers, minlength=7).tolist(),
            "winning_in_candidate_pool": pool_hit, "winning_in_top100": selected_hit,
            "first_rejection": "selected" if selected_hit else "combination_ranking" if pool_hit else "candidate_generation",
            "full_space_score_rank": actual_global_rank,
            "swap_missing_extra_delta_bits": swap,
            "pretax_net_cny": None if unknown else gross - 200,
            "roi": None if unknown else (gross - 200) / 200,
            "fixed_tier_net_lower_bound_cny": gross - 200,
            "floating_payout_tickets": unknown}


def lex_id(red):
    previous, rank = 0, 0
    for pos, number in enumerate(red):
        rank += sum(math.comb(33 - value, 5 - pos) for value in range(previous + 1, number))
        previous = number
    return rank


def init_worker(snapshot_path, contract_path):
    global _INPUTS
    snap, contract = read(snapshot_path), read(contract_path)
    _INPUTS = (snap["body"], contract, targets(snap["body"]["rows"]))
    combinations()


def evaluate_issue(index):
    started = time.monotonic()
    snapshot, contract, y = _INPUTS
    rows = snapshot["rows"]
    validate_outer_fold(OuterFold(tuple(range(1, index + 1)), index + 1),
                        minimum_training_issues=MINIMUM, dataset_issue_count=len(rows))
    row = rows[index]
    history = [(r["issue"], date.fromisoformat(r["draw_date"]), tuple(r["red"])) for r in rows[:index]]
    _, old_model = formal.fit_model_artifacts(source_contract=snapshot["formal_source"],
        preregistration=snapshot["formal_preregistration"], history_rows=history, target_issue=row["issue"])
    old = np.asarray(old_model["body"]["probabilities_q_1_to_33"])
    all_q = {"old": old, "uniform": np.full(33, 6 / 33)}
    all_q.update({c["name"]: fit(y[:index], c)[0] for c in CONFIGS})
    new = all_q["shrink900"]
    prereg_digest = snapshot["formal_preregistration"]["artifact_digest"]
    pool_seed = formal._arm_seed(preregistration_digest=prereg_digest, target_issue=row["issue"],
        arm="MODEL_PROPOSAL_POOL", model_digest=old_model["artifact_digest"])
    ids = np.asarray(_sample_lex_ids(seed_material=bytes.fromhex(pool_seed), count=10000))
    space = combinations()
    # Exact original scalar score is retained for the original algorithm.
    old_local = np.asarray([formal._ticket_score(ticket + 1, old) for ticket in space[ids]])
    new_local = scores(new, space[ids])
    full_old, full_new = scores(old, space), scores(new, space)
    full_ids = np.arange(len(space))
    old_full = ordered(full_ids, full_old)
    new_shortlist = ordered(full_ids, full_new, 10000)
    tickets = {"old_original": ordered(ids, old_local), "new_original": ordered(ids, new_local),
        "old_full": old_full, "old_diverse": diverse(ids, old_local, space[ids]),
        "new_full": new_shortlist[:100],
        "combined_diverse": diverse(new_shortlist, full_new[new_shortlist], space[new_shortlist])}
    actual_id = lex_id(row["red"])
    ranks = {name: int(1 + np.count_nonzero((s > s[actual_id]) | ((s == s[actual_id]) & (full_ids < actual_id))))
             for name, s in (("old", full_old), ("new", full_new))}
    blues = formal._blue_numbers(preregistration_digest=prereg_digest, target_issue=row["issue"])
    arms = {}
    for name, selected in tickets.items():
        is_new = name in ("new_original", "new_full", "combined_diverse")
        full = name in ("old_full", "new_full", "combined_diverse")
        arms[name] = ticket_diagnostics(selected, blues, row, new if is_new else old,
                                        full_ids if full else ids, ranks["new" if is_new else "old"])
        arms[name]["overlap_with_original_ticket_count"] = int(np.isin(selected, tickets["old_original"]).sum())
        if name in ("old_diverse", "combined_diverse") and not arms[name]["winning_in_top100"] and arms[name]["winning_in_candidate_pool"]:
            arms[name]["first_rejection"] = "final_selection"
        if name == "combined_diverse" and actual_id not in new_shortlist:
            arms[name]["first_rejection"] = "selection_shortlist"
        if not full:
            local = new_local if is_new else old_local
            at = np.flatnonzero(ids == actual_id)
            arms[name]["local_pool_score_rank"] = (int(1 + np.count_nonzero((local > local[at[0]]) |
                ((local == local[at[0]]) & (ids < actual_id)))) if len(at) else None)
    randoms = {}
    for kind in ("random_red_shared_blue", "random_complete"):
        summaries = []
        for rep in range(contract["body"]["random_repetitions"]):
            random_ids = np.asarray(_sample_lex_ids(seed_material=seed(row["issue"], kind, rep), count=100))
            rng = np.random.default_rng(int.from_bytes(seed(row["issue"], kind + "blue", rep), "big"))
            assigned = blues if kind == "random_red_shared_blue" else rng.integers(1, 17, 100).tolist()
            # Retain full random IDs and labels; omit redundant swap matrices.
            random_pool = space[random_ids]
            hit = np.isin(random_pool, np.asarray(row["red"]) - 1).sum(axis=1)
            tier = [prize_tier(red_hits=int(h), blue_hit=int(b) == row["blue"]) for h, b in zip(hit, assigned)]
            missing = any(t in (1, 2) for t in tier)
            gross = sum({0:0, 3:3000, 4:200, 5:10, 6:5}.get(t, 0) for t in tier)
            summaries.append({"ticket_ids": random_ids.tolist(), "blue_by_rank": assigned,
                "max_red_hits": int(hit.max()), "hit_counts_0_to_6": np.bincount(hit, minlength=7).tolist(),
                "tier_counts_0_to_6": np.bincount(tier, minlength=7).tolist(),
                "pretax_net_cny": None if missing else gross - 200})
        randoms[kind] = summaries
    return seal("PredictionLearningIssue", {"contract_digest": contract["artifact_digest"],
        "issue": row["issue"], "index": index, "train_end_issue": rows[index - 1]["issue"],
        "label_red": y[index].tolist(), "label_blue": row["blue"],
        "blue_probabilities": [1 / 16] * 16, "old_model_digest": old_model["artifact_digest"],
        "old_pool_seed": pool_seed, "old_pool_ids": ids.tolist(),
        "probabilities": {k: q.tolist() for k, q in all_q.items()},
        "log_loss_nats_per_number": {k: loss(y[index], q) for k, q in all_q.items()},
        "arms": arms, "random": randoms})


def probe():
    start = time.monotonic()
    space = combinations()
    q = np.full(33, 6 / 33)
    q[0] += 0.01
    q[1] -= 0.01
    s = scores(q, space)
    ids = ordered(np.arange(len(space)), s, 10000)
    diverse(ids, s[ids], space[ids])
    elapsed = time.monotonic() - start
    return {"synthetic_only": True, "legal_space": len(space), "seconds": elapsed,
            "peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
            "score_digest": hashlib.sha256(s.tobytes()).hexdigest()}
