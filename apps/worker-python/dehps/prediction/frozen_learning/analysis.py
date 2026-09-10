"""Preserved numerical analysis with explicit artifact and payout inputs.

No filesystem publication, live data access or crawler fallback occurs here.
Runtime authority, persistence and resource accounting belong to the capability.
"""
from copy import deepcopy
import numpy as np
from . import calculation as core

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


def payouts(issue_values, payout_records):
    """Use only supplied frozen payout evidence; verify exact label identity."""
    required = []
    for value in issue_values:
        rows = list(value["arms"].values()) + [r for a in value["random"].values() for r in a]
        if any(r["tier_counts_0_to_6"][1] or r["tier_counts_0_to_6"][2] for r in rows):
            required.append(value)
    amounts = {}
    for value in required:
        issue = value["issue"]
        record = core.verify(payout_records[issue])["body"]["record"]
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


def analyze(contract, training, read_issue, payout_records):
    issue_values = []
    for item in training["body"]["issues"]:
        value = core.verify(deepcopy(read_issue(item["artifact_digest"])))
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
    exact_payouts = payouts(issue_values, payout_records)
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
    return report


def refit_checkpoint(snapshot, contract):
    snap = snapshot
    rows = snapshot["body"]["rows"]
    all_y = core.targets(rows)
    _, trained = core.fit(all_y, core.CONFIGS[0])
    checkpoint = core.seal("PredictionLearningCheckpoint", {**trained, "status": "TRAINED_RESEARCH_ONLY",
        "goal": core.GOAL, "contract_digest": contract["artifact_digest"],
        "snapshot_digest": snap["artifact_digest"], "training_start_issue": rows[0]["issue"],
        "training_end_issue": rows[-1]["issue"], "version": "20260905-shrink900-v1",
        "blue_policy": "unchanged shared deterministic uniform by rank",
        "evidence_of_training_data_performance": False})
    return checkpoint
