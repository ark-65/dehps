from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

import typer

from dehps.agents.actions import AgentAction
from dehps.agents.errors import AgentAuthorityError
from dehps.agents.policy import AgentAuthorityPolicy, AuthorizationContext
from dehps.agents.repository import AgentRequestRepository
from dehps.agents.requests import (
    AgentRequestStatus,
    AgentRequestType,
    AgentRiskLevel,
)
from dehps.agents.roles import AgentRole
from dehps.agents.service import AgentRequestService
from dehps.research.errors import HypothesisRegistryError
from dehps.research.repository import HypothesisRepository
from dehps.research.service import ResearchHypothesisService
from dehps.research.status import (
    EvidenceDirection,
    HypothesisFamilyStatus,
    HypothesisStatus,
    RejectionScope,
)
from dehps.research_autonomy.context import ResearchContextBuilder
from dehps.research_autonomy.proposal_engine import (
    DEFAULT_ENGINE_VERSION,
    AutonomousHypothesisProposalEngine,
)
from dehps.research_autonomy.repository import ResearchAutonomyArtifactRepository
from dehps.research_autonomy.submission import ResearchProposalSubmissionService
from dehps.research_autonomy.validation import HypothesisProposalValidator
from dehps.research_planning.service import ExperimentPlanningService
from dehps.experiments.ranking_disagreement.cli import app as ranking_disagreement_app
from dehps.draw_sync.scheduler import DrawSyncSchedulePolicy, DrawSyncWatch
from dehps.draw_sync.service import DrawSyncService
from dehps.forward_state.service import ForwardStateService
from dehps.forward_runtime.resident import ResidentForwardRuntime, ResidentForwardRuntimeConfig
from dehps.forward_runtime.service import ForwardRuntimeService
from dehps.research_evidence.service import EvidenceEvaluationService
from dehps.research_runtime.models import ResidentResearchRuntimeConfig, ResearchRuntimeBudget
from dehps.research_runtime.resident import ResidentResearchRuntime
from dehps.research_runtime.runtime import ContinuousResearchRuntime
from dehps.research_os.control_plane import ResearchOSControlPlane
from dehps.research_os.information_theory import (
    CANONICAL_PREREGISTRATION_RELATIVE_PATH,
    InformationTheoryValidationError,
    M4_MANIFEST_RELATIVE_PATH,
    PhaseGateError,
    build_m4_status,
    freeze_preregistration,
    load_m4_manifest,
    load_preregistration,
    manifest_with_external_event,
    require_formal_run_gate,
    show_preregistration,
    validate_preregistration,
)
from dehps.research_os.information_theory.synthetic import (
    generate_null_dataset,
    load_synthetic_run_manifest,
)
from dehps.research_os.information_theory.metrics import (
    build_metric_artifact,
    load_metric_kernel_manifest,
    show_metric_artifact,
    validate_metric_artifact,
    validate_metric_input,
)
from dehps.research_os.models import ResearchOSValidationError
from dehps.research_os.repository import PostgresResearchOSRepository
from dehps.research_os.shadow import LegacyResearchOSShadowService
from dehps.research_scheduler.scheduler import AutonomousResearchScheduler
from dehps.engineering.service import AutonomousEngineeringService
from dehps.pattern_discovery.models import PatternSearchBudget
from dehps.pattern_discovery.service import PatternDiscoveryService
from dehps.training_resume.service import TrainingResumeService
from dehps.notifications.mail import (
    MailConfigurationError,
    MailDeliveryError,
    QqMailConfig,
    QqMailService,
)
from dehps.notifications.mainline_prediction import (
    MainlinePredictionMailError,
    MainlinePredictionNotificationService,
    PredictionDeliveryStateError,
)
from dehps.notifications.post_draw_evaluation import (
    PostDrawDeliveryStateError,
    PostDrawEvaluationNotificationService,
    PostDrawEvaluationReportError,
    load_post_draw_evaluations,
)
from dehps.db import get_connection
from dehps.config import ROOT_DIR
from dehps.forward_runtime.latest_prediction import (
    build_latest_prediction_payload,
    load_latest_prediction_rows,
)
from dehps.source_version import resolve_git_commit

app = typer.Typer(help="DEHPS worker commands")
agent_app = typer.Typer(
    help="Audited Agent Request lifecycle. It does not execute Shell, Git, or Supervisor operations."
)
research_context_app = typer.Typer(help="Build deterministic ResearchContext from formal sources.")
research_proposal_app = typer.Typer(
    help="Dry-run autonomous hypothesis proposals or submit one Research Agent Request."
)
experiment_plan_app = typer.Typer(
    help="Build and materialize preregistered autonomous experiment plans."
)
hypothesis_app = typer.Typer(
    help="Human-operated hypothesis registry. It does not execute experiments or promote strategies."
)
evidence_app = typer.Typer(help="Build and inspect formal autonomous research Evidence.")
decision_app = typer.Typer(help="Draft and review autonomous hypothesis decisions.")
scheduler_app = typer.Typer(help="Autonomous research scheduler. It only creates audited Research Requests.")
engineering_app = typer.Typer(help="Dry-run autonomous engineering implementation contracts.")
pattern_app = typer.Typer(help="Autonomous pattern discovery and declarative strategy synthesis.")
draw_sync_app = typer.Typer(help="Independent audited draw synchronization.")
forward_app = typer.Typer(help="Forward-state reconciliation for training resume.")
training_resume_app = typer.Typer(help="Exactly-once training resume from audited draw events.")
research_runtime_app = typer.Typer(help="Continuous research runtime decoupled from forward validation.")
research_os_app = typer.Typer(
    help="Goal-driven Research OS control plane. P1 resolves dependencies but does not dispatch Tasks."
)
information_theory_app = typer.Typer(
    help="M4 information-theory contract surfaces. Statistical execution is phase-gated."
)
information_theory_preregistration_app = typer.Typer(
    help="Validate, freeze, and inspect immutable M4 preregistrations."
)
information_theory_synthetic_app = typer.Typer(
    help="P2.1 synthetic contracts and one-replicate null generation."
)
information_theory_metrics_app = typer.Typer(
    help="P2.2 deterministic descriptive metric artifacts; not a P2 gate."
)
information_theory_app.add_typer(
    information_theory_preregistration_app,
    name="preregistration",
)
information_theory_app.add_typer(
    information_theory_synthetic_app,
    name="synthetic",
)
information_theory_app.add_typer(
    information_theory_metrics_app,
    name="metrics",
)
research_os_app.add_typer(information_theory_app, name="information-theory")
forward_runtime_app = typer.Typer(help="Forward validation runtime decoupled from continuous research.")
mail_app = typer.Typer(
    help="Operator-controlled email delivery. Credentials are read only from environment variables."
)
app.add_typer(hypothesis_app, name="hypothesis")
app.add_typer(agent_app, name="agent")
app.add_typer(research_context_app, name="research-context")
app.add_typer(research_proposal_app, name="research-proposal")
app.add_typer(experiment_plan_app, name="experiment-plan")
app.add_typer(ranking_disagreement_app, name="ranking-disagreement")
app.add_typer(evidence_app, name="evidence")
app.add_typer(decision_app, name="decision")
app.add_typer(scheduler_app, name="scheduler")
app.add_typer(engineering_app, name="engineering")
app.add_typer(pattern_app, name="pattern")
app.add_typer(draw_sync_app, name="draw-sync")
app.add_typer(forward_app, name="forward")
app.add_typer(training_resume_app, name="training-resume")
app.add_typer(research_runtime_app, name="research-runtime")
app.add_typer(research_os_app, name="research-os")
app.add_typer(forward_runtime_app, name="forward-runtime")
app.add_typer(mail_app, name="mail")


@app.command()
def version() -> None:
    from dehps import __version__

    typer.echo(__version__)


@mail_app.command("send")
def mail_send(
    subject: str = typer.Option(..., help="Message subject."),
    text: str = typer.Option(..., help="Plain-text message body."),
    html: str | None = typer.Option(None, help="Optional HTML alternative."),
    recipient: str | None = typer.Option(
        None,
        "--to",
        help="Optional recipient; defaults to the configured QQ sender address.",
    ),
) -> None:
    """Send one message through QQ SMTP over TLS."""
    try:
        receipt = QqMailService(QqMailConfig.from_environment()).send(
            subject=subject,
            text=text,
            html=html,
            recipient=recipient,
        )
        _emit({"sent": True, "receipt": receipt})
    except (MailConfigurationError, MailDeliveryError) as exc:
        _fail(exc)


