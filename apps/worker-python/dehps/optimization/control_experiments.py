from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Iterable, Literal

from dehps.config import ROOT_DIR
from dehps.models.frequency_ranker import FrequencyRankerConfig, HistoryDraw, history_draw_date, history_issue, history_numbers
from dehps.optimization.walk_forward import (
    TargetRank,
    build_ranked_universe,
    create_worker_pool,
    fingerprint_history,
    normalize_worker_count,
    rank_target_grid_with_red5,
)
from scripts.run_training_supervisor import (
    ALL_FIELDS,
    attach_frozen_validation,
    clamp_config,
    config_dict,
    control_experiment_configs,
    frozen_validation_window,
    reward_summary,
    summarize_rank_quality,
    summarize_target_ranks,
)


CandidateSource = Literal["kdj", "neural", "config-json"]
TrainMode = Literal["expanding", "rolling"]
CONTROL_LABELS = (
    "current_best_frozen_baseline",
    "default_baseline",
    "structural_baseline",
    "frequency_baseline",
    "omission_baseline",
    "null_baseline",
    "random_same_budget",
)
GUARDRAIL_LANGUAGE = (
    "Guardrail: this is a frozen control experiment, not a prediction claim. "
    "Promotion is blocked unless the candidate beats every fixed control on the same target issues "
    "and does not worsen tail risk against the current best frozen baseline; future unseen draws remain required."
)


@dataclass(frozen=True)
class LoadedCandidate:
    label: str
    source: CandidateSource
    config: FrequencyRankerConfig | None
    fixed_ranked_candidates: tuple[tuple[int, tuple[int, ...], float], ...] = ()
    metadata: dict | None = None


def parse_random_seeds(value: str | Iterable[int] | None) -> tuple[int, ...]:
    if value is None:
        return (11, 23, 37)
    if isinstance(value, str):
        seeds = tuple(int(item.strip()) for item in value.split(",") if item.strip())
        return seeds or (11, 23, 37)
    seeds = tuple(int(item) for item in value)
    return seeds or (11, 23, 37)


def fixed_control_labels() -> tuple[str, ...]:
    return CONTROL_LABELS


def protocol_snapshot(
    *,
    as_of_issue: str,
    history_fingerprint_value: str,
    train_mode: TrainMode,
    train_window: int,
    eval_window: int,
    top_n: int,
    universe_size: int,
    target_issues: list[str],
    random_seeds: tuple[int, ...],
) -> dict:
    return {
        "as_of_issue": as_of_issue,
        "history_fingerprint": history_fingerprint_value,
        "train_mode": train_mode,
        "train_window": train_window,
        "eval_window": eval_window,
        "top_n": top_n,
        "universe_size": universe_size,
        "target_issues": target_issues,
        "random_seeds": list(random_seeds),
        "control_labels": list(CONTROL_LABELS),
        "protocol_equality": {
            "same_universe": True,
            "same_target_issues": True,
            "same_top_n": True,
            "same_train_eval_protocol": True,
        },
    }


def load_config_json_candidate(path: Path) -> LoadedCandidate:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError("--config-json must point to a JSON object")
    raw_config = payload.get("config") or payload.get("candidate_config") or payload.get("best_config") or payload
    if not isinstance(raw_config, dict):
        raise ValueError("config-json payload must be a config object or contain config/candidate_config/best_config")
    values = config_dict(FrequencyRankerConfig())
    unknown = sorted(set(raw_config) - set(values))
    if unknown:
        raise ValueError(f"unknown config fields: {', '.join(unknown)}")
    values.update({field: float(raw_config[field]) for field in raw_config if field in values})
    return LoadedCandidate(
        label=str(payload.get("label") or "candidate_config_json"),
        source="config-json",
        config=clamp_config(FrequencyRankerConfig(**values)),
        metadata={"path": str(path), "unknown_fields": []},
    )


