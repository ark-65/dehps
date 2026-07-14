from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import typer

from dehps.agents.repository import AgentRequestRepository
from dehps.agents.requests import AgentExecutionStatus
from dehps.agents.roles import AgentRole
from dehps.agents.service import AgentRequestService
from dehps.experiments.ranking_disagreement.artifacts import validate_manifest
from dehps.experiments.ranking_disagreement.executor import RankingDisagreementExecutor
from dehps.experiments.ranking_disagreement.models import (
    FROZEN_OPERATOR_REQUEST_KEY,
    FROZEN_PLAN_KEY,
    FROZEN_PLAN_FINGERPRINT,
    stable_json,
    utc_now_iso,
)
from dehps.experiments.ranking_disagreement.validation import (
    require_approved_operator_request,
    validate_artifact_directory,
)


app = typer.Typer(help="Round 24 frozen ranking-disagreement isolated experiment tool.")


@app.command("feasibility")
def feasibility(
    plan_key: str = typer.Option(FROZEN_PLAN_KEY, "--plan-key"),
    output_directory: Path | None = typer.Option(None, "--output-directory"),
    legal_universe_limit: int | None = typer.Option(None, "--legal-universe-limit"),
    no_registry: bool = typer.Option(False, "--no-registry"),
) -> None:
    try:
        executor = _executor(plan_key, output_directory, legal_universe_limit, update_registry=not no_registry)
        _emit(executor.run_feasibility())
    except Exception as exc:
        _fail(exc)


@app.command("search")
def search(
    plan_key: str = typer.Option(FROZEN_PLAN_KEY, "--plan-key"),
    output_directory: Path | None = typer.Option(None, "--output-directory"),
    legal_universe_limit: int | None = typer.Option(None, "--legal-universe-limit"),
    no_registry: bool = typer.Option(False, "--no-registry"),
) -> None:
    try:
        executor = _executor(plan_key, output_directory, legal_universe_limit, update_registry=not no_registry)
        _emit(executor.run_historical_search())
    except Exception as exc:
        _fail(exc)


@app.command("frozen")
def frozen(
    plan_key: str = typer.Option(FROZEN_PLAN_KEY, "--plan-key"),
    output_directory: Path | None = typer.Option(None, "--output-directory"),
    legal_universe_limit: int | None = typer.Option(None, "--legal-universe-limit"),
    no_registry: bool = typer.Option(False, "--no-registry"),
) -> None:
    try:
        executor = _executor(plan_key, output_directory, legal_universe_limit, update_registry=not no_registry)
        _emit(executor.run_frozen_validation())
    except Exception as exc:
        _fail(exc)


@app.command("run-isolated")
def run_isolated(
    plan_key: str = typer.Option(FROZEN_PLAN_KEY, "--plan-key"),
    operator_request_key: str = typer.Option(FROZEN_OPERATOR_REQUEST_KEY, "--operator-request-key"),
    output_directory: Path | None = typer.Option(None, "--output-directory"),
    legal_universe_limit: int | None = typer.Option(None, "--legal-universe-limit"),
    executor_id: str = typer.Option("operator:round24", "--executor-id"),
    cpu_limit: int = typer.Option(16, "--cpu-limit", min=1, max=16),
    memory_limit_gb: float = typer.Option(20.0, "--memory-limit-gb", min=0.1, max=20.0),
    timeout_seconds: int = typer.Option(3600, "--timeout-seconds", min=1),
) -> None:
    try:
        _reject_production_database()
        operator = require_approved_operator_request(operator_request_key=operator_request_key, plan_key=plan_key)
        repository = AgentRequestRepository()
        repository.ensure_schema()
        service = AgentRequestService(repository)
        run_id = f"round24-{FROZEN_PLAN_FINGERPRINT[:12]}-{utc_now_iso().replace(':', '').replace('+', 'Z')}"
        _, execution = service.begin_execution(
            operator_request_key,
            executor_role=AgentRole.OPERATOR,
            executor_id=executor_id,
            environment="isolated",
            run_id=run_id,
        )
        try:
            result = _executor(plan_key, output_directory, legal_universe_limit, update_registry=True).run_isolated(
                cpu_limit=cpu_limit,
                memory_limit_gb=memory_limit_gb,
                timeout_seconds=timeout_seconds,
            )
            operator_result = {
                **result,
                "operator_request_key": operator_request_key,
                "operator_request_database": operator["database"],
                "actual_cpu": {"limit": cpu_limit},
                "actual_memory": {"limit_gb": memory_limit_gb},
                "actual_time": result["resources"],
                "failures": [],
                "skipped": ["forward_validation"],
                "violations": [],
                "production_access": False,
            }
            service.complete_execution(
                operator_request_key,
                execution_id=execution.id,
                executor_role=AgentRole.OPERATOR,
                executor_id=executor_id,
                result=operator_result,
                artifact_paths=list(result["artifact_paths"]),
            )
            _emit(operator_result)
        except Exception as exc:
            service.fail_execution(
                operator_request_key,
                execution_id=execution.id,
                executor_role=AgentRole.OPERATOR,
                executor_id=executor_id,
                error={"message": str(exc), "status": AgentExecutionStatus.FAILED.value},
            )
            raise
    except Exception as exc:
        _fail(exc)


@app.command("validate-artifacts")
def validate_artifacts(
    output_directory: Path = typer.Argument(...),
) -> None:
    try:
        _emit(validate_artifact_directory(output_directory))
    except Exception as exc:
        _fail(exc)


@app.command("show-results")
def show_results(
    output_directory: Path = typer.Argument(...),
) -> None:
    try:
        manifest = validate_manifest(output_directory / "manifest.json")
        payload: dict[str, Any] = {"manifest": manifest}
        for filename in ("search_results.json", "frozen_results.json", "statistics.json", "validation_report.json"):
            path = output_directory / filename
            if path.exists():
                payload[filename.removesuffix(".json")] = json.loads(path.read_text(encoding="utf-8"))
        _emit(payload)
    except Exception as exc:
        _fail(exc)


def _executor(
    plan_key: str,
    output_directory: Path | None,
    legal_universe_limit: int | None,
    *,
    update_registry: bool,
) -> RankingDisagreementExecutor:
    return RankingDisagreementExecutor(
        plan_key=plan_key,
        output_directory=output_directory,
        legal_universe_limit=legal_universe_limit,
        update_registry=update_registry,
    )


def _reject_production_database() -> None:
    database = os.environ.get("DB_NAME", "dehps")
    if database in {"dehps", "production", "prod"}:
        raise ValueError(
            "run-isolated refuses the default/production database; set DB_NAME to an isolated database"
        )


def _emit(value: Any) -> None:
    typer.echo(stable_json(value))


def _fail(exc: Exception) -> None:
    typer.echo(f"error: {exc}", err=True)
    raise typer.Exit(code=2)
