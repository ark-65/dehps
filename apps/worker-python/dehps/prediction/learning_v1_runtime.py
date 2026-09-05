"""Offline experiment persistence and bounded execution, separate from Formal P3."""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
import multiprocessing
import os
import resource
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from dehps.prediction import learning_v1 as core

SOURCE_PATHS = (
    "apps/worker-python/dehps/prediction/learning_v1.py",
    "apps/worker-python/dehps/prediction/learning_v1_runtime.py",
    "apps/worker-python/dehps/prediction/learning_v1_mainline.py",
    "apps/worker-python/scripts/run_prediction_learning_v1.py",
    "docs/experiments/2026-09-05-prediction-learning-v1-contract.md",
)


def source_identity(root):
    # Bind reused Python modules too; runtime dependencies may not silently drift.
    paths = sorted(set(SOURCE_PATHS) | {str(p.relative_to(root)) for p in (root / "apps/worker-python/dehps").rglob("*.py")})
    return {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in paths}


def snapshot(production_root, output):
    from dehps.db import get_connection
    from dehps.research_os.information_theory.measurement_system_v2 import forward_prequential_confirmatory as formal
    if (output / "snapshot.json").exists():
        return core.read(output / "snapshot.json")
    source = formal.load_source_contract(root_dir=production_root)
    with get_connection() as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        records = connection.execute("SELECT issue,draw_date,red_numbers,blue_number,source FROM ssq_history ORDER BY issue").fetchall()
        rows = [{"issue": str(r[0]), "draw_date": r[1].isoformat(), "red": list(r[2]),
                 "blue": r[3], "source": r[4]} for r in records]
        core.validate_rows(rows, today=datetime.now(timezone.utc).date().isoformat())
        registered = connection.execute(
            "SELECT artifact_path,artifact_digest FROM research_os_mainline_artifacts WHERE task_key=%s AND artifact_type=%s",
            (formal.PREREGISTRATION_TASK_KEY, formal.PREREGISTRATION_ARTIFACT_TYPE)).fetchall()
        assert len(registered) == 1, "canonical preregistration must be unique"
    path = (production_root / registered[0][0]).resolve()
    assert path.is_relative_to(production_root)
    prereg = formal.validate_artifact(json.loads(path.read_text()))
    assert prereg["artifact_digest"] == registered[0][1]
    value = core.seal("PredictionLearningSnapshot", {"rows": rows, "formal_source": source,
        "formal_preregistration": prereg, "availability": "historical draw date, exploratory reuse",
        "snapshot_at": datetime.now(timezone.utc).isoformat(), "production_read_only": True})
    core.immutable(output / "snapshot.json", value)
    return value