def load_neural_candidate(path: Path, *, top_n: int) -> LoadedCandidate:
    payload = json.loads(path.read_text())
    scoring = payload.get("scoring") if isinstance(payload.get("scoring"), dict) else {}
    raw_candidates = scoring.get("top_candidates") if isinstance(scoring, dict) else None
    if not isinstance(raw_candidates, list):
        raise ValueError("neural candidate JSON must contain scoring.top_candidates")
    candidates: list[tuple[int, tuple[int, ...], float]] = []
    for item in raw_candidates[:top_n]:
        if not isinstance(item, dict) or not isinstance(item.get("numbers"), list):
            continue
        candidates.append(
            (
                int(item.get("rank") or len(candidates) + 1),
                tuple(int(number) for number in item["numbers"]),
                float(item.get("score") or 0.0),
            )
        )
    if not candidates:
        raise ValueError("neural candidate JSON does not contain usable top candidates")
    return LoadedCandidate(
        label="candidate_neural_fixed_budget",
        source="neural",
        config=None,
        fixed_ranked_candidates=tuple(candidates),
        metadata={
            "path": str(path),
            "scorer_key": scoring.get("scorer_key"),
            "mode": "fixed_ranked_candidate_set",
        },
    )


def latest_neural_candidate_path(output_dir: Path) -> Path:
    paths = sorted(output_dir.glob("neural-feasibility-*.json"))
    if not paths:
        raise ValueError(f"no neural-feasibility-*.json files found in {output_dir}")
    return paths[-1]


def target_indexes(*, history_len: int, train_window: int, eval_window: int) -> range:
    if train_window < 1:
        raise ValueError("train_window must be at least 1")
    if eval_window < 1:
        raise ValueError("eval_window must be at least 1")
    if history_len <= train_window:
        raise ValueError("history must contain more rows than train_window")
    start = max(train_window, history_len - eval_window)
    return range(start, history_len)


def _target_rank_from_ranked_target(
    *,
    issue: str,
    draw_date,
    red_numbers: tuple[int, ...],
    ranked_target: tuple[int, float, object | None],
) -> TargetRank:
    rank, score, red5_match = ranked_target
    return TargetRank(
        issue=issue,
        rank=rank,
        score=score,
        hit_top_100=rank <= 100,
        hit_top_1000=rank <= 1000,
        hit_top_10000=rank <= 10000,
        draw_date=draw_date,
        red_numbers=red_numbers,
        red5_rank=red5_match.rank if red5_match else None,
        red5_score=red5_match.score if red5_match else None,
        red5_numbers=red5_match.numbers if red5_match else None,
        red5_missing_number=red5_match.missing_number if red5_match else None,
        red5_extra_number=red5_match.extra_number if red5_match else None,
        hit_red5_top_100=red5_match is not None and red5_match.rank <= 100,
        hit_red5_top_1000=red5_match is not None and red5_match.rank <= 1000,
        hit_red5_top_10000=red5_match is not None and red5_match.rank <= 10000,
    )


def evaluate_config_summaries(
    *,
    history: list[HistoryDraw],
    ranked_universe,
    labeled_configs: tuple[tuple[str, FrequencyRankerConfig], ...],
    train_window: int,
    train_mode: TrainMode,
    eval_window: int,
    top_n: int,
    workers: int,
) -> list[dict]:
    indexes = list(target_indexes(history_len=len(history), train_window=train_window, eval_window=eval_window))
    target_rank_lists: list[list[TargetRank]] = [[] for _ in labeled_configs]
    configs = tuple(config for _label, config in labeled_configs)
    pool = create_worker_pool(workers, ranked_universe)
    try:
        for target_index in indexes:
            train_start = 0 if train_mode == "expanding" else max(0, target_index - train_window)
            train_history = history[train_start:target_index]
            target_draw = history[target_index]
            ranked_targets = rank_target_grid_with_red5(
                target_numbers=history_numbers(target_draw),
                train_history=train_history,
                configs=configs,
                ranked_universe=ranked_universe,
                target_draw_date=history_draw_date(target_draw),
                workers=workers,
                pool=pool,
            )
            for config_index, ranked_target in enumerate(ranked_targets):
                target_rank_lists[config_index].append(
                    _target_rank_from_ranked_target(
                        issue=history_issue(target_draw),
                        draw_date=history_draw_date(target_draw),
                        red_numbers=history_numbers(target_draw),
                        ranked_target=ranked_target,
                    )
                )
    finally:
        if pool is not None:
            pool.close()
            pool.join()

    as_of_issue = history_issue(history[-1])
    history_fingerprint_value = fingerprint_history(history)
    summaries = []
    for (label, config), target_ranks in zip(labeled_configs, target_rank_lists, strict=True):
        summary = summarize_target_ranks(
            target_ranks=target_ranks,
            config=config,
            as_of_issue=as_of_issue,
            history_fingerprint_value=history_fingerprint_value,
            train_window=train_window,
            train_mode=train_mode,
            top_n=top_n,
            universe_size=len(ranked_universe),
        )
        summary["label"] = label
        summary["protocol_key"] = protocol_key(summary)
        summaries.append(summary)
    attach_frozen_validation(
        summaries,
        validation_window=frozen_validation_window(eval_window),
        universe_size=len(ranked_universe),
    )
    return summaries


