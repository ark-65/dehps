from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import typer

from dehps.research.errors import HypothesisRegistryError
from dehps.research.repository import HypothesisRepository
from dehps.research.service import ResearchHypothesisService
from dehps.research.status import (
    EvidenceDirection,
    HypothesisFamilyStatus,
    HypothesisStatus,
    RejectionScope,
)

app = typer.Typer(help="DEHPS worker commands")
hypothesis_app = typer.Typer(
    help="Human-operated hypothesis registry. It does not execute experiments or promote strategies."
)
app.add_typer(hypothesis_app, name="hypothesis")


@app.command()
def version() -> None:
    from dehps import __version__

    typer.echo(__version__)


def _registry_context() -> tuple[HypothesisRepository, ResearchHypothesisService]:
    repository = HypothesisRepository()
    repository.ensure_schema()
    return repository, ResearchHypothesisService(repository)


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise HypothesisRegistryError(f"cannot read JSON input {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise HypothesisRegistryError(f"JSON input must be an object: {path}")
    return value


def _normalized(value: Any) -> Any:
    if is_dataclass(value):
        return _normalized(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _normalized(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalized(item) for item in value]
    return value


def _emit(value: Any) -> None:
    typer.echo(json.dumps(_normalized(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def _fail(exc: Exception) -> None:
    typer.echo(f"error: {exc}", err=True)
    raise typer.Exit(code=2)


def _enum(enum_type, value: str):
    try:
        return enum_type(value)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in enum_type)
        raise HypothesisRegistryError(f"invalid {enum_type.__name__} {value!r}; allowed: {allowed}") from exc


@hypothesis_app.command("family-create")
def hypothesis_family_create(input_file: Path = typer.Option(..., "--input")) -> None:
    try:
        data = _load_object(input_file)
        repository, _ = _registry_context()
        result = repository.create_family(
            family_key=data["family_key"],
            title=data["title"],
            description=data.get("description", ""),
            mechanism=data["mechanism"],
            status=_enum(HypothesisFamilyStatus, data.get("status", "active")),
            rejection_scope=_enum(RejectionScope, data.get("rejection_scope", "none")),
            rejection_reason=data.get("rejection_reason"),
            reopen_condition=data.get("reopen_condition"),
            metadata=data.get("metadata", {}),
        )
        _emit({"family": result})
    except (HypothesisRegistryError, KeyError, TypeError) as exc:
        _fail(exc)


@hypothesis_app.command("family-list")
def hypothesis_family_list(
    status: str | None = typer.Option(None),
    limit: int = typer.Option(100, min=1, max=1000),
    offset: int = typer.Option(0, min=0),
) -> None:
    try:
        repository, _ = _registry_context()
        result = repository.list_families(
            status=None if status is None else _enum(HypothesisFamilyStatus, status),
            limit=limit,
            offset=offset,
        )
        _emit({"families": result, "limit": limit, "offset": offset})
    except HypothesisRegistryError as exc:
        _fail(exc)


@hypothesis_app.command("create")
def hypothesis_create(input_file: Path = typer.Option(..., "--input")) -> None:
    try:
        data = _load_object(input_file)
        repository, _ = _registry_context()
        result = repository.create_hypothesis(
            hypothesis_key=data["hypothesis_key"],
            family_key=data["family_key"],
            title=data["title"],
            mechanism=data["mechanism"],
            statement=data.get("statement", ""),
            null_hypothesis=data.get("null_hypothesis", ""),
            minimal_non_null=data.get("minimal_non_null", ""),
            invariants=data.get("invariants", []),
            baseline_definition=data.get("baseline_definition", {}),
            metric_definition=data.get("metric_definition", {}),
            failure_condition=data.get("failure_condition", {}),
            self_deception_risk=data.get("self_deception_risk", []),
            parent_hypothesis_id=data.get("parent_hypothesis_id"),
            reopen_condition=data.get("reopen_condition"),
            metadata=data.get("metadata", {}),
        )
        _emit({"hypothesis": result})
    except (HypothesisRegistryError, KeyError, TypeError) as exc:
        _fail(exc)


@hypothesis_app.command("list")
def hypothesis_list(
    status: list[str] | None = typer.Option(None),
    family_key: str | None = typer.Option(None),
    limit: int = typer.Option(100, min=1, max=1000),
    offset: int = typer.Option(0, min=0),
) -> None:
    try:
        repository, _ = _registry_context()
        statuses = [_enum(HypothesisStatus, value) for value in (status or [])]
        result = repository.list_hypotheses(
            family_key=family_key,
            statuses=statuses,
            limit=limit,
            offset=offset,
        )
        _emit({"hypotheses": result, "limit": limit, "offset": offset})
    except HypothesisRegistryError as exc:
        _fail(exc)


@hypothesis_app.command("show")
def hypothesis_show(hypothesis_key: str) -> None:
    try:
        repository, _ = _registry_context()
        _emit({"hypothesis": repository.get_hypothesis(hypothesis_key)})
    except HypothesisRegistryError as exc:
        _fail(exc)


@hypothesis_app.command("preregister")
def hypothesis_preregister(
    hypothesis_key: str,
    decided_by: str = typer.Option(...),
) -> None:
    try:
        _, service = _registry_context()
        _emit({"hypothesis": service.preregister(hypothesis_key, decided_by=decided_by)})
    except HypothesisRegistryError as exc:
        _fail(exc)


@hypothesis_app.command("start")
def hypothesis_start(hypothesis_key: str, decided_by: str = typer.Option(...)) -> None:
    try:
        _, service = _registry_context()
        _emit({"hypothesis": service.start(hypothesis_key, decided_by=decided_by)})
    except HypothesisRegistryError as exc:
        _fail(exc)


def _completion(hypothesis_key: str, input_file: Path, status: HypothesisStatus) -> None:
    try:
        data = _load_object(input_file)
        _, service = _registry_context()
        if status == HypothesisStatus.REJECTED:
            result = service.reject(
                hypothesis_key,
                decision_code=data["decision_code"],
                summary=data["summary"],
                decided_by=data["decided_by"],
                reason=data["reason"],
                evidence_ids=data["evidence_ids"],
                rejection_scope=_enum(RejectionScope, data["rejection_scope"]),
                reopen_condition=data["reopen_condition"],
            )
        else:
            result = service.complete_with_decision(
                hypothesis_key,
                new_status=status,
                decision_code=data["decision_code"],
                summary=data["summary"],
                decided_by=data["decided_by"],
                reason=data["reason"],
                evidence_ids=data["evidence_ids"],
            )
        _emit({"hypothesis": result})
    except (HypothesisRegistryError, KeyError, TypeError) as exc:
        _fail(exc)


@hypothesis_app.command("reject")
def hypothesis_reject(hypothesis_key: str, input_file: Path = typer.Option(..., "--input")) -> None:
    _completion(hypothesis_key, input_file, HypothesisStatus.REJECTED)


@hypothesis_app.command("inconclusive")
def hypothesis_inconclusive(
    hypothesis_key: str, input_file: Path = typer.Option(..., "--input")
) -> None:
    _completion(hypothesis_key, input_file, HypothesisStatus.INCONCLUSIVE)


@hypothesis_app.command("invalidate")
def hypothesis_invalidate(
    hypothesis_key: str, input_file: Path = typer.Option(..., "--input")
) -> None:
    try:
        data = _load_object(input_file)
        _, service = _registry_context()
        result = service.invalidate(
            hypothesis_key,
            decision_code=data["decision_code"],
            summary=data["summary"],
            decided_by=data["decided_by"],
            reason=data["reason"],
            evidence_ids=data.get("evidence_ids", []),
        )
        _emit({"hypothesis": result})
    except (HypothesisRegistryError, KeyError, TypeError) as exc:
        _fail(exc)


@hypothesis_app.command("reopen")
def hypothesis_reopen(
    hypothesis_key: str, input_file: Path = typer.Option(..., "--input")
) -> None:
    try:
        data = _load_object(input_file)
        _, service = _registry_context()
        result = service.reopen(
            hypothesis_key,
            new_hypothesis_key=data["new_hypothesis_key"],
            reopen_reason=data["reopen_reason"],
            decided_by=data["decided_by"],
            changed_basis=data["changed_basis"],
            title=data.get("title"),
        )
        _emit({"hypothesis": result})
    except (HypothesisRegistryError, KeyError, TypeError) as exc:
        _fail(exc)


@hypothesis_app.command("experiment-add")
def hypothesis_experiment_add(input_file: Path = typer.Option(..., "--input")) -> None:
    try:
        data = _load_object(input_file)
        _, service = _registry_context()
        result = service.register_experiment(
            hypothesis_key=data["hypothesis_key"],
            experiment_key=data["experiment_key"],
            experiment_type=data["experiment_type"],
            report_path=data.get("report_path"),
            artifact_paths=data.get("artifact_paths", []),
            external_run_id=data.get("external_run_id"),
            training_run_id=data.get("training_run_id"),
            training_round_index=data.get("training_round_index"),
            config_snapshot=data.get("config_snapshot", {}),
            metadata=data.get("metadata", {}),
            external_reference=bool(data.get("external_reference", False)),
            compute_hashes=bool(data.get("compute_hashes", False)),
        )
        _emit({"experiment": result})
    except (HypothesisRegistryError, KeyError, TypeError) as exc:
        _fail(exc)


@hypothesis_app.command("evidence-add")
def hypothesis_evidence_add(input_file: Path = typer.Option(..., "--input")) -> None:
    try:
        data = _load_object(input_file)
        _, service = _registry_context()
        observed_at = data.get("observed_at")
        result = service.register_evidence(
            hypothesis_key=data["hypothesis_key"],
            evidence_type=data["evidence_type"],
            direction=_enum(EvidenceDirection, data["direction"]),
            summary=data["summary"],
            experiment_key=data.get("experiment_key"),
            metrics=data.get("metrics", {}),
            artifact_path=data.get("artifact_path"),
            content_hash=data.get("content_hash"),
            observed_at=(
                None
                if observed_at is None
                else datetime.fromisoformat(str(observed_at).replace("Z", "+00:00"))
            ),
            metadata=data.get("metadata", {}),
            external_reference=bool(data.get("external_reference", False)),
        )
        _emit({"evidence": result})
    except (HypothesisRegistryError, KeyError, TypeError, ValueError) as exc:
        _fail(exc)


@hypothesis_app.command("decisions")
def hypothesis_decisions(hypothesis_key: str) -> None:
    try:
        repository, _ = _registry_context()
        _emit({"decisions": repository.list_decisions(hypothesis_key)})
    except HypothesisRegistryError as exc:
        _fail(exc)


if __name__ == "__main__":
    app()