def freeze(root, output):
    snap = core.read(output / "snapshot.json")
    if (output / "contract.json").exists():
        value = core.read(output / "contract.json")
        assert value["body"]["source"] == source_identity(root), "frozen experiment code changed"
        return value
    measurement = core.probe()
    count = len(snap["body"]["rows"]) - core.MINIMUM
    # Conservative ceiling before viewing any scores. Keep all issues if feasible.
    workers = min(4, max(1, (os.cpu_count() or 2) // 2))
    estimate = count * max(5.0, measurement["seconds"] * 12) / workers
    assert estimate < 23 * 3600, "full diagnostic coverage exceeds round budget"
    rows = snap["body"]["rows"]
    value = core.seal("PredictionLearningContract", {
        "goal": core.GOAL, "run_id": "20260905-first-round", "snapshot_digest": snap["artifact_digest"],
        "source": source_identity(root), "candidate_configurations": list(core.CONFIGS),
        "candidate_limit": 24, "candidate_count": 4, "primary_model": "shrink900",
        "outer_issues": [r["issue"] for r in rows[core.MINIMUM:]], "minimum_training": core.MINIMUM,
        "seed": core.SEED, "workers": workers, "nested_threads": 1,
        "wall_seconds": 86400, "random_repetitions": 32, "bootstrap_repetitions": 4000,
        "runtime_versions": {"python": sys.version, "numpy": np.__version__},
        "bootstrap_block_length": 13, "primary_family_contrasts": 8,
        "primary_metric": "mean across issues of mean across 33 Bernoulli log losses, nats",
        "examples": [rows[core.MINIMUM]["issue"], rows[core.MINIMUM + count // 2]["issue"], rows[-1]["issue"]],
        "evidence": "EXPLORATORY_HISTORICAL_WALK_FORWARD", "probe": measurement,
        "estimated_seconds_conservative": estimate, "frozen_at": datetime.now(timezone.utc).isoformat(),
        "formal_changes": False, "blue_strategy": "existing shared deterministic uniform by rank",
        "stop_rule": "24h across resumes, four configs once, no next round, no outer retuning"})
    core.immutable(output / "contract.json", value)
    return value


def append_event(output, value):
    path = output / "attempts.jsonl"
    with path.open("ab") as stream:
        stream.write(core.raw({"at": datetime.now(timezone.utc).isoformat(), **value}) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())


def formal_busy():
    result = subprocess.run(["systemctl", "--user", "show", "dehps-forward-prequential-successor.service",
        "-p", "ActiveState", "--value"], capture_output=True, text=True, check=True)
    return result.stdout.strip() in ("active", "activating", "reloading")


def run_training(root, output):
    contract = core.read(output / "contract.json")
    assert contract["body"]["source"] == source_identity(root)
    snap = core.read(output / "snapshot.json")
    assert snap["artifact_digest"] == contract["body"]["snapshot_digest"]
    start_path = output / "start.json"
    if not start_path.exists():
        core.immutable(start_path, core.seal("PredictionLearningStart", {"epoch": time.time(),
                       "contract_digest": contract["artifact_digest"], "configurations_counted": 4}))
    start = core.read(start_path)["body"]["epoch"]
    deadline = start + contract["body"]["wall_seconds"]
    rows = snap["body"]["rows"]
    output.joinpath("issues").mkdir(exist_ok=True)
    remaining = []
    for index in range(core.MINIMUM, len(rows)):
        path = output / "issues" / (rows[index]["issue"] + ".json")
        if path.exists():
            body = core.read(path)["body"]
            assert body["contract_digest"] == contract["artifact_digest"] and body["index"] == index
        else:
            remaining.append(index)
    workers = contract["body"]["workers"]
    # Each completed part is published once. Nothing reuses another run's files.
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers,
            mp_context=multiprocessing.get_context("spawn"), initializer=core.init_worker,
            initargs=(str(output / "snapshot.json"), str(output / "contract.json"))) as executor:
        pending = {}
        iterator = iter(remaining)
        exhausted = False
        while pending or not exhausted:
            if time.time() >= deadline:
                append_event(output, {"event": "BUDGET_EXHAUSTED", "pending": len(pending)})
                raise TimeoutError("first round wall-clock budget exhausted; no automatic second round")
            busy = formal_busy()
            while not busy and not exhausted and len(pending) < workers:
                index = next(iterator, None)
                if index is None:
                    exhausted = True
                    break
                append_event(output, {"event": "ISSUE_STARTED", "issue": rows[index]["issue"], "index": index})
                pending[executor.submit(core.evaluate_issue, index)] = (index, time.monotonic())
            if not pending:
                if exhausted:
                    break
                time.sleep(10)
                continue
            done, _ = concurrent.futures.wait(pending, timeout=10,
                                             return_when=concurrent.futures.FIRST_COMPLETED)
            for future in done:
                index, began = pending.pop(future)
                try:
                    value = future.result()
                except Exception as exc:
                    append_event(output, {"event": "ISSUE_FAILED", "index": index, "error": repr(exc)})
                    raise
                core.immutable(output / "issues" / (rows[index]["issue"] + ".json"), value)
                append_event(output, {"event": "ISSUE_COMPLETED", "issue": rows[index]["issue"],
                    "artifact_digest": value["artifact_digest"], "seconds": time.monotonic() - began})
    all_y = core.targets(rows)
    _, trained = core.fit(all_y, core.CONFIGS[0])
    checkpoint = core.seal("PredictionLearningCheckpoint", {**trained, "status": "TRAINED_RESEARCH_ONLY",
        "goal": core.GOAL, "contract_digest": contract["artifact_digest"],
        "snapshot_digest": snap["artifact_digest"], "training_start_issue": rows[0]["issue"],
        "training_end_issue": rows[-1]["issue"], "version": "20260905-shrink900-v1",
        "blue_policy": "unchanged shared deterministic uniform by rank",
        "evidence_of_training_data_performance": False})
    core.immutable(output / "checkpoint.json", checkpoint)
    issues = [{"path": str(p.relative_to(root)), "artifact_digest": core.read(p)["artifact_digest"]}
              for p in sorted((output / "issues").glob("*.json"))]
    assert len(issues) == len(rows) - core.MINIMUM
    index_artifact = core.seal("PredictionLearningTraining", {"contract_digest": contract["artifact_digest"],
        "issues": issues, "checkpoint_digest": checkpoint["artifact_digest"],
        "trained_configurations": 4, "outer_issues": len(issues),
        "cold_start_rows": core.MINIMUM, "cold_start_status": "LABELS_RETAINED_INSUFFICIENT_PRIOR_HISTORY",
        "wall_seconds": time.time() - start,
        "cpu_seconds_parent": resource.getrusage(resource.RUSAGE_SELF).ru_utime,
        "cpu_seconds_children": resource.getrusage(resource.RUSAGE_CHILDREN).ru_utime,
        "peak_child_rss_mib": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024,
        "attempt_ledger_sha256": hashlib.sha256((output / "attempts.jsonl").read_bytes()).hexdigest()})
    core.immutable(output / "training.json", index_artifact)
    return index_artifact, checkpoint


def paired_interval(delta, *, seed, family=1):
    values = np.asarray(delta, dtype=float)
    rng = np.random.default_rng(seed)
    n, block, repetitions = len(values), 13, 4000
    result = np.empty(repetitions)
    for i in range(repetitions):
        starts = rng.integers(0, n, int(np.ceil(n / block)))
        indices = ((starts[:, None] + np.arange(block)) % n).ravel()[:n]
        result[i] = values[indices].mean()
    alpha = 0.05 / family
    return {"mean": float(values.mean()), "lower": float(np.quantile(result, alpha / 2)),
            "upper": float(np.quantile(result, 1 - alpha / 2)), "family": family,
            "method": "paired circular moving-block bootstrap length 13, 4000 replicates"}


def payouts(output, issue_values):
    """Fetch only required floating payouts, verify exact label identity; cache raw evidence."""
    from dehps.crawler.ssq_client import ZhcwSsqDataSource
    required = []
    for value in issue_values:
        rows = list(value["arms"].values()) + [r for a in value["random"].values() for r in a]
        if any(r["tier_counts_0_to_6"][1] or r["tier_counts_0_to_6"][2] for r in rows):
            required.append(value)
    amounts = {}
    for value in required:
        issue = value["issue"]
        path = output / "payouts" / (issue + ".json")
        if path.exists():
            record = core.read(path)["body"]["record"]
        else:
            record = ZhcwSsqDataSource().fetch_issue_with_prizes(issue)
            if record is None:
                raise ValueError(f"floating payout missing for {issue}")
            core.immutable(path, core.seal("PredictionLearningPayout", {"issue": issue, "record": record,
                "source": "https://jc.zhcw.com/port/client_json.php"}))
        actual = (np.flatnonzero(value["label_red"]) + 1).tolist()
        red = record.get("red", record.get("red_numbers"))
        red = list(map(int, red.replace(",", " ").split())) if isinstance(red, str) else list(red)
        assert sorted(red) == actual and int(record.get("blue", record.get("blue_number"))) == value["label_blue"]
        assert str(record.get("issue", record.get("code"))) == issue
        tiers = {int(r["awardEtc"]): float(r["baseBetWinner"]["awardMoney"]) for r in record["winnerDetails"]}
        assert set(tiers) == set(range(1, 7)) and all(np.isfinite(v) and v >= 0 for v in tiers.values())
        assert all(tiers[k] == v for k, v in {3:3000, 4:200, 5:10, 6:5}.items())
        amounts[issue] = tiers
    return amounts


def analyze(root, output):
    training = core.read(output / "training.json")
    contract = core.read(output / "contract.json")
    issue_values = []
    for item in training["body"]["issues"]:
        value = core.read(root / item["path"])
        assert value["artifact_digest"] == item["artifact_digest"]
        for arm in value["body"]["arms"].values():
            for key in ("swap_missing_extra_delta_bits", "ticket_ids", "blue_by_rank", "number_counts"):
                arm.pop(key, None)
        value["body"].pop("old_pool_ids")
        for repeats in value["body"]["random"].values():
            for repeat in repeats:
                repeat.pop("ticket_ids")
                repeat.pop("blue_by_rank")
        issue_values.append(value["body"])
    exact_payouts = payouts(output, issue_values)
    names = ("old", "uniform", *(c["name"] for c in core.CONFIGS))
    losses = {name: np.asarray([r["log_loss_nats_per_number"][name] for r in issue_values]) for name in names}
    probability = {}
    labels = np.asarray([r["label_red"] for r in issue_values])
    for name in names:
        p = np.asarray([r["probabilities"][name] for r in issue_values])
        bins = []
        edges = np.linspace(0, 1, 21)
        for j, (low, high) in enumerate(zip(edges[:-1], edges[1:])):
            mask = (p >= low) & ((p <= high) if j == 19 else (p < high))
            bins.append({"lower": float(low), "upper": float(high), "count": int(mask.sum()),
                "mean_predicted": float(p[mask].mean()) if mask.any() else None,
                "observed_frequency": float(labels[mask].mean()) if mask.any() else None})
        probability[name] = {"mean_log_loss": float(losses[name].mean()), "calibration": bins,
            "brier": float(((p - labels) ** 2).mean())}
        if name not in ("old", "uniform"):
            probability[name]["paired_vs_old"] = paired_interval(losses[name] - losses["old"], seed=core.SEED)
            probability[name]["family_vs_old"] = paired_interval(losses[name] - losses["old"], seed=core.SEED, family=8)
            probability[name]["family_vs_uniform"] = paired_interval(losses[name] - losses["uniform"], seed=core.SEED, family=8)
    arm_values = {}
    for name in (*core.ARMS, "random_red_shared_blue", "random_complete"):
        net, maximum, hits = [], [], []
        for issue in issue_values:
            rows = issue["random"][name] if name.startswith("random") else [issue["arms"][name]]
            amounts = exact_payouts.get(issue["issue"], {1:0, 2:0, 3:3000, 4:200, 5:10, 6:5})
            net.append(float(np.mean([sum(r["tier_counts_0_to_6"][k] * amounts[k] for k in range(1,7)) - 200 for r in rows])))
            maximum.append(float(np.mean([r["max_red_hits"] for r in rows])))
            hits.append(np.mean([r["hit_counts_0_to_6"] for r in rows], axis=0))
        arm_values[name] = {"net": np.asarray(net), "maximum": np.asarray(maximum), "hits": np.asarray(hits)}
    ticket_results = {}
    for name, values in arm_values.items():
        ticket_results[name] = {"mean_net_cny_per_issue": float(values["net"].mean()),
            "total_net_cny": float(values["net"].sum()), "roi": float(values["net"].mean() / 200),
            "mean_max_red_hits": float(values["maximum"].mean()),
            "hit_counts_per_100_tickets": values["hits"].mean(axis=0).tolist(),
            "paired_net_vs_old": paired_interval(values["net"] - arm_values["old_original"]["net"], seed=core.SEED),
            "paired_max_hits_vs_old": paired_interval(values["maximum"] - arm_values["old_original"]["maximum"], seed=core.SEED)}
        if not name.startswith("random"):
            rows = [r["arms"][name] for r in issue_values]
            ticket_results[name].update({"candidate_coverage": float(np.mean([r["winning_in_candidate_pool"] for r in rows])),
                "top100_coverage": float(np.mean([r["winning_in_top100"] for r in rows])),
                "mean_pairwise_overlap": float(np.mean([r["mean_pairwise_red_overlap"] for r in rows])),
                "mean_max_number_share": float(np.mean([r["max_number_share"] for r in rows])),
                "mean_full_space_rank": float(np.mean([r["full_space_score_rank"] for r in rows]))})
    primary = probability["shrink900"]
    improved = all(primary[k]["upper"] < 0 for k in ("family_vs_old", "family_vs_uniform"))
    conclusion = ("有改进证据（仅历史探索性 log-loss）" if improved else
        "未观察到改进" if primary["mean_log_loss"] >= probability["old"]["mean_log_loss"] else "证据不足")
    report = core.seal("PredictionLearningAnalysis", {"contract_digest": contract["artifact_digest"],
        "training_digest": training["artifact_digest"], "probability": probability, "tickets": ticket_results,
        "conclusion": conclusion, "evidence": "EXPLORATORY_HISTORICAL_WALK_FORWARD",
        "payout_issues": sorted(exact_payouts), "issue_count": len(issue_values),
        "examples": [{"issue": r["issue"], "old_loss": r["log_loss_nats_per_number"]["old"],
            "new_loss": r["log_loss_nats_per_number"]["shrink900"],
            "old_first_rejection": r["arms"]["old_original"]["first_rejection"],
            "new_first_rejection": r["arms"]["new_original"]["first_rejection"],
            "old_global_rank": r["arms"]["old_original"]["full_space_score_rank"],
            "new_global_rank": r["arms"]["new_original"]["full_space_score_rank"],
            "old_max_red_hits": r["arms"]["old_original"]["max_red_hits"],
            "new_max_red_hits": r["arms"]["new_original"]["max_red_hits"]}
            for r in issue_values if r["issue"] in contract["body"]["examples"]]})
    core.immutable(output / "analysis.json", report)
    return report


def semantic_replay(root, output):
    contract = core.read(output / "contract.json")
    snapshot = core.read(output / "snapshot.json")
    training = core.read(output / "training.json")
    y = core.targets(snapshot["body"]["rows"])
    samples = set(contract["body"]["examples"])
    core.init_worker(output / "snapshot.json", output / "contract.json")
    checked = []
    for item in training["body"]["issues"]:
        value = core.read(root / item["path"])
        assert value["artifact_digest"] == item["artifact_digest"]
        body, index = value["body"], value["body"]["index"]
        assert body["label_red"] == y[index].tolist()
        assert body["label_blue"] == snapshot["body"]["rows"][index]["blue"]
        old = list(map(float, core.formal.estimate_legal_marginals(
            list(map(int, y[:index].sum(axis=0))), training_issue_count=index)))
        assert old == body["probabilities"]["old"]
        assert core.loss(y[index], old) == body["log_loss_nats_per_number"]["old"]
        assert body["probabilities"]["uniform"] == [6 / 33] * 33
        for config in core.CONFIGS:
            q = core.fit(y[:index], config)[0]
            assert q.tolist() == body["probabilities"][config["name"]]
            assert core.loss(y[index], q) == body["log_loss_nats_per_number"][config["name"]]
        if body["issue"] in samples:
            assert core.evaluate_issue(index) == value, "complete selected-issue semantic replay changed"
            checked.append(body["issue"])
    checkpoint = core.read(output / "checkpoint.json")
    _, fitted = core.fit(y, core.CONFIGS[0])
    assert all(checkpoint["body"][k] == v for k, v in fitted.items())
    original_analysis = core.read(output / "analysis.json")
    assert analyze(root, output) == original_analysis
    if (output / "experimental-top100.json").exists():
        predicted = core.read(output / "experimental-top100.json")["body"]
        assert predicted["checkpoint_digest"] == checkpoint["artifact_digest"]
        q = np.asarray(checkpoint["body"]["probabilities"])
        space = core.combinations()
        s = core.scores(q, space)
        ids = core.ordered(np.arange(len(space)), s, 10000)
        selected = core.diverse(ids, s[ids], space[ids])
        blues = core.formal._blue_numbers(preregistration_digest=snapshot["body"]["formal_preregistration"]["artifact_digest"], target_issue=predicted["target_issue"])
        assert predicted["tickets"] == [{"rank": rank + 1, "red": (space[i] + 1).tolist(), "blue": blues[rank]} for rank, i in enumerate(selected)]
    return core.seal("PredictionLearningSemanticReplay", {
        "status": "REPLAY_VERIFIED", "contract_digest": contract["artifact_digest"],
        "training_digest": training["artifact_digest"], "analysis_digest": original_analysis["artifact_digest"],
        "all_issue_file_digests_verified": len(training["body"]["issues"]),
        "all_candidate_probabilities_and_losses_recomputed": True,
        "full_ticket_generation_recomputed_issues": sorted(checked),
        "checkpoint_refit_verified": True, "analysis_recomputed": True,
        "scope": "all registered identities and model/metric computations; complete ticket replay at frozen first/middle/last issues"})


def experimental_prediction(output):
    from datetime import date
    from dehps.db import get_connection
    path = output / "experimental-top100.json"
    if path.exists():
        return core.read(path)
    snapshot = core.read(output / "snapshot.json")["body"]
    checkpoint = core.read(output / "checkpoint.json")
    rows = snapshot["rows"]
    with get_connection() as connection:
        connection.execute("SET TRANSACTION READ ONLY")
        latest = connection.execute("SELECT max(issue) FROM ssq_history").fetchone()[0]
    assert latest == rows[-1]["issue"], "new data arrived after snapshot; do not silently refit or label a stale target"
    history = [(r["issue"], date.fromisoformat(r["draw_date"]), tuple(r["red"])) for r in rows]
    moment = datetime.now(core.formal.SHANGHAI)
    issue, day, deadline, official = core.formal.target_for_now(history, moment=moment)
    assert issue > latest and moment < official
    q = np.asarray(checkpoint["body"]["probabilities"])
    space = core.combinations()
    s = core.scores(q, space)
    ids = core.ordered(np.arange(len(space)), s, 10000)
    selected = core.diverse(ids, s[ids], space[ids])
    blues = core.formal._blue_numbers(preregistration_digest=snapshot["formal_preregistration"]["artifact_digest"], target_issue=issue)
    result = core.seal("PredictionLearningExperimentalTop100", {"status": "RESEARCH_ONLY",
        "checkpoint_digest": checkpoint["artifact_digest"], "target_issue": issue,
        "draw_date": day.isoformat(), "generated_at": moment.isoformat(),
        "training_end_issue": latest, "candidate_score_space": len(space), "selection_shortlist": 10000,
        "score": "marginal composite log2 score, no learned joint structure",
        "selector": "combined_diverse; secondary experimental arm, no promotion",
        "tickets": [{"rank": rank + 1, "red": (space[identifier] + 1).tolist(), "blue": blues[rank]}
                    for rank, identifier in enumerate(selected)],
        "formal_prediction_changed": False, "mail_sent": False})
    core.immutable(path, result)
    return result


def render_report(output, integration):
    analysis = core.read(output / "analysis.json")["body"]
    training = core.read(output / "training.json")["body"]
    contract = core.read(output / "contract.json")
    rows = core.read(output / "snapshot.json")["body"]["rows"]
    lines = ["# Prediction learning v1 — first offline round", "", analysis["conclusion"], "",
        f"Data: {rows[0]['issue']}–{rows[-1]['issue']}, {len(rows)} complete red/blue labels. "
        f"{analysis['issue_count']} chronological outer predictions after 900 warm-up draws.",
        "All results are exploratory reuse of researched history. No new independent or confirmatory test set.",
        "The old policy is reconstructed with its frozen estimator and original sampler; these historical reconstructions are not original predraw records.", "",
        f"Contract: `{contract['artifact_digest']}`. Primary model fixed before results: shrink900. Four candidate configurations; no outer selection.",
        "Marginal counts only, no joint structure learned. Shrinkage counts are actual fitted sufficient statistics; checkpoint is trained on all snapshot rows and is RESEARCH_ONLY.", "",
        "| Model | log-loss (nats/number/issue) | delta vs old | family interval vs old | family interval vs uniform |",
        "| --- | ---: | ---: | --- | --- |"]
    for name, p in analysis["probability"].items():
        old, uniform = p.get("family_vs_old"), p.get("family_vs_uniform")
        lines.append(f"| {name} | {p['mean_log_loss']:.9f} | " +
            (f"{old['mean']:+.9f} | [{old['lower']:+.9f}, {old['upper']:+.9f}] | [{uniform['lower']:+.9f}, {uniform['upper']:+.9f}] |" if old else "— | — | — |"))
    lines += ["", "Intervals: paired circular blocks of 13 issues, 4,000 resamples; eight primary contrasts use Bonferroni family intervals. Calibration bins and Brier scores are in analysis.json.", "",
        "| Ticket arm | mean max red hits | mean net CNY / issue | pretax ROI | candidate coverage | mean pairwise overlap |",
        "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for name, p in analysis["tickets"].items():
        lines.append(f"| {name} | {p['mean_max_red_hits']:.4f} | {p['mean_net_cny_per_issue']:.2f} | {p['roi']:.2%} | {p.get('candidate_coverage', 'random')} | {p.get('mean_pairwise_overlap', 'random')} |")
    lines += ["", "Read single-factor comparisons first: new_original vs old_original (probabilities); old_full vs old_original (coverage); old_diverse vs old_original (selection). new_full and combined_diverse are secondary combined arms.",
        "All red-selection arms share the original blue-by-rank vector. Each random arm uses 32 groups per issue, averaged before paired comparisons. Complete random blue is separate. Cost is 200 CNY per 100-ticket group. Returns are simulated pretax amounts, not a forecast of profit.",
        "Floating first/second prizes are retrieved for exact required issues and matched to labels; raw evidence is cached under payouts/. Fixed tiers use the existing payout contract. All hit bins and paired net/hit intervals are in analysis.json.",
        "Full-space ranks cover all 1,107,568 red combinations. Original candidate ranks cover only 10,000. Combined diversity optimizes a declared top-10,000 shortlist, not the full space.", "", "## Prespecified error examples"]
    for e in analysis["examples"]:
        lines += ["", f"- {e['issue']}: original first rejection = {e['old_first_rejection']}; new = {e['new_first_rejection']}. "
            f"Global winning ranks old/new: {e['old_global_rank']}/{e['new_global_rank']}; best red hits: {e['old_max_red_hits']}/{e['new_max_red_hits']}; "
            f"per-number loss: {e['old_loss']:.8f}/{e['new_loss']:.8f}."]
    lines += ["", "Each issue file retains all probabilities and labels, all selected tickets, every omitted/extra-ball replacement score delta, candidate pool IDs, overlap, concentration and hit counts. Warm-up labels remain in snapshot.json with explicit insufficient-history status.", "",
        f"Resources: {training['wall_seconds']:.1f} s wall; {training['cpu_seconds_children']:.1f} s child CPU; peak child RSS {training['peak_child_rss_mib']:.1f} MiB; {contract['body']['workers']} workers, one BLAS thread each. Full append-only attempts: attempts.jsonl.",
        "Checkpoint: checkpoint.json; counts, prior, effective mass, data end and all 33 probabilities are versioned and digest-bound. Its fitted-data performance is not a reported OOS result.", "", "## Integration matrix", "",
        "| Surface | Evidence |", "| --- | --- |",
        "| Goal / DAG / resolver / Ready Queue | experiment DB manifest and before/after snapshots |",
        "| Unified Supervisor / immutable executions | freeze -> train-evaluate -> analysis, registered execution IDs |",
        "| Upstream / downstream artifacts | snapshot, frozen contract, training index, checkpoint, analysis registrations |",
        "| Status / next consumer | learning-status.json; completed predecessor makes next phase Ready |",
        "| Evidence / decision | exploratory frozen comparisons, zero Formal P3 gate credit |",
        "| Replay | replay.json and semantic-replay.json: all identities, all new-model predictions/losses, checkpoint and report; full ticket regeneration on three frozen examples |",
        "| Production scope | isolated DB and directory; no production mutation, service restart, mail or promotion |", "",
        integration, "", "Engineering integration and predictive improvement are separate findings. Log-loss evidence cannot substitute for hit or return evidence."]
    (output / "report.md").write_text("\n".join(lines) + "\n")