@mail_app.command("mainline-prediction")
def mail_mainline_prediction(
    send: bool = typer.Option(
        False,
        "--send/--preview",
        help="Deliver the email or only validate and summarize the latest mainline.",
    ),
) -> None:
    """Validate or send the durable static_100 Top-100 prediction."""
    try:
        config = QqMailConfig.from_environment()
        service = MainlinePredictionNotificationService(config)
        with get_connection() as conn:
            runs, candidates = load_latest_prediction_rows(conn, top_limit=100)
        payload = build_latest_prediction_payload(
            runs,
            candidates,
            git_commit=resolve_git_commit(ROOT_DIR),
            top_limit=100,
        )
        if send:
            result = service.deliver(payload, now=datetime.now(timezone.utc))
            _emit({"delivery": result})
            return
        email = service.preview(payload)
        _emit(
            {
                "status": "preview",
                "delivery_key": email.delivery_key,
                "issue": email.issue,
                "as_of_issue": email.as_of_issue,
                "prediction_run_key": email.prediction_run_key,
                "candidate_count": email.candidate_count,
                "recipient": config.destination,
                "subject": email.subject,
            }
        )
    except (
        MailConfigurationError,
        MailDeliveryError,
        MainlinePredictionMailError,
        PredictionDeliveryStateError,
        OSError,
        ValueError,
    ) as exc:
        _fail(exc)


@mail_app.command("post-draw-evaluation")
def mail_post_draw_evaluation(
    issue: str = typer.Option(..., help="Evaluated draw issue to report."),
    send: bool = typer.Option(
        False,
        "--send/--preview",
        help="Deliver the email or only validate and summarize the report.",
    ),
) -> None:
    """Validate or send one accepted three-line post-draw evaluation report."""
    try:
        config = QqMailConfig.from_environment()
        service = PostDrawEvaluationNotificationService(config)
        with get_connection() as conn:
            rows = load_post_draw_evaluations(conn, issue=issue)
        if send:
            result = service.deliver(rows)
            _emit({"delivery": result})
            return
        report = service.preview(rows)
        _emit(
            {
                "status": "preview",
                "issue": report.issue,
                "report_digest": report.report_digest,
                "delivery_key": report.delivery_key,
                "recipient": config.destination,
                "subject": report.subject,
                "line_count": len(report.payload["lines"]),
            }
        )
    except (
        MailConfigurationError,
        MailDeliveryError,
        PostDrawEvaluationReportError,
        PostDrawDeliveryStateError,
        OSError,
        ValueError,
    ) as exc:
        _fail(exc)


def _registry_context() -> tuple[HypothesisRepository, ResearchHypothesisService]:
    repository = HypothesisRepository()
    repository.ensure_schema()
    return repository, ResearchHypothesisService(repository)


def _agent_context() -> tuple[AgentRequestRepository, AgentRequestService]:
    repository = AgentRequestRepository()
    repository.ensure_schema()
    return repository, AgentRequestService(repository)


def _research_context_builder() -> ResearchContextBuilder:
    return ResearchContextBuilder()


def _proposal_engine(engine_version: str) -> AutonomousHypothesisProposalEngine:
    return AutonomousHypothesisProposalEngine(engine_version=engine_version)


def _experiment_planning_service() -> ExperimentPlanningService:
    return ExperimentPlanningService()


def _evidence_service() -> EvidenceEvaluationService:
    service = EvidenceEvaluationService()
    service.ensure_schema()
    return service


def _scheduler_service() -> AutonomousResearchScheduler:
    service = AutonomousResearchScheduler()
    service.ensure_schema()
    return service


def _research_os_repository() -> PostgresResearchOSRepository:
    repository = PostgresResearchOSRepository()
    repository.ensure_schema()
    return repository


def _engineering_service() -> AutonomousEngineeringService:
    return AutonomousEngineeringService()


def _pattern_service() -> PatternDiscoveryService:
    return PatternDiscoveryService()


def _draw_sync_service() -> DrawSyncService:
    service = DrawSyncService()
    service.ensure_schema()
    return service


def _forward_state_service() -> ForwardStateService:
    return ForwardStateService()


def _training_resume_service() -> TrainingResumeService:
    service = TrainingResumeService()
    service.repository.ensure_schema()
    return service


def _research_runtime() -> ContinuousResearchRuntime:
    return ContinuousResearchRuntime()


def _forward_runtime_service() -> ForwardRuntimeService:
    return ForwardRuntimeService()


def _resident_research_runtime(
    *,
    interval_seconds: float,
    max_cycles: int | None,
    research_cpu: int,
    forward_cpu: int,
    total_memory_gb: int,
    research_memory_gb: int,
    forward_memory_gb: int,
    daily_cycle_limit: int,
) -> ResidentResearchRuntime:
    budget = ResearchRuntimeBudget(
        research_cpu=research_cpu,
        forward_cpu=forward_cpu,
        total_memory_gb=total_memory_gb,
        research_memory_gb=research_memory_gb,
        forward_memory_gb=forward_memory_gb,
        daily_cycle_limit=daily_cycle_limit,
    )
    return ResidentResearchRuntime(
        budget=budget,
        config=ResidentResearchRuntimeConfig(interval_seconds=interval_seconds, max_cycles=max_cycles),
    )