def evaluate_fixed_candidate_set(
    *,
    candidate: LoadedCandidate,
    history: list[HistoryDraw],
    universe_size: int,
    train_window: int,
    train_mode: TrainMode,
    eval_window: int,
    top_n: int,
) -> dict:
    candidate_rank_by_numbers = {
        numbers: rank
        for rank, numbers, _score in candidate.fixed_ranked_candidates[:top_n]
    }
    target_ranks: list[TargetRank] = []
    for target_index in target_indexes(history_len=len(history), train_window=train_window, eval_window=eval_window):
        target_draw = history[target_index]
        numbers = history_numbers(target_draw)
        rank = candidate_rank_by_numbers.get(numbers, universe_size + 1)
        target_ranks.append(
            TargetRank(
                issue=history_issue(target_draw),
                rank=rank,
                score=0.0,
                hit_top_100=rank <= 100,
                hit_top_1000=rank <= 1000,
                hit_top_10000=rank <= 10000,
                draw_date=history_draw_date(target_draw),
                red_numbers=numbers,
            )
        )
    summary = summarize_target_ranks(
        target_ranks=target_ranks,
        config=FrequencyRankerConfig(),
        as_of_issue=history_issue(history[-1]),
        history_fingerprint_value=fingerprint_history(history),
        train_window=train_window,
        train_mode=train_mode,
        top_n=top_n,
        universe_size=universe_size,
    )
    summary["label"] = candidate.label
    summary["candidate_source"] = candidate.source
    summary["candidate_metadata"] = candidate.metadata or {}
    summary["config"] = None
    summary["config_hash"] = "fixed-candidate-set"
    summary["protocol_key"] = protocol_key(summary)
    attach_frozen_validation([summary], validation_window=frozen_validation_window(eval_window), universe_size=universe_size)
    return summary


def protocol_key(summary: dict) -> dict:
    return {
        "as_of_issue": summary.get("as_of_issue"),
        "history_fingerprint": summary.get("history_fingerprint"),
        "evaluated_draws": summary.get("evaluated_draws"),
    }


