from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from dehps.db import get_connection
from dehps.portfolio import NullModelConfig, ScoredCandidate, audit_candidate_portfolio
from dehps.portfolio.artifact import (
    load_and_verify_portfolio_audit_artifact,
    write_portfolio_audit_artifact,
)
from dehps.portfolio.models import PortfolioAuditViolation, reject
from dehps.portfolio.repository import load_forward_prediction_portfolio


def _candidate_from_dict(value: object) -> ScoredCandidate:
    if not isinstance(value, dict):
        reject("portfolio_json_candidate_invalid", "candidate rows must be JSON objects")
    numbers = value.get("red_numbers", value.get("numbers"))
    if not isinstance(numbers, list):
        reject("portfolio_json_candidate_numbers_missing", "candidate red_numbers are required")
    return ScoredCandidate.build(
        source_rank=value.get("source_rank", value.get("rank")),
        red_numbers=numbers,
        score=value.get("score"),
        lex_id=value.get("lex_id"),
    )


def _load_json_input(path: Path, *, budget: int, pool_limit: int):
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PortfolioAuditViolation(
            "portfolio_json_input_read_error",
            "could not read candidate portfolio JSON",
            path=str(path),
        ) from exc
    if not isinstance(payload, dict):
        reject("portfolio_json_input_invalid", "portfolio JSON must be an object")
    raw_pool = payload.get("candidate_pool", payload.get("candidates"))
    if not isinstance(raw_pool, list):
        reject("portfolio_json_pool_missing", "candidate_pool or candidates must be a list")
    pool = tuple(_candidate_from_dict(row) for row in raw_pool[:pool_limit])
    raw_selected = payload.get("selected_candidates")
    if raw_selected is None:
        selected = pool[:budget]
    elif isinstance(raw_selected, list):
        selected = tuple(_candidate_from_dict(row) for row in raw_selected)
    else:
        reject("portfolio_json_selected_invalid", "selected_candidates must be a list")
    if len(selected) != budget:
        reject(
            "portfolio_json_budget_mismatch",
            "selected candidate count must equal budget",
            selected_count=len(selected),
            budget=budget,
        )
    source = payload.get("source")
    if source is not None and not isinstance(source, dict):
        reject("portfolio_json_source_invalid", "source must be a JSON object")
    return selected, pool, source or {"source_kind": "json_file", "source_key": str(path)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only candidate portfolio geometry audit; never changes production TopK.",
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--prediction-run-key")
    source.add_argument("--input", type=Path)
    source.add_argument("--verify-artifact", type=Path)
    parser.add_argument("--budget", type=int, default=100)
    parser.add_argument("--pool-limit", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=20260722)
    parser.add_argument("--uniform-replicates", type=int, default=500)
    parser.add_argument("--pool-replicates", type=int, default=500)
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.verify_artifact:
        verification = load_and_verify_portfolio_audit_artifact(args.verify_artifact)
        print(json.dumps(verification, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if not args.prediction_run_key and args.input is None:
        parser.error("one of --prediction-run-key, --input, or --verify-artifact is required")
    if args.budget < 1:
        parser.error("--budget must be at least 1")
    if args.pool_limit < args.budget:
        parser.error("--pool-limit must be at least --budget")
    if args.prediction_run_key:
        with get_connection() as conn:
            loaded = load_forward_prediction_portfolio(
                conn,
                prediction_run_key=args.prediction_run_key,
                budget=args.budget,
                pool_limit=args.pool_limit,
            )
        candidates = loaded.candidates
        pool = loaded.candidate_pool
        source = loaded.source
    else:
        candidates, pool, source = _load_json_input(
            args.input,
            budget=args.budget,
            pool_limit=args.pool_limit,
        )
    artifact = audit_candidate_portfolio(
        candidates,
        candidate_pool=pool,
        source=source,
        null_config=NullModelConfig(
            master_seed=args.seed,
            uniform_legal_replicates=args.uniform_replicates,
            random_from_pool_replicates=args.pool_replicates,
        ),
    )
    if args.output:
        write_portfolio_audit_artifact(artifact, args.output)
    payload: dict[str, Any] = artifact.as_dict()
    if args.output:
        payload["output_path"] = str(args.output)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