def _resident_forward_runtime(*, interval_seconds: float, max_checks: int | None) -> ResidentForwardRuntime:
    return ResidentForwardRuntime(
        config=ResidentForwardRuntimeConfig(interval_seconds=interval_seconds, max_checks=max_checks),
    )


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise HypothesisRegistryError(f"cannot read JSON input {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise HypothesisRegistryError(f"JSON input must be an object: {path}")
    return value


def _load_draw_records(path: Path | None) -> list[tuple[str, tuple[int, ...]]] | None:
    if path is None:
        return None
    value = json.loads(path.read_text())
    draws = value.get("draws", value) if isinstance(value, dict) else value
    if not isinstance(draws, list):
        raise HypothesisRegistryError("draw input must be a list or an object with draws")
    records: list[tuple[str, tuple[int, ...]]] = []
    for index, item in enumerate(draws, start=1):
        if isinstance(item, dict):
            issue = str(item.get("issue") or f"input-{index:04d}")
            numbers = item.get("red_numbers") or item.get("numbers")
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            issue = str(item[0])
            numbers = item[1]
        else:
            issue = f"input-{index:04d}"
            numbers = item
        if not isinstance(numbers, (list, tuple)):
            raise HypothesisRegistryError(f"draw {issue} must provide red_numbers")
        records.append((issue, tuple(int(n) for n in numbers)))
    return records


def _pattern_budget(
    families: int,
    patterns_per_family: int,
    feature_candidates: int = 50,
    strategy_candidates: int = 30,
    weight_candidates: int = 200,
) -> PatternSearchBudget:
    return PatternSearchBudget(
        families=families,
        patterns_per_family=patterns_per_family,
        feature_candidates=feature_candidates,
        strategy_candidates=strategy_candidates,
        weight_candidates=weight_candidates,
    )


def _normalized(value: Any) -> Any:
    if is_dataclass(value):
        return _normalized(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return value.as_posix()
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


def _agent_role(value: str) -> AgentRole:
    return _enum(AgentRole, value)


@research_context_app.command("build")
def research_context_build(
    context_output: Path | None = typer.Option(None, "--context-output"),
) -> None:
    try:
        context = _research_context_builder().build()
        output = None
        if context_output is not None:
            output = ResearchAutonomyArtifactRepository().write_context(context, context_output)
        _emit({"context_fingerprint": context.fingerprint, "context": context, "context_output": output})
    except (ValueError, OSError, TypeError) as exc:
        _fail(exc)


@research_context_app.command("show")
def research_context_show(
    input_file: Path | None = typer.Option(None, "--input"),
) -> None:
    try:
        _emit(ResearchAutonomyArtifactRepository().read_context(input_file))
    except (ValueError, OSError, TypeError) as exc:
        _fail(exc)


def _generate_research_proposals(
    *,
    max_candidates: int,
    engine_version: str,
    context_output: Path | None,
):
    context = _research_context_builder().build()
    if context_output is not None:
        ResearchAutonomyArtifactRepository().write_context(context, context_output)
    result = _proposal_engine(engine_version).propose(context, max_candidates=max_candidates)
    return context, result


@research_proposal_app.command("generate")
def research_proposal_generate(
    max_candidates: int = typer.Option(20, "--max-candidates", min=1, max=20),
    engine_version: str = typer.Option(DEFAULT_ENGINE_VERSION, "--engine-version"),
    context_output: Path | None = typer.Option(None, "--context-output"),
) -> None:
    """Dry-run proposal generation; this command creates no Request or Hypothesis."""
    try:
        context, result = _generate_research_proposals(
            max_candidates=max_candidates,
            engine_version=engine_version,
            context_output=context_output,
        )
        _emit({"dry_run": True, "context_fingerprint": context.fingerprint, "result": result})
    except (ValueError, OSError, TypeError) as exc:
        _fail(exc)


@research_proposal_app.command("list")
def research_proposal_list(
    limit: int = typer.Option(100, min=1, max=500),
    offset: int = typer.Option(0, min=0),
) -> None:
    try:
        repository, _ = _agent_context()
        requests = repository.list_requests(
            request_type=AgentRequestType.RESEARCH_HYPOTHESIS_PROPOSAL,
            limit=limit,
            offset=offset,
        )
        _emit({"proposals": requests, "limit": limit, "offset": offset})
    except (AgentAuthorityError, ValueError, TypeError) as exc:
        _fail(exc)


@research_proposal_app.command("show")
def research_proposal_show(proposal_key: str) -> None:
    try:
        repository, _ = _agent_context()
        requests = repository.list_requests(
            request_type=AgentRequestType.RESEARCH_HYPOTHESIS_PROPOSAL,
            limit=500,
        )
        request = next(
            (
                item
                for item in requests
                if item.request_key == proposal_key
                or item.payload.get("proposal", {}).get("proposal_key") == proposal_key
            ),
            None,
        )
        if request is None:
            raise AgentAuthorityError(f"research proposal not found: {proposal_key}")
        _emit({"proposal": request})
    except (AgentAuthorityError, ValueError, TypeError) as exc:
        _fail(exc)


@research_proposal_app.command("submit")
def research_proposal_submit(
    requested_by: str = typer.Option(..., "--requested-by"),
    request_key: str | None = typer.Option(None, "--request-key"),
    max_candidates: int = typer.Option(20, "--max-candidates", min=1, max=20),
    engine_version: str = typer.Option(DEFAULT_ENGINE_VERSION, "--engine-version"),
    context_output: Path | None = typer.Option(None, "--context-output"),
) -> None:
    try:
        context, result = _generate_research_proposals(
            max_candidates=max_candidates,
            engine_version=engine_version,
            context_output=context_output,
        )
        repository, agent_service = _agent_context()
        request = ResearchProposalSubmissionService(repository, agent_service).submit(
            result,
            context,
            requested_by=requested_by,
            request_key=request_key,
        )
        _emit({"request": request, "selected": result.selected, "executed": False})
    except (AgentAuthorityError, ValueError, OSError, TypeError) as exc:
        _fail(exc)


@research_proposal_app.command("validate")
def research_proposal_validate(
    max_candidates: int = typer.Option(20, "--max-candidates", min=1, max=20),
    engine_version: str = typer.Option(DEFAULT_ENGINE_VERSION, "--engine-version"),
    context_output: Path | None = typer.Option(None, "--context-output"),
) -> None:
    try:
        context, result = _generate_research_proposals(
            max_candidates=max_candidates,
            engine_version=engine_version,
            context_output=context_output,
        )
        if result.selected is None:
            raise ValueError("no valid proposal is available")
        report = HypothesisProposalValidator().validate(result.selected, context)
        _emit({"proposal_key": result.selected.proposal_key, "validation": report})
        if not report.valid:
            raise typer.Exit(code=2)
    except (ValueError, OSError, TypeError) as exc:
        _fail(exc)


@experiment_plan_app.command("build")
def experiment_plan_build(
    proposal_request_key: str | None = typer.Option(None, "--proposal-request-key"),
) -> None:
    """Dry-run plan build; this command creates no Hypothesis, Experiment, Request, or Evidence."""
    try:
        plan, approved, context = _experiment_planning_service().build(
            proposal_request_key=proposal_request_key
        )
        _emit({
            "dry_run": True,
            "proposal_request_key": approved.request.request_key,
            "context_fingerprint": context.fingerprint,
            "plan": plan,
            "writes": [],
        })
    except (AgentAuthorityError, HypothesisRegistryError, ValueError, OSError, TypeError) as exc:
        _fail(exc)


@experiment_plan_app.command("validate")
def experiment_plan_validate(
    proposal_request_key: str | None = typer.Option(None, "--proposal-request-key"),
) -> None:
    """Validate a dry-run plan; this command writes nothing."""
    try:
        plan, report = _experiment_planning_service().validate(
            proposal_request_key=proposal_request_key
        )
        _emit({"plan_key": plan.plan_key, "validation": report, "writes": []})
        if not report.valid:
            raise typer.Exit(code=2)
    except (AgentAuthorityError, HypothesisRegistryError, ValueError, OSError, TypeError) as exc:
        _fail(exc)


@experiment_plan_app.command("show")
def experiment_plan_show(plan_key: str) -> None:
    try:
        _emit({"plan": _experiment_planning_service().show_plan(plan_key)})
    except (AgentAuthorityError, HypothesisRegistryError, ValueError, TypeError) as exc:
        _fail(exc)


@experiment_plan_app.command("list")
def experiment_plan_list(
    limit: int = typer.Option(100, min=1, max=500),
    offset: int = typer.Option(0, min=0),
) -> None:
    try:
        _emit({
            "plans": _experiment_planning_service().list_plans(limit=limit, offset=offset),
            "limit": limit,
            "offset": offset,
        })
    except (AgentAuthorityError, HypothesisRegistryError, ValueError, TypeError) as exc:
        _fail(exc)


@experiment_plan_app.command("materialize")
def experiment_plan_materialize(
    proposal_request_key: str = typer.Option(..., "--proposal-request-key"),
) -> None:
    """Create the Hypothesis and planned Experiments from an approved proposal request."""
    try:
        plan, report, result = _experiment_planning_service().materialize(
            proposal_request_key=proposal_request_key
        )
        _emit({
            "plan_key": plan.plan_key,
            "validation": report,
            "materialization": result,
            "experiment_execution_started": False,
            "evidence_created": False,
        })
    except (AgentAuthorityError, HypothesisRegistryError, ValueError, OSError, TypeError) as exc:
        _fail(exc)


@experiment_plan_app.command("engineering-request")
def experiment_plan_engineering_request(
    plan_key: str = typer.Option(..., "--plan-key"),
    requested_by: str = typer.Option("research:planner", "--requested-by"),
) -> None:
    """Submit an Engineering request for an already materialized plan."""
    try:
        request = _experiment_planning_service().create_engineering_request(
            plan_key=plan_key,
            requested_by=requested_by,
        )
        _emit({"request": request, "submitted": request.status == AgentRequestStatus.SUBMITTED})
    except (AgentAuthorityError, HypothesisRegistryError, ValueError, TypeError) as exc:
        _fail(exc)


@experiment_plan_app.command("operator-request")
def experiment_plan_operator_request(
    plan_key: str = typer.Option(..., "--plan-key"),
    requested_by: str = typer.Option("research:planner", "--requested-by"),
) -> None:
    """Create a draft Operator isolated-run request; this command does not submit or execute it."""
    try:
        request = _experiment_planning_service().create_operator_request(
            plan_key=plan_key,
            requested_by=requested_by,
        )
        _emit({
            "request": request,
            "draft": request.status == AgentRequestStatus.DRAFT,
            "executed": False,
        })
    except (AgentAuthorityError, HypothesisRegistryError, ValueError, TypeError) as exc:
        _fail(exc)


@evidence_app.command("build")
def evidence_build(
    artifact_dir: Path = typer.Option(..., "--artifact-dir"),
    hypothesis_key: str | None = typer.Option(None, "--hypothesis-key"),
    plan_key: str | None = typer.Option(None, "--plan-key"),
    plan_fingerprint: str | None = typer.Option(None, "--plan-fingerprint"),
    append: bool = typer.Option(True, "--append/--dry-run"),
) -> None:
    try:
        _emit(
            _evidence_service().build_evidence(
                artifact_directory=artifact_dir,
                hypothesis_key=hypothesis_key,
                plan_key=plan_key,
                plan_fingerprint=plan_fingerprint,
                append=append,
            )
        )
    except (AgentAuthorityError, HypothesisRegistryError, ValueError, OSError, TypeError) as exc:
        _fail(exc)


@evidence_app.command("show")
def evidence_show(key: str) -> None:
    try:
        _emit(_evidence_service().show_evidence(key))
    except (AgentAuthorityError, HypothesisRegistryError, ValueError) as exc:
        _fail(exc)


@evidence_app.command("aggregate")
def evidence_aggregate(
    hypothesis_key: str = typer.Option(..., "--hypothesis-key"),
) -> None:
    try:
        _emit(_evidence_service().aggregate(hypothesis_key=hypothesis_key))
    except (AgentAuthorityError, HypothesisRegistryError, ValueError) as exc:
        _fail(exc)


@decision_app.command("draft")
def decision_draft(
    hypothesis_key: str = typer.Option(..., "--hypothesis-key"),
    requested_by: str = typer.Option("research:evidence-engine", "--requested-by"),
    submit: bool = typer.Option(True, "--submit/--draft-only"),
) -> None:
    try:
        _emit(
            _evidence_service().draft_decision(
                hypothesis_key=hypothesis_key,
                requested_by=requested_by,
                submit=submit,
            )
        )
    except (AgentAuthorityError, HypothesisRegistryError, ValueError) as exc:
        _fail(exc)


@decision_app.command("review")
def decision_review(
    request_key: str,
    reviewer_id: str = typer.Option(..., "--reviewer-id"),
) -> None:
    try:
        _emit(_evidence_service().review_decision(request_key=request_key, reviewer_id=reviewer_id))
    except (AgentAuthorityError, HypothesisRegistryError, ValueError) as exc:
        _fail(exc)


@decision_app.command("approve")
def decision_approve(
    request_key: str,
    reviewer_id: str = typer.Option(..., "--reviewer-id"),
) -> None:
    try:
        _emit(_evidence_service().approve_decision(request_key=request_key, reviewer_id=reviewer_id))
    except (AgentAuthorityError, HypothesisRegistryError, ValueError) as exc:
        _fail(exc)


@decision_app.command("reject")
def decision_reject(
    request_key: str,
    reviewer_id: str = typer.Option(..., "--reviewer-id"),
    reason_file: Path | None = typer.Option(None, "--reason-file"),
) -> None:
    try:
        reason = _load_object(reason_file) if reason_file else None
        _emit(_evidence_service().reject_decision(request_key=request_key, reviewer_id=reviewer_id, reason=reason))
    except (AgentAuthorityError, HypothesisRegistryError, ValueError, OSError, TypeError) as exc:
        _fail(exc)


@scheduler_app.command("next")
def scheduler_next(
    budget_file: Path | None = typer.Option(None, "--budget-file"),
) -> None:
    """Compute the next research action without writing queue or Agent Request rows."""
    try:
        budget = _load_object(budget_file) if budget_file else None
        _emit(_scheduler_service().next_action(budget=budget))
    except (AgentAuthorityError, HypothesisRegistryError, ValueError, OSError, TypeError) as exc:
        _fail(exc)


@scheduler_app.command("once")
def scheduler_once(
    requested_by: str = typer.Option("research:scheduler", "--requested-by"),
    budget_file: Path | None = typer.Option(None, "--budget-file"),
    create_request: bool = typer.Option(True, "--create-request/--queue-only"),
) -> None:
    """Run one scheduler decision and create at most one Research Scheduler Request."""
    try:
        budget = _load_object(budget_file) if budget_file else None
        _emit(
            _scheduler_service().once(
                requested_by=requested_by,
                budget=budget,
                create_request=create_request,
            )
        )
    except (AgentAuthorityError, HypothesisRegistryError, ValueError, OSError, TypeError) as exc:
        _fail(exc)


@scheduler_app.command("run")
def scheduler_run(
    requested_by: str = typer.Option("research:scheduler", "--requested-by"),
    max_iterations: int = typer.Option(1, "--max-iterations", min=1, max=10),
    budget_file: Path | None = typer.Option(None, "--budget-file"),
) -> None:
    """Run bounded scheduler iterations; it stops on WAIT/BLOCK/STOP/CONTINUE."""
    try:
        budget = _load_object(budget_file) if budget_file else None
        _emit(
            _scheduler_service().run(
                requested_by=requested_by,
                max_iterations=max_iterations,
                budget=budget,
            )
        )
    except (AgentAuthorityError, HypothesisRegistryError, ValueError, OSError, TypeError) as exc:
        _fail(exc)


@scheduler_app.command("status")
def scheduler_status() -> None:
    try:
        _emit(_scheduler_service().status())
    except (AgentAuthorityError, HypothesisRegistryError, ValueError, OSError, TypeError) as exc:
        _fail(exc)


@scheduler_app.command("queue")
def scheduler_queue(
    limit: int = typer.Option(100, min=1, max=500),
    offset: int = typer.Option(0, min=0),
) -> None:
    try:
        _emit(_scheduler_service().queue(limit=limit, offset=offset))
    except (AgentAuthorityError, HypothesisRegistryError, ValueError, OSError, TypeError) as exc:
        _fail(exc)


@engineering_app.command("graph")
def engineering_graph(
    plan_key: str | None = typer.Option(None, "--plan-key"),
) -> None:
    try:
        _emit(_engineering_service().graph(plan_key=plan_key))
    except (AgentAuthorityError, HypothesisRegistryError, ValueError, OSError, TypeError) as exc:
        _fail(exc)


@engineering_app.command("locate")
def engineering_locate(
    plan_key: str | None = typer.Option(None, "--plan-key"),
) -> None:
    try:
        _emit(_engineering_service().locate(plan_key=plan_key))
    except (AgentAuthorityError, HypothesisRegistryError, ValueError, OSError, TypeError) as exc:
        _fail(exc)


@engineering_app.command("contract")
def engineering_contract(
    plan_key: str | None = typer.Option(None, "--plan-key"),
) -> None:
    try:
        _emit(_engineering_service().contract(plan_key=plan_key))
    except (AgentAuthorityError, HypothesisRegistryError, ValueError, OSError, TypeError) as exc:
        _fail(exc)


@engineering_app.command("plan")
def engineering_plan(
    plan_key: str | None = typer.Option(None, "--plan-key"),
) -> None:
    try:
        _emit(_engineering_service().plan(plan_key=plan_key))
    except (AgentAuthorityError, HypothesisRegistryError, ValueError, OSError, TypeError) as exc:
        _fail(exc)


@engineering_app.command("validate")
def engineering_validate(
    plan_key: str | None = typer.Option(None, "--plan-key"),
) -> None:
    try:
        result = _engineering_service().validate(plan_key=plan_key)
        _emit(result)
        if not result["validation"].valid:
            raise typer.Exit(code=2)
    except (AgentAuthorityError, HypothesisRegistryError, ValueError, OSError, TypeError) as exc:
        _fail(exc)


@pattern_app.command("discover")
def pattern_discover(
    input_file: Path | None = typer.Option(None, "--input"),
    persist: bool = typer.Option(False, "--persist/--dry-run"),
    families: int = typer.Option(10, "--families", min=1, max=10),
    patterns_per_family: int = typer.Option(20, "--patterns-per-family", min=1, max=20),
) -> None:
    """Discover patterns. Dry-run by default; no Request, Registry, training, or code writes."""
    try:
        result = _pattern_service().discover(
            draws=_load_draw_records(input_file),
            budget=_pattern_budget(families, patterns_per_family),
            persist=persist,
        )
        _emit(result)
    except (AgentAuthorityError, HypothesisRegistryError, ValueError, OSError, TypeError) as exc:
        _fail(exc)


@pattern_app.command("list")
def pattern_list(
    limit: int = typer.Option(100, min=1, max=500),
    offset: int = typer.Option(0, min=0),
) -> None:
    try:
        _emit(_pattern_service().list_patterns(limit=limit, offset=offset))
    except (AgentAuthorityError, HypothesisRegistryError, KeyError, ValueError, OSError, TypeError) as exc:
        _fail(exc)


@pattern_app.command("show")
def pattern_show(pattern_key: str) -> None:
    try:
        _emit(_pattern_service().show_pattern(pattern_key))
    except (AgentAuthorityError, HypothesisRegistryError, KeyError, ValueError, OSError, TypeError) as exc:
        _fail(exc)


@pattern_app.command("validate")
def pattern_validate(
    input_file: Path | None = typer.Option(None, "--input"),
) -> None:
    try:
        service = _pattern_service()
        result = service.discover(draws=_load_draw_records(input_file), persist=False)
        reports = [service.validator.validate_candidate(pattern) for pattern in result["patterns"]]
        _emit({"valid": all(report.valid for report in reports), "reports": reports, "writes": []})
        if not all(report.valid for report in reports):
            raise typer.Exit(code=2)
    except (AgentAuthorityError, HypothesisRegistryError, ValueError, OSError, TypeError) as exc:
        _fail(exc)


@pattern_app.command("compare-null")
def pattern_compare_null(
    length: int = typer.Option(..., "--length", min=3, max=6),
    start: int = typer.Option(..., "--start", min=1, max=33),
    difference: int = typer.Option(..., "--difference", min=1, max=32),
    input_file: Path | None = typer.Option(None, "--input"),
) -> None:
    try:
        service = _pattern_service()
        draws = _load_draw_records(input_file)
        if draws is None:
            draws = list(service.repository.load_history())
        _emit({
            "signature": {"length": length, "start": start, "difference": difference},
            "nulls": service.compare_null(signature=(length, start, difference), draws=draws),
            "writes": [],
        })
    except (AgentAuthorityError, HypothesisRegistryError, ValueError, OSError, TypeError) as exc:
        _fail(exc)


@pattern_app.command("arithmetic")
def pattern_arithmetic(
    input_file: Path | None = typer.Option(None, "--input"),
) -> None:
    try:
        service = _pattern_service()
        draws = _load_draw_records(input_file)
        if draws is None:
            draws = list(service.repository.load_history())
        _emit({"patterns": service.arithmetic(draws=draws), "writes": []})
    except (AgentAuthorityError, HypothesisRegistryError, ValueError, OSError, TypeError) as exc:
        _fail(exc)


@pattern_app.command("screen")
def pattern_screen(
    input_file: Path | None = typer.Option(None, "--input"),
    persist: bool = typer.Option(False, "--persist/--dry-run"),
) -> None:
    try:
        service = _pattern_service()
        discovered = service.discover(draws=_load_draw_records(input_file), persist=persist)
        _emit(service.screen(discovered["patterns"], persist=persist))
    except (AgentAuthorityError, HypothesisRegistryError, ValueError, OSError, TypeError) as exc:
        _fail(exc)


@pattern_app.command("feature-synthesize")
def pattern_feature_synthesize(
    input_file: Path | None = typer.Option(None, "--input"),
    persist: bool = typer.Option(False, "--persist/--dry-run"),
) -> None:
    try:
        service = _pattern_service()
        discovered = service.discover(draws=_load_draw_records(input_file), persist=persist)
        screened = service.screen(discovered["patterns"], persist=persist)
        accepted = [result.pattern for result in screened["results"] if result.accepted]
        _emit(service.synthesize_features(accepted, persist=persist))
    except (AgentAuthorityError, HypothesisRegistryError, ValueError, OSError, TypeError) as exc:
        _fail(exc)


@pattern_app.command("strategy-synthesize")
def pattern_strategy_synthesize(
    input_file: Path | None = typer.Option(None, "--input"),
    persist: bool = typer.Option(False, "--persist/--dry-run"),
) -> None:
    try:
        service = _pattern_service()
        discovered = service.discover(draws=_load_draw_records(input_file), persist=persist)
        screened = service.screen(discovered["patterns"], persist=persist)
        accepted = [result.pattern for result in screened["results"] if result.accepted]
        features = service.synthesize_features(accepted)["features"]
        _emit(service.synthesize_strategies(features, patterns=accepted, persist=persist))
    except (AgentAuthorityError, HypothesisRegistryError, ValueError, OSError, TypeError) as exc:
        _fail(exc)


@pattern_app.command("submit")
def pattern_submit(
    input_file: Path | None = typer.Option(None, "--input"),
    requested_by: str = typer.Option("research:pattern-discovery", "--requested-by"),
) -> None:
    """Submit one pattern-derived Research Proposal Request; does not change Registry."""
    try:
        service = _pattern_service()
        cycle = service.cycle(draws=_load_draw_records(input_file), persist=False, submit=True, requested_by=requested_by)
        _emit({"submitted_request_key": cycle.submitted_request_key, "cycle": cycle, "registry_updated": False})
    except (AgentAuthorityError, HypothesisRegistryError, ValueError, OSError, TypeError) as exc:
        _fail(exc)


@pattern_app.command("cycle")
def pattern_cycle(
    input_file: Path | None = typer.Option(None, "--input"),
    persist: bool = typer.Option(False, "--persist/--dry-run"),
    submit: bool = typer.Option(False, "--submit/--no-submit"),
    requested_by: str = typer.Option("research:pattern-discovery", "--requested-by"),
) -> None:
    try:
        _emit(
            _pattern_service().cycle(
                draws=_load_draw_records(input_file),
                persist=persist,
                submit=submit,
                requested_by=requested_by,
            )
        )
    except (AgentAuthorityError, HypothesisRegistryError, ValueError, OSError, TypeError) as exc:
        _fail(exc)


@pattern_app.command("status")
def pattern_status() -> None:
    try:
        _emit(_pattern_service().status())
    except (AgentAuthorityError, HypothesisRegistryError, ValueError, OSError, TypeError) as exc:
        _fail(exc)


@agent_app.command("request-create")
def agent_request_create(input_file: Path = typer.Option(..., "--input")) -> None:
    try:
        data = _load_object(input_file)
        _, service = _agent_context()
        result = service.create_draft(
            request_key=data["request_key"],
            request_type=_enum(AgentRequestType, data["request_type"]),
            requested_by_role=_agent_role(data["requested_by_role"]),
            requested_by=data["requested_by"],
            title=data["title"],
            summary=data.get("summary", ""),
            payload=data["payload"],
            environment=data.get("environment", "isolated"),
            risk_level=(
                None
                if data.get("risk_level") is None
                else _enum(AgentRiskLevel, data["risk_level"])
            ),
            hypothesis_key=data.get("hypothesis_key"),
            experiment_key=data.get("experiment_key"),
            parent_request_key=data.get("parent_request_key"),
            metadata=data.get("metadata", {}),
        )
        _emit({"request": result})
    except (AgentAuthorityError, HypothesisRegistryError, KeyError, TypeError) as exc:
        _fail(exc)


@agent_app.command("request-list")
def agent_request_list(
    status: str | None = typer.Option(None),
    request_type: str | None = typer.Option(None),
    requested_by_role: str | None = typer.Option(None),
    risk_level: str | None = typer.Option(None),
    created_after: str | None = typer.Option(None),
    created_before: str | None = typer.Option(None),
    limit: int = typer.Option(100, min=1, max=1000),
    offset: int = typer.Option(0, min=0),
) -> None:
    try:
        repository, _ = _agent_context()
        requests = repository.list_requests(
            status=None if status is None else _enum(AgentRequestStatus, status),
            request_type=None if request_type is None else _enum(AgentRequestType, request_type),
            requested_by_role=(
                None if requested_by_role is None else _agent_role(requested_by_role)
            ),
            risk_level=None if risk_level is None else _enum(AgentRiskLevel, risk_level),
            created_after=None if created_after is None else datetime.fromisoformat(created_after),
            created_before=None if created_before is None else datetime.fromisoformat(created_before),
            limit=limit,
            offset=offset,
        )
        _emit({"requests": requests, "limit": limit, "offset": offset})
    except (AgentAuthorityError, HypothesisRegistryError, ValueError) as exc:
        _fail(exc)


@agent_app.command("request-show")
def agent_request_show(request_key: str) -> None:
    try:
        repository, _ = _agent_context()
        _emit({"request": repository.get_request(request_key)})
    except AgentAuthorityError as exc:
        _fail(exc)


def _agent_actor_options(
    actor_role: str,
    actor_id: str,
) -> tuple[AgentRole, str]:
    return _agent_role(actor_role), actor_id


@agent_app.command("request-submit")
def agent_request_submit(
    request_key: str,
    actor_role: str = typer.Option(...),
    actor_id: str = typer.Option(...),
    environment: str = typer.Option("isolated"),
) -> None:
    try:
        _, service = _agent_context()
        role, actor = _agent_actor_options(actor_role, actor_id)
        _emit({"request": service.submit(request_key, actor_role=role, actor_id=actor, environment=environment)})
    except (AgentAuthorityError, HypothesisRegistryError) as exc:
        _fail(exc)


@agent_app.command("request-review")
def agent_request_review(
    request_key: str,
    reviewer_role: str = typer.Option(...),
    reviewer_id: str = typer.Option(...),
    environment: str = typer.Option("isolated"),
) -> None:
    try:
        _, service = _agent_context()
        _emit(
            {
                "request": service.begin_review(
                    request_key,
                    reviewer_role=_agent_role(reviewer_role),
                    reviewer_id=reviewer_id,
                    environment=environment,
                )
            }
        )
    except (AgentAuthorityError, HypothesisRegistryError) as exc:
        _fail(exc)


def _review_decision(
    request_key: str,
    input_file: Path,
    *,
    approve: bool,
) -> None:
    try:
        data = _load_object(input_file)
        _, service = _agent_context()
        method = service.approve if approve else service.reject
        result = method(
            request_key,
            reviewer_role=_agent_role(data["reviewer_role"]),
            reviewer_id=data["reviewer_id"],
            reason=data.get("reason", {}),
            environment=data.get("environment", "isolated"),
        )
        _emit({"request": result})
    except (AgentAuthorityError, HypothesisRegistryError, KeyError, TypeError) as exc:
        _fail(exc)


@agent_app.command("request-approve")
def agent_request_approve(
    request_key: str,
    input_file: Path = typer.Option(..., "--input"),
) -> None:
    _review_decision(request_key, input_file, approve=True)


@agent_app.command("request-reject")
def agent_request_reject(
    request_key: str,
    input_file: Path = typer.Option(..., "--input"),
) -> None:
    _review_decision(request_key, input_file, approve=False)


@agent_app.command("request-cancel")
def agent_request_cancel(
    request_key: str,
    input_file: Path = typer.Option(..., "--input"),
) -> None:
    try:
        data = _load_object(input_file)
        _, service = _agent_context()
        result = service.cancel(
            request_key,
            actor_role=_agent_role(data["actor_role"]),
            actor_id=data["actor_id"],
            reason=data.get("reason", {}),
            environment=data.get("environment", "isolated"),
        )
        _emit({"request": result})
    except (AgentAuthorityError, HypothesisRegistryError, KeyError, TypeError) as exc:
        _fail(exc)


@agent_app.command("execution-start")
def agent_execution_start(
    request_key: str,
    input_file: Path = typer.Option(..., "--input"),
) -> None:
    try:
        data = _load_object(input_file)
        _, service = _agent_context()
        request, execution = service.begin_execution(
            request_key,
            executor_role=_agent_role(data["executor_role"]),
            executor_id=data["executor_id"],
            environment=data.get("environment", "isolated"),
            run_id=data.get("run_id"),
        )
        _emit({"request": request, "execution": execution})
    except (AgentAuthorityError, HypothesisRegistryError, KeyError, TypeError) as exc:
        _fail(exc)


@agent_app.command("execution-complete")
def agent_execution_complete(
    request_key: str,
    execution_id: int,
    input_file: Path = typer.Option(..., "--input"),
) -> None:
    try:
        data = _load_object(input_file)
        _, service = _agent_context()
        request, execution = service.complete_execution(
            request_key,
            execution_id=execution_id,
            executor_role=_agent_role(data["executor_role"]),
            executor_id=data["executor_id"],
            result=data.get("result", {}),
            artifact_paths=data.get("artifact_paths", []),
        )
        _emit({"request": request, "execution": execution})
    except (AgentAuthorityError, HypothesisRegistryError, KeyError, TypeError) as exc:
        _fail(exc)


@agent_app.command("execution-fail")
def agent_execution_fail(
    request_key: str,
    execution_id: int,
    input_file: Path = typer.Option(..., "--input"),
) -> None:
    try:
        data = _load_object(input_file)
        _, service = _agent_context()
        request, execution = service.fail_execution(
            request_key,
            execution_id=execution_id,
            executor_role=_agent_role(data["executor_role"]),
            executor_id=data["executor_id"],
            error=data.get("error", {}),
        )
        _emit({"request": request, "execution": execution})
    except (AgentAuthorityError, HypothesisRegistryError, KeyError, TypeError) as exc:
        _fail(exc)


@agent_app.command("decisions")
def agent_decisions(request_key: str) -> None:
    try:
        repository, _ = _agent_context()
        _emit({"decisions": repository.list_decisions(request_key)})
    except AgentAuthorityError as exc:
        _fail(exc)


@agent_app.command("authorize")
def agent_authorize(
    role: str = typer.Option(...),
    action: str = typer.Option(...),
    request_type: str | None = typer.Option(None),
    request_status: str | None = typer.Option(None),
    environment: str = typer.Option("isolated"),
    risk_level: str | None = typer.Option(None),
) -> None:
    """Dry-run the policy engine without reading or writing the database."""
    try:
        decision = AgentAuthorityPolicy().authorize(
            AuthorizationContext(
                role=_agent_role(role),
                action=_enum(AgentAction, action),
                request_type=request_type,
                request_status=request_status,
                environment=environment,
                risk_level=risk_level,
            )
        )
        _emit({"authorization": decision})
        if not decision.allowed:
            raise typer.Exit(code=2)
    except (AgentAuthorityError, HypothesisRegistryError) as exc:
        _fail(exc)


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


@draw_sync_app.command("once")
def draw_sync_once(
    source: str = typer.Option("zhcw", "--source"),
    history: bool = typer.Option(True, "--history/--no-history"),
    csv_file: str | None = typer.Option(None, "--csv-file"),
    lock_timeout_seconds: float = typer.Option(0.0, "--lock-timeout-seconds", min=0.0),
) -> None:
    try:
        result = _draw_sync_service().once(
            source=source,
            history=history,
            csv_file=csv_file,
            lock_timeout_seconds=lock_timeout_seconds,
        )
        _emit({"result": result})
    except (ValueError, OSError, TypeError) as exc:
        _fail(exc)


@draw_sync_app.command("watch")
def draw_sync_watch(
    interval_seconds: int = typer.Option(900, "--interval-seconds", min=300),
    hot_interval_seconds: int = typer.Option(300, "--hot-interval-seconds", min=300),
    cold_interval_seconds: int = typer.Option(3600, "--cold-interval-seconds", min=900),
    timezone: str = typer.Option("Asia/Shanghai", "--timezone"),
    resume_on_event: bool = typer.Option(False, "--resume-on-event/--no-resume-on-event"),
    once: bool = typer.Option(False, "--once"),
) -> None:
    try:
        DrawSyncWatch(
            policy=DrawSyncSchedulePolicy(
                interval_seconds=interval_seconds,
                hot_interval_seconds=hot_interval_seconds,
                cold_interval_seconds=cold_interval_seconds,
                timezone=timezone,
            ),
            resume_on_event=resume_on_event,
        ).run(once=once)
    except (ValueError, OSError, TypeError) as exc:
        _fail(exc)


@draw_sync_app.command("status")
def draw_sync_status() -> None:
    try:
        _emit(_draw_sync_service().status())
    except (ValueError, OSError, TypeError) as exc:
        _fail(exc)


@draw_sync_app.command("events")
def draw_sync_events(
    limit: int = typer.Option(100, "--limit", min=1, max=1000),
    offset: int = typer.Option(0, "--offset", min=0),
) -> None:
    try:
        _emit(_draw_sync_service().events(limit=limit, offset=offset))
    except (ValueError, OSError, TypeError) as exc:
        _fail(exc)


@forward_app.command("reconcile")
def forward_reconcile(event_key: str | None = typer.Option(None, "--event-key")) -> None:
    try:
        _emit(_forward_state_service().reconcile(event_key=event_key))
    except (ValueError, OSError, TypeError) as exc:
        _fail(exc)


@forward_app.command("status")
def forward_status() -> None:
    try:
        _emit(_forward_state_service().status())
    except (ValueError, OSError, TypeError) as exc:
        _fail(exc)


@training_resume_app.command("check")
def training_resume_check(event_key: str | None = typer.Option(None, "--event-key")) -> None:
    try:
        _emit(_training_resume_service().check(event_key=event_key))
    except (ValueError, OSError, TypeError) as exc:
        _fail(exc)


@training_resume_app.command("execute")
def training_resume_execute(event_key: str | None = typer.Option(None, "--event-key")) -> None:
    try:
        _emit(_training_resume_service().execute(event_key=event_key))
    except (ValueError, OSError, TypeError) as exc:
        _fail(exc)


@training_resume_app.command("history")
def training_resume_history(
    limit: int = typer.Option(100, "--limit", min=1, max=1000),
    offset: int = typer.Option(0, "--offset", min=0),
) -> None:
    try:
        _emit(_training_resume_service().history(limit=limit, offset=offset))
    except (ValueError, OSError, TypeError) as exc:
        _fail(exc)


@research_runtime_app.command("status")
def research_runtime_status() -> None:
    try:
        _emit(_research_runtime().status())
    except (ValueError, OSError, TypeError) as exc:
        _fail(exc)


@research_runtime_app.command("once")
def research_runtime_once() -> None:
    try:
        _emit({"result": _research_runtime().once()})
    except (ValueError, OSError, TypeError) as exc:
        _fail(exc)


@research_runtime_app.command("run")
def research_runtime_run(
    interval_seconds: float = typer.Option(1.0, "--interval-seconds", min=0.0),
    max_cycles: int | None = typer.Option(None, "--max-cycles", min=1),
    research_cpu: int = typer.Option(12, "--research-cpu", min=1),
    forward_cpu: int = typer.Option(4, "--forward-cpu", min=0),
    total_memory_gb: int = typer.Option(20, "--total-memory-gb", min=1),
    research_memory_gb: int = typer.Option(18, "--research-memory-gb", min=1),
    forward_memory_gb: int = typer.Option(2, "--forward-memory-gb", min=0),
    daily_cycle_limit: int = typer.Option(100, "--daily-cycle-limit", min=1),
) -> None:
    try:
        _emit(
            _resident_research_runtime(
                interval_seconds=interval_seconds,
                max_cycles=max_cycles,
                research_cpu=research_cpu,
                forward_cpu=forward_cpu,
                total_memory_gb=total_memory_gb,
                research_memory_gb=research_memory_gb,
                forward_memory_gb=forward_memory_gb,
                daily_cycle_limit=daily_cycle_limit,
            ).run()
        )
    except (ValueError, OSError, TypeError, RuntimeError) as exc:
        _fail(exc)


@information_theory_preregistration_app.command("validate")
def information_theory_preregistration_validate(
    input_file: Path = typer.Option(..., "--input"),
) -> None:
    """Validate contract completeness without running any statistical method."""
    try:
        _emit(validate_preregistration(load_preregistration(input_file)))
    except (
        InformationTheoryValidationError,
        json.JSONDecodeError,
        OSError,
        TypeError,
        ValueError,
    ) as exc:
        _fail(exc)


@information_theory_preregistration_app.command("freeze")
def information_theory_preregistration_freeze(
    input_file: Path = typer.Option(..., "--input"),
    output_dir: Path = typer.Option(..., "--output-dir"),
) -> None:
    """Freeze one validated preregistration in a digest-addressed directory."""
    try:
        result = freeze_preregistration(
            load_preregistration(input_file),
            output_dir=output_dir,
            repo_root=ROOT_DIR,
        )
        _emit(
            {
                "status": "FROZEN",
                "digest": result.digest,
                "output_path": str(result.output_path),
                "preregistration": result.payload,
            }
        )
    except (
        InformationTheoryValidationError,
        json.JSONDecodeError,
        OSError,
        TypeError,
        ValueError,
    ) as exc:
        _fail(exc)


@information_theory_preregistration_app.command("show")
def information_theory_preregistration_show(
    digest: str = typer.Option(..., "--digest"),
    artifact_dir: Path = typer.Option(
        ROOT_DIR / "runtime/research-os/information-theory/preregistrations",
        "--artifact-dir",
    ),
) -> None:
    """Show a frozen preregistration by its immutable digest."""
    try:
        _emit(
            show_preregistration(
                digest=digest,
                search_paths=(
                    artifact_dir,
                    ROOT_DIR / CANONICAL_PREREGISTRATION_RELATIVE_PATH,
                ),
            )
        )
    except (
        InformationTheoryValidationError,
        json.JSONDecodeError,
        OSError,
        TypeError,
        ValueError,
    ) as exc:
        _fail(exc)


@information_theory_app.command("status")
def information_theory_status(
    input_file: Path = typer.Option(
        ROOT_DIR / M4_MANIFEST_RELATIVE_PATH,
        "--input",
    ),
) -> None:
    """Emit P1/P2 phase state without dispatching research work."""
    try:
        _emit(build_m4_status(load_m4_manifest(input_file)))
    except (
        InformationTheoryValidationError,
        ResearchOSValidationError,
        json.JSONDecodeError,
        OSError,
        TypeError,
        ValueError,
    ) as exc:
        _fail(exc)


@information_theory_synthetic_app.command("validate-config")
def information_theory_synthetic_validate_config(
    input_file: Path = typer.Option(..., "--input"),
) -> None:
    """Validate the frozen P2.1 workload contract without executing it."""
    try:
        manifest = load_synthetic_run_manifest(input_file)
        _emit(
            {
                "valid": True,
                "phase": "M4-P2.1",
                "status": manifest.payload["status"],
                "artifact_digest": manifest.artifact_digest,
                "scenario_count": len(manifest.scenarios),
                "scale_count": len(manifest.scales),
                "large_replicates_executed": False,
            }
        )
    except (
        HypothesisRegistryError,
        json.JSONDecodeError,
        OSError,
        TypeError,
        ValueError,
    ) as exc:
        _fail(exc)


@information_theory_synthetic_app.command("generate")
def information_theory_synthetic_generate(
    input_file: Path = typer.Option(..., "--input"),
    scale_id: str = typer.Option(..., "--scale"),
    seed: int = typer.Option(..., "--seed"),
    output_dir: Path = typer.Option(..., "--output-dir"),
) -> None:
    """Generate one digest-addressed null dataset; formal replicate runs stay gated."""
    try:
        dirty = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT_DIR,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if dirty:
            raise ValueError("dirty_worktree: synthetic artifact generation requires a clean tree")
        manifest = load_synthetic_run_manifest(input_file)
        artifact = generate_null_dataset(
            manifest,
            scale_id=scale_id,
            seed=seed,
        ).to_dict()
        destination = output_dir / artifact["artifact_digest"] / "dataset.json"
        if destination.exists():
            existing = json.loads(destination.read_text(encoding="utf-8"))
            if existing != artifact:
                raise ValueError("digest collision: existing synthetic artifact differs")
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(
                json.dumps(artifact, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                encoding="utf-8",
            )
        _emit(
            {
                "status": "GENERATED",
                "artifact_digest": artifact["artifact_digest"],
                "draw_digest": artifact["draw_digest"],
                "target_digest": artifact["target_digest"],
                "output_path": str(destination),
            }
        )
    except (
        HypothesisRegistryError,
        json.JSONDecodeError,
        OSError,
        subprocess.CalledProcessError,
        TypeError,
        ValueError,
    ) as exc:
        _fail(exc)


def _information_theory_synthetic_execution_gate() -> None:
    _fail(
        PhaseGateError(
            "P2.3-P2.7 execution is not implemented or authorized by P2.2",
        )
    )


@information_theory_synthetic_app.command("run")
def information_theory_synthetic_run() -> None:
    """Fail closed until the remaining P2 implementation contracts exist."""
    _information_theory_synthetic_execution_gate()


@information_theory_synthetic_app.command("resume")
def information_theory_synthetic_resume() -> None:
    """Fail closed until a formal synthetic run exists."""
    _information_theory_synthetic_execution_gate()


@information_theory_synthetic_app.command("report")
def information_theory_synthetic_report() -> None:
    """Fail closed until a formal synthetic run exists."""
    _information_theory_synthetic_execution_gate()


@information_theory_synthetic_app.command("gate")
def information_theory_synthetic_gate() -> None:
    """Fail closed until P2.6 evidence exists."""
    _information_theory_synthetic_execution_gate()


@information_theory_metrics_app.command("validate")
def information_theory_metrics_validate(
    input_file: Path = typer.Option(..., "--input"),
    manifest_file: Path = typer.Option(
        ROOT_DIR
        / "configs/research-os/m4-information-theory-metric-kernel-v1.json",
        "--manifest",
    ),
) -> None:
    """Validate one P2.2 input without evaluating a formal dataset."""
    try:
        manifest = load_metric_kernel_manifest(manifest_file)
        result = validate_metric_input(_load_object(input_file))
        _emit(
            {
                **result,
                "metric_kernel_version": manifest.metric_kernel_version,
                "metric_kernel_manifest_digest": manifest.artifact_digest,
            }
        )
    except (
        HypothesisRegistryError,
        json.JSONDecodeError,
        OSError,
        TypeError,
        ValueError,
    ) as exc:
        _fail(exc)


@information_theory_metrics_app.command("evaluate")
def information_theory_metrics_evaluate(
    input_file: Path = typer.Option(..., "--input"),
    output_dir: Path = typer.Option(..., "--output-dir"),
    manifest_file: Path = typer.Option(
        ROOT_DIR
        / "configs/research-os/m4-information-theory-metric-kernel-v1.json",
        "--manifest",
    ),
) -> None:
    """Build a deterministic descriptive artifact; never a P2 gate or Evidence."""
    try:
        dirty = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT_DIR,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if dirty:
            raise ValueError(
                "dirty_worktree: formal metric artifact requires a clean tree"
            )
        manifest = load_metric_kernel_manifest(manifest_file)
        artifact = build_metric_artifact(
            _load_object(input_file),
            manifest=manifest,
            git_commit=resolve_git_commit(ROOT_DIR),
            working_tree_clean=True,
        )
        destination = (
            output_dir / artifact["artifact_digest"] / "metric-artifact.json"
        )
        if destination.exists():
            existing = _load_object(destination)
            if _normalized(existing) != _normalized(artifact):
                raise ValueError("digest collision: existing metric artifact differs")
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(
                json.dumps(artifact, ensure_ascii=False, sort_keys=True, indent=2)
                + "\n",
                encoding="utf-8",
            )
        _emit(
            {
                "status": "DESCRIPTIVE_METRIC_ARTIFACT",
                "artifact_digest": artifact["artifact_digest"],
                "issue_count": artifact["issue_count"],
                "output_path": str(destination),
                "p2_gate_result": False,
                "real_data_evidence": False,
            }
        )
    except (
        HypothesisRegistryError,
        json.JSONDecodeError,
        OSError,
        subprocess.CalledProcessError,
        TypeError,
        ValueError,
    ) as exc:
        _fail(exc)


@information_theory_metrics_app.command("show")
def information_theory_metrics_show(
    digest: str = typer.Option(..., "--digest"),
    artifact_dir: Path = typer.Option(
        ROOT_DIR / "runtime/research-os/information-theory/metrics",
        "--artifact-dir",
    ),
) -> None:
    """Show and revalidate a deterministic metric artifact."""
    try:
        artifact = show_metric_artifact(digest=digest, artifact_dir=artifact_dir)
        validate_metric_artifact(artifact)
        _emit(artifact)
    except (
        HypothesisRegistryError,
        json.JSONDecodeError,
        OSError,
        TypeError,
        ValueError,
    ) as exc:
        _fail(exc)


def _information_theory_formal_command_gate() -> None:
    try:
        require_formal_run_gate(p1_status="FROZEN", p2_status="NOT_STARTED")
    except PhaseGateError as exc:
        _fail(exc)


@information_theory_app.command("run")
def information_theory_run() -> None:
    """Fail closed until P2 measurement validation has passed."""
    _information_theory_formal_command_gate()


@information_theory_app.command("negative-controls")
def information_theory_negative_controls() -> None:
    """Fail closed during P1."""
    _information_theory_formal_command_gate()


@information_theory_app.command("power-analysis")
def information_theory_power_analysis() -> None:
    """Fail closed during P1."""
    _information_theory_formal_command_gate()


@information_theory_app.command("report")
def information_theory_report() -> None:
    """Fail closed during P1."""
    _information_theory_formal_command_gate()


@research_os_app.command("resolve")
def research_os_resolve(
    input_file: Path = typer.Option(..., "--input"),
) -> None:
    """Resolve one immutable Goal/Task manifest without dispatching any Task."""
    try:
        _emit(ResearchOSControlPlane().resolve_payload(_load_object(input_file)))
    except (ResearchOSValidationError, HypothesisRegistryError, OSError, TypeError, ValueError) as exc:
        _fail(exc)


@research_os_app.command("m4-manifest")
def research_os_m4_manifest(
    input_file: Path = typer.Option(
        ROOT_DIR / M4_MANIFEST_RELATIVE_PATH,
        "--input",
    ),
) -> None:
    """Emit the canonical digest-addressed M4 Goal/Task manifest without dispatch."""
    try:
        _emit(load_m4_manifest(input_file).to_dict(include_digest=True))
    except (
        json.JSONDecodeError,
        ResearchOSValidationError,
        OSError,
        TypeError,
        ValueError,
    ) as exc:
        _fail(exc)


@research_os_app.command("m4-status")
def research_os_m4_status(
    input_file: Path = typer.Option(
        ROOT_DIR / M4_MANIFEST_RELATIVE_PATH,
        "--input",
    ),
    external_event: str | None = typer.Option(
        None,
        "--external-event",
        help="Optional exact observed event, such as draw:2026085.",
    ),
) -> None:
    """Resolve the canonical M4 manifest into the unified read-only status report."""
    try:
        manifest = load_m4_manifest(input_file)
        if external_event is not None:
            manifest = manifest_with_external_event(
                manifest,
                event_key=external_event,
            )
        _emit(build_m4_status(manifest))
    except (
        json.JSONDecodeError,
        ResearchOSValidationError,
        OSError,
        TypeError,
        ValueError,
    ) as exc:
        _fail(exc)


@research_os_app.command("import-manifest")
def research_os_import_manifest(
    control_plane_key: str = typer.Option(..., "--control-plane-key"),
    input_file: Path = typer.Option(..., "--input"),
    source: str = typer.Option("native", "--source"),
) -> None:
    """Idempotently import one manifest into the durable shadow repository."""
    try:
        _emit(
            _research_os_repository().import_manifest(
                control_plane_key=control_plane_key,
                payload=_load_object(input_file),
                source=source,
            )
        )
    except (ResearchOSValidationError, HypothesisRegistryError, OSError, TypeError, ValueError) as exc:
        _fail(exc)


@research_os_app.command("resolve-persisted")
def research_os_resolve_persisted(
    control_plane_key: str = typer.Option(..., "--control-plane-key"),
) -> None:
    """Reload and verify durable state before recomputing the Resolution Snapshot."""
    try:
        _emit(_research_os_repository().resolve_persisted(control_plane_key=control_plane_key))
    except (ResearchOSValidationError, HypothesisRegistryError, OSError, TypeError, ValueError) as exc:
        _fail(exc)


@research_os_app.command("export-manifest")
def research_os_export_manifest(
    control_plane_key: str = typer.Option(..., "--control-plane-key"),
) -> None:
    """Export the current verified manifest with its canonical digest."""
    try:
        _emit(_research_os_repository().export_manifest(control_plane_key=control_plane_key))
    except (ResearchOSValidationError, HypothesisRegistryError, OSError, TypeError, ValueError) as exc:
        _fail(exc)


@research_os_app.command("shadow-legacy")
def research_os_shadow_legacy(
    control_plane_key: str = typer.Option(..., "--control-plane-key"),
    legacy_goal_key: str = typer.Option(..., "--legacy-goal-key"),
    input_file: Path = typer.Option(..., "--input"),
) -> None:
    """Read legacy queue/process state and persist a one-way shadow projection."""
    try:
        repository = _research_os_repository()
        _emit(
            LegacyResearchOSShadowService(repository=repository).refresh(
                control_plane_key=control_plane_key,
                base_payload=_load_object(input_file),
                legacy_goal_key=legacy_goal_key,
            )
        )
    except (ResearchOSValidationError, HypothesisRegistryError, OSError, TypeError, ValueError) as exc:
        _fail(exc)


@forward_runtime_app.command("status")
def forward_runtime_status(event_key: str | None = typer.Option(None, "--event-key")) -> None:
    try:
        _emit(_forward_runtime_service().status(event_key=event_key))
    except (ValueError, OSError, TypeError) as exc:
        _fail(exc)


@forward_runtime_app.command("run")
def forward_runtime_run(
    interval_seconds: float = typer.Option(10.0, "--interval-seconds", min=0.0),
    max_checks: int | None = typer.Option(None, "--max-checks", min=1),
) -> None:
    try:
        _emit(_resident_forward_runtime(interval_seconds=interval_seconds, max_checks=max_checks).run())
    except (ValueError, OSError, TypeError, RuntimeError) as exc:
        _fail(exc)


if __name__ == "__main__":
    app()