def random_same_budget_summary(
    *,
    evaluated_draws: int,
    universe_size: int,
    top_n: int,
    random_seeds: tuple[int, ...],
) -> dict:
    safe_universe = max(1, universe_size)
    cutoffs = {
        "top_100": min(100, top_n, safe_universe),
        "top_1000": min(1000, top_n, safe_universe),
        "top_10000": min(10000, top_n, safe_universe),
        "top_n": min(top_n, safe_universe),
    }
    analytical = {
        name: {
            "hit_rate": cutoff / safe_universe,
            "expected_hits": evaluated_draws * cutoff / safe_universe,
        }
        for name, cutoff in cutoffs.items()
    }
    simulations = []
    for seed in random_seeds:
        rng = random.Random(seed)
        ranks = [rng.randint(1, safe_universe) for _ in range(evaluated_draws)]
        summary = {
            "label": "random_same_budget",
            "evaluated_draws": evaluated_draws,
            "top_100_hits": sum(rank <= cutoffs["top_100"] for rank in ranks),
            "top_1000_hits": sum(rank <= cutoffs["top_1000"] for rank in ranks),
            "top_10000_hits": sum(rank <= cutoffs["top_10000"] for rank in ranks),
            "median_rank": sorted(ranks)[len(ranks) // 2] if ranks else None,
            "best_rank": min(ranks) if ranks else None,
            "worst_rank": max(ranks) if ranks else None,
            "rank_quality": summarize_rank_quality(ranks, universe_size=safe_universe),
            "simulated_ranks": ranks,
        }
        summary["reward"] = reward_summary(summary, universe_size=safe_universe)
        simulations.append({"seed": seed, **summary})

    objective_values = [float(item["reward"]["objectiveScore"]) for item in simulations]
    tail_penalties = [float(item["reward"]["tailRiskPenalty"]) for item in simulations]
    return {
        "label": "random_same_budget",
        "evaluated_draws": evaluated_draws,
        "top_n": top_n,
        "universe_size": universe_size,
        "analytical": analytical,
        "monte_carlo": simulations,
        "reward": {
            "objectiveScore": round(mean(objective_values), 6) if objective_values else 0.0,
            "tailRiskPenalty": round(mean(tail_penalties), 6) if tail_penalties else 0.0,
        },
        "rank_quality": {
            "tail_risk_penalty": round(mean(tail_penalties), 6) if tail_penalties else 0.0,
        },
        "protocol_key": {"evaluated_draws": evaluated_draws, "universe_size": universe_size},
    }


def objective_score(summary: dict) -> float:
    reward = summary.get("reward") if isinstance(summary.get("reward"), dict) else {}
    return float(reward.get("objectiveScore") or 0.0)


def tail_risk_penalty(summary: dict) -> float:
    reward = summary.get("reward") if isinstance(summary.get("reward"), dict) else {}
    if "tailRiskPenalty" in reward:
        return float(reward.get("tailRiskPenalty") or 0.0)
    rank_quality = summary.get("rank_quality") if isinstance(summary.get("rank_quality"), dict) else {}
    return float(rank_quality.get("tail_risk_penalty") or 0.0)


def promotion_gate(*, candidate_summary: dict, control_summaries: list[dict], current_best_label: str = "current_best_frozen_baseline") -> dict:
    candidate_objective = objective_score(candidate_summary)
    objective_failures = [
        {
            "label": control.get("label"),
            "objective_score": objective_score(control),
        }
        for control in control_summaries
        if objective_score(control) >= candidate_objective
    ]
    current_best = next((control for control in control_summaries if control.get("label") == current_best_label), None)
    current_best_tail = tail_risk_penalty(current_best) if current_best else None
    candidate_tail = tail_risk_penalty(candidate_summary)
    tail_risk_pass = current_best_tail is None or candidate_tail <= current_best_tail
    passed = not objective_failures and tail_risk_pass
    return {
        "passed": passed,
        "candidate_objective_score": candidate_objective,
        "candidate_tail_risk_penalty": candidate_tail,
        "objective_failures": objective_failures,
        "tail_risk_pass": tail_risk_pass,
        "current_best_tail_risk_penalty": current_best_tail,
        "language": "pass only if candidate frozen objective beats every control and tail risk is not worse than current_best_frozen_baseline",
    }


def run_control_experiments(
    *,
    history: list[HistoryDraw],
    universe: Iterable[tuple[int, ...]],
    candidate: LoadedCandidate,
    base_config: FrequencyRankerConfig,
    train_mode: TrainMode,
    train_window: int,
    eval_window: int,
    top_n: int,
    random_seeds: tuple[int, ...],
    workers: int | None = 1,
    ranked_universe=None,
) -> dict:
    started = time.time()
    worker_count = normalize_worker_count(workers)
    ranked_universe = ranked_universe or build_ranked_universe(universe)
    history_fingerprint_value = fingerprint_history(history)
    indexes = list(target_indexes(history_len=len(history), train_window=train_window, eval_window=eval_window))
    target_issues = [history_issue(history[index]) for index in indexes]

    control_configs = control_experiment_configs(base_config)
    labeled_configs = tuple(control_configs)
    if candidate.config is not None:
        labeled_configs = (("candidate", candidate.config), *control_configs)
        summaries = evaluate_config_summaries(
            history=history,
            ranked_universe=ranked_universe,
            labeled_configs=labeled_configs,
            train_window=train_window,
            train_mode=train_mode,
            eval_window=eval_window,
            top_n=top_n,
            workers=worker_count,
        )
        candidate_summary = summaries[0]
        candidate_summary["label"] = candidate.label
        candidate_summary["candidate_source"] = candidate.source
        candidate_summary["candidate_metadata"] = candidate.metadata or {}
        control_summaries = summaries[1:]
    else:
        control_summaries = evaluate_config_summaries(
            history=history,
            ranked_universe=ranked_universe,
            labeled_configs=control_configs,
            train_window=train_window,
            train_mode=train_mode,
            eval_window=eval_window,
            top_n=top_n,
            workers=worker_count,
        )
        candidate_summary = evaluate_fixed_candidate_set(
            candidate=candidate,
            history=history,
            universe_size=len(ranked_universe),
            train_window=train_window,
            train_mode=train_mode,
            eval_window=eval_window,
            top_n=top_n,
        )

    random_summary = random_same_budget_summary(
        evaluated_draws=len(indexes),
        universe_size=len(ranked_universe),
        top_n=top_n,
        random_seeds=random_seeds,
    )
    all_controls = [*control_summaries, random_summary]
    verdict = promotion_gate(candidate_summary=candidate_summary, control_summaries=all_controls)
    protocol = protocol_snapshot(
        as_of_issue=history_issue(history[-1]),
        history_fingerprint_value=history_fingerprint_value,
        train_mode=train_mode,
        train_window=train_window,
        eval_window=len(indexes),
        top_n=top_n,
        universe_size=len(ranked_universe),
        target_issues=target_issues,
        random_seeds=random_seeds,
    )
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "candidate_source": candidate.source,
        "candidate": candidate_summary,
        "protocol": protocol,
        "controls": control_summaries,
        "random_baseline": random_summary,
        "frozen_verdict": verdict,
        "guardrail": GUARDRAIL_LANGUAGE,
        "feature_matrix_cache": dict(getattr(ranked_universe, "cache_info", {})),
        "elapsed_seconds": round(time.time() - started, 3),
    }


def render_control_experiment_report(payload: dict) -> str:
    controls = [*payload["controls"], payload["random_baseline"]]
    rows = "\n".join(
        f"| {item['label']} | {objective_score(item)} | {tail_risk_penalty(item)} | "
        f"{item.get('top_10000_hits', 'n/a')} | {item.get('median_rank', 'n/a')} | {item.get('worst_rank', 'n/a')} |"
        for item in controls
    )
    candidate = payload["candidate"]
    protocol = payload["protocol"]
    verdict = payload["frozen_verdict"]
    return f"""# DEHPS Control Experiments

- Generated at: {payload["generated_at"]}
- Candidate source: `{payload["candidate_source"]}`
- Candidate label: `{candidate["label"]}`
- As-of issue: `{protocol["as_of_issue"]}`
- Train mode/window: `{protocol["train_mode"]}` / {protocol["train_window"]}
- Eval window: {protocol["eval_window"]}
- Top-N: {protocol["top_n"]}
- Universe size: {protocol["universe_size"]}
- Target issues: {", ".join(protocol["target_issues"])}
- Promotion verdict: `{ "PASS" if verdict["passed"] else "FAIL" }`

## Candidate

- Objective score: {objective_score(candidate)}
- Tail risk penalty: {tail_risk_penalty(candidate)}
- Top10000 hits: {candidate.get("top_10000_hits")}
- Median/worst rank: {candidate.get("median_rank")} / {candidate.get("worst_rank")}

## Controls

| Control | Objective | Tail risk penalty | Top10000 | Median rank | Worst rank |
| --- | ---: | ---: | ---: | ---: | ---: |
{rows}

## Random Same-Budget

```json
{json.dumps(payload["random_baseline"]["analytical"], ensure_ascii=False, indent=2, sort_keys=True)}
```

## Frozen Verdict

```json
{json.dumps(verdict, ensure_ascii=False, indent=2, sort_keys=True)}
```

## Guardrail

{payload["guardrail"]}

- Same universe: {protocol["protocol_equality"]["same_universe"]}
- Same target issues: {protocol["protocol_equality"]["same_target_issues"]}
- Same top_n: {protocol["protocol_equality"]["same_top_n"]}
- Same train/eval protocol: {protocol["protocol_equality"]["same_train_eval_protocol"]}
"""


def write_control_experiment_artifacts(payload: dict, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    key = datetime.now().strftime("%Y%m%d-%H%M%S")
    json_path = output_dir / f"control-experiments-{key}.json"
    md_path = output_dir / f"control-experiments-{key}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    md_path.write_text(render_control_experiment_report(payload))
    return json_path, md_path


def default_output_dir() -> Path:
    return ROOT_DIR / "data/output/optimization"


def normalize_candidate_source(value: str) -> CandidateSource:
    if value not in ("kdj", "neural", "config-json"):
        raise ValueError("candidate source must be one of kdj, neural, config-json")
    return value  # type: ignore[return-value]


def validate_train_mode(value: str) -> TrainMode:
    if value not in ("expanding", "rolling"):
        raise ValueError("train_mode must be expanding or rolling")
    return value  # type: ignore[return-value]


def all_weight_fields() -> tuple[str, ...]:
    return tuple(ALL_FIELDS)
