from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import re
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from dehps.contracts import ContractRef, canonical_digest
from dehps.input_contracts.candidate_abi import (
    CANDIDATE_ABI_VERSION,
    CANDIDATE_CONTRACT_V1,
)
from dehps.input_contracts.feature_contract import FEATURE_CONTRACT_V1
from dehps.input_contracts.history_window import (
    HISTORY_SNAPSHOT_CONTRACT_V1,
    WINDOW_CONTRACT_V1,
)
from dehps.ranking_contract import STRICT_RANKING_CONTRACT

if TYPE_CHECKING:
    from dehps.feature_runtime.runtime import FeatureABIRuntime


RUNTIME_ENVELOPE_VERSION = "runtime_envelope.v1"
RUNTIME_DOMAIN = "ssq_red_ball"
STRICT_SCORING_CONTRACT = "dehps-scoring-strict-v1"
_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_CODE_COMMIT_PATTERN = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_ISSUE_PATTERN = re.compile(r"^[0-9]{7}$")


class RuntimeState(str, Enum):
    COMPILED_ABI = "compiled_abi"
    VERIFIED_RUNTIME = "verified_runtime"
    KERNEL_READY = "kernel_ready"
    KERNEL_EXECUTING = "kernel_executing"
    ARTIFACT_PRODUCED = "artifact_produced"


_STATE_ORDER = tuple(RuntimeState)
_NEXT_STATE = {
    current: following
    for current, following in zip(_STATE_ORDER, _STATE_ORDER[1:])
}


class RuntimeEnvelopeViolation(ValueError):
    def __init__(self, code: str, message: str, **context: Any) -> None:
        self.code = code
        self.context = context
        super().__init__(f"{code}: {message}")

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": str(self), "context": dict(self.context)}


@dataclass(frozen=True)
class RuntimeEnvelopeV1:
    envelope_version: str
    artifact_type: str
    domain: str
    state: RuntimeState
    state_path: tuple[RuntimeState, ...]
    history_contract: ContractRef
    history_snapshot_id: str
    history_snapshot_digest: str
    history_latest_issue: str | None
    history_draw_count: int
    window_contract: ContractRef
    window_artifact_digest: str
    window_spec_digest: str
    candidate_contract: ContractRef
    candidate_abi: str
    candidate_digest: str
    candidate_layout_digest: str
    candidate_package_digest: str
    feature_contract: ContractRef
    feature_abi: str
    feature_component_manifest_digest: str
    feature_layout_digest: str
    feature_runtime_digest: str
    feature_tile_count: int
    scoring_contract: str
    ranking_contract: str
    evaluation_contract: str | None
    backend: str
    code_commit: str
    abi_package_digest: str
    artifact_payload_digest: str | None = None

    def identity_payload(self) -> dict[str, Any]:
        return {
            "envelope_version": self.envelope_version,
            "artifact_type": self.artifact_type,
            "domain": self.domain,
            "state": self.state.value,
            "state_path": [state.value for state in self.state_path],
            "history": {
                "contract": self.history_contract.as_dict(),
                "snapshot_id": self.history_snapshot_id,
                "snapshot_digest": self.history_snapshot_digest,
                "latest_issue": self.history_latest_issue,
                "draw_count": self.history_draw_count,
            },
            "window": {
                "contract": self.window_contract.as_dict(),
                "artifact_digest": self.window_artifact_digest,
                "spec_digest": self.window_spec_digest,
            },
            "candidate": {
                "contract": self.candidate_contract.as_dict(),
                "abi": self.candidate_abi,
                "candidate_digest": self.candidate_digest,
                "layout_digest": self.candidate_layout_digest,
                "package_digest": self.candidate_package_digest,
            },
            "feature": {
                "contract": self.feature_contract.as_dict(),
                "abi": self.feature_abi,
                "component_manifest_digest": self.feature_component_manifest_digest,
                "layout_digest": self.feature_layout_digest,
                "runtime_digest": self.feature_runtime_digest,
                "tile_count": self.feature_tile_count,
            },
            "scoring": {"contract": self.scoring_contract, "backend": self.backend},
            "ranking": {"contract": self.ranking_contract},
            "evaluation": {"contract": self.evaluation_contract},
            "code": {"commit": self.code_commit},
            "abi_package_digest": self.abi_package_digest,
            "artifact_payload_digest": self.artifact_payload_digest,
        }

    @property
    def envelope_digest(self) -> str:
        return canonical_digest(self.identity_payload(), domain="dehps.runtime-envelope.v1")

    def as_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "envelope_digest": self.envelope_digest}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> RuntimeEnvelopeV1:
        try:
            history = _mapping(payload["history"], field="history")
            window = _mapping(payload["window"], field="window")
            candidate = _mapping(payload["candidate"], field="candidate")
            feature = _mapping(payload["feature"], field="feature")
            scoring = _mapping(payload["scoring"], field="scoring")
            ranking = _mapping(payload["ranking"], field="ranking")
            evaluation = _mapping(payload["evaluation"], field="evaluation")
            code = _mapping(payload["code"], field="code")
            state = RuntimeState(str(payload["state"]))
            raw_path = payload["state_path"]
            if not isinstance(raw_path, list):
                raise RuntimeEnvelopeViolation(
                    "runtime_envelope_parse_error",
                    "state_path must be a list",
                    field="state_path",
                )
            envelope = cls(
                envelope_version=str(payload["envelope_version"]),
                artifact_type=str(payload["artifact_type"]),
                domain=str(payload["domain"]),
                state=state,
                state_path=tuple(RuntimeState(str(value)) for value in raw_path),
                history_contract=_contract_ref(history["contract"], field="history.contract"),
                history_snapshot_id=str(history["snapshot_id"]),
                history_snapshot_digest=str(history["snapshot_digest"]),
                history_latest_issue=(
                    str(history["latest_issue"])
                    if history.get("latest_issue") is not None
                    else None
                ),
                history_draw_count=history["draw_count"],
                window_contract=_contract_ref(window["contract"], field="window.contract"),
                window_artifact_digest=str(window["artifact_digest"]),
                window_spec_digest=str(window["spec_digest"]),
                candidate_contract=_contract_ref(candidate["contract"], field="candidate.contract"),
                candidate_abi=str(candidate["abi"]),
                candidate_digest=str(candidate["candidate_digest"]),
                candidate_layout_digest=str(candidate["layout_digest"]),
                candidate_package_digest=str(candidate["package_digest"]),
                feature_contract=_contract_ref(feature["contract"], field="feature.contract"),
                feature_abi=str(feature["abi"]),
                feature_component_manifest_digest=str(feature["component_manifest_digest"]),
                feature_layout_digest=str(feature["layout_digest"]),
                feature_runtime_digest=str(feature["runtime_digest"]),
                feature_tile_count=feature["tile_count"],
                scoring_contract=str(scoring["contract"]),
                ranking_contract=str(ranking["contract"]),
                evaluation_contract=(
                    str(evaluation["contract"])
                    if evaluation.get("contract") is not None
                    else None
                ),
                backend=str(scoring["backend"]),
                code_commit=str(code["commit"]),
                abi_package_digest=str(payload["abi_package_digest"]),
                artifact_payload_digest=(
                    str(payload["artifact_payload_digest"])
                    if payload.get("artifact_payload_digest") is not None
                    else None
                ),
            )
        except RuntimeEnvelopeViolation:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeEnvelopeViolation(
                "runtime_envelope_parse_error",
                "Runtime Envelope payload is malformed",
            ) from exc
        RuntimeEnvelopeVerifier().verify(envelope)
        stored_digest = payload.get("envelope_digest")
        if not isinstance(stored_digest, str) or not _DIGEST_PATTERN.fullmatch(stored_digest):
            raise RuntimeEnvelopeViolation(
                "runtime_envelope_digest_missing",
                "serialized Runtime Envelope requires its canonical digest",
            )
        if stored_digest != envelope.envelope_digest:
            raise RuntimeEnvelopeViolation(
                "runtime_envelope_digest_mismatch",
                "serialized Runtime Envelope digest does not match its contents",
            )
        return envelope

    def transition(self, next_state: RuntimeState) -> RuntimeEnvelopeV1:
        if not isinstance(next_state, RuntimeState):
            raise RuntimeEnvelopeViolation(
                "invalid_runtime_state_transition",
                "requested Runtime Envelope state is invalid",
                requested_state=str(next_state),
            )
        expected = _NEXT_STATE.get(self.state)
        if expected is not next_state:
            raise RuntimeEnvelopeViolation(
                "invalid_runtime_state_transition",
                "Runtime Envelope state transitions must be sequential",
                current_state=self.state.value,
                expected_state=expected.value if expected else None,
                requested_state=next_state.value,
            )
        if next_state is RuntimeState.ARTIFACT_PRODUCED:
            raise RuntimeEnvelopeViolation(
                "artifact_digest_required_for_transition",
                "use produce_artifact() to enter artifact_produced",
            )
        transitioned = replace(
            self,
            state=next_state,
            state_path=(*self.state_path, next_state),
        )
        RuntimeEnvelopeVerifier().verify(transitioned)
        return transitioned

    def produce_artifact(self, payload_digest: str) -> RuntimeEnvelopeV1:
        if self.state is not RuntimeState.KERNEL_EXECUTING:
            raise RuntimeEnvelopeViolation(
                "invalid_runtime_state_transition",
                "artifacts may only be produced from kernel_executing",
                current_state=self.state.value,
            )
        _require_digest("artifact_payload_digest", payload_digest)
        produced = replace(
            self,
            state=RuntimeState.ARTIFACT_PRODUCED,
            state_path=(*self.state_path, RuntimeState.ARTIFACT_PRODUCED),
            artifact_payload_digest=payload_digest,
        )
        RuntimeEnvelopeVerifier().verify(produced)
        return produced


def _require_digest(name: str, value: str) -> None:
    if not isinstance(value, str) or not _DIGEST_PATTERN.fullmatch(value):
        raise RuntimeEnvelopeViolation(
            "invalid_runtime_envelope_digest",
            f"{name} must be a lowercase sha256 digest",
            field=name,
        )


def _mapping(value: Any, *, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RuntimeEnvelopeViolation(
            "runtime_envelope_parse_error",
            f"{field} must be an object",
            field=field,
        )
    return value


def _contract_ref(value: Any, *, field: str) -> ContractRef:
    payload = _mapping(value, field=field)
    try:
        return ContractRef(
            family=str(payload["family"]),
            semantic_version=str(payload["semantic_version"]),
            schema_version=str(payload["schema_version"]),
            normative_digest=str(payload["normative_digest"]),
            golden_suite_digest=str(payload["golden_suite_digest"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeEnvelopeViolation(
            "runtime_envelope_parse_error",
            f"{field} is not a valid ContractRef",
            field=field,
        ) from exc


class RuntimeEnvelopeCompiler:
    def compile_kernel_ready(
        self,
        runtime: FeatureABIRuntime,
        *,
        backend: str,
        code_commit: str,
        artifact_type: str = "scoring_kernel_result",
    ) -> RuntimeEnvelopeV1:
        runtime.verify()
        history = runtime.history_snapshot
        window = runtime.window_artifact
        candidate = runtime.candidate_package
        feature = runtime.feature_tiles[0]
        compiled = RuntimeEnvelopeV1(
            envelope_version=RUNTIME_ENVELOPE_VERSION,
            artifact_type=artifact_type,
            domain=RUNTIME_DOMAIN,
            state=RuntimeState.COMPILED_ABI,
            state_path=(RuntimeState.COMPILED_ABI,),
            history_contract=history.contract,
            history_snapshot_id=history.snapshot_id,
            history_snapshot_digest=history.history_digest,
            history_latest_issue=history.latest_issue,
            history_draw_count=history.draw_count,
            window_contract=window.envelope.window_contract,
            window_artifact_digest=window.artifact_digest,
            window_spec_digest=window.spec.spec_digest,
            candidate_contract=candidate.header.candidate_contract,
            candidate_abi=candidate.header.abi_version,
            candidate_digest=candidate.header.candidate_digest,
            candidate_layout_digest=candidate.header.layout_digest,
            candidate_package_digest=candidate.package_digest,
            feature_contract=feature.header.feature_contract,
            feature_abi=feature.header.abi_version,
            feature_component_manifest_digest=feature.header.component_manifest_digest,
            feature_layout_digest=feature.header.layout_digest,
            feature_runtime_digest=runtime.runtime_digest,
            feature_tile_count=len(runtime.feature_tiles),
            scoring_contract=STRICT_SCORING_CONTRACT,
            ranking_contract=STRICT_RANKING_CONTRACT,
            evaluation_contract=None,
            backend=backend,
            code_commit=code_commit,
            abi_package_digest=runtime.runtime_digest,
        )
        verifier = RuntimeEnvelopeVerifier()
        verifier.verify(compiled, runtime=runtime)
        verified = compiled.transition(RuntimeState.VERIFIED_RUNTIME)
        verifier.verify(verified, runtime=runtime)
        ready = verified.transition(RuntimeState.KERNEL_READY)
        verifier.verify(ready, runtime=runtime)
        return ready


class RuntimeEnvelopeVerifier:
    def verify(
        self,
        envelope: RuntimeEnvelopeV1,
        *,
        runtime: FeatureABIRuntime | None = None,
        expected_backend: str | None = None,
    ) -> None:
        if envelope.envelope_version != RUNTIME_ENVELOPE_VERSION:
            self._reject("unsupported_runtime_envelope", "unsupported Runtime Envelope version")
        if (
            not isinstance(envelope.artifact_type, str)
            or not envelope.artifact_type.strip()
            or envelope.domain != RUNTIME_DOMAIN
        ):
            self._reject("runtime_envelope_identity_mismatch", "invalid artifact type or domain")
        if not isinstance(envelope.state, RuntimeState):
            self._reject("runtime_state_invalid", "Runtime Envelope state is invalid")
        expected_path = _STATE_ORDER[: _STATE_ORDER.index(envelope.state) + 1]
        if envelope.state_path != expected_path:
            self._reject("runtime_state_path_mismatch", "Runtime Envelope state path is not canonical")
        if not isinstance(envelope.history_contract, ContractRef) or not envelope.history_contract.normatively_equals(
            HISTORY_SNAPSHOT_CONTRACT_V1
        ):
            self._reject("runtime_history_contract_mismatch", "Runtime Envelope history contract is invalid")
        if not isinstance(envelope.window_contract, ContractRef) or not envelope.window_contract.normatively_equals(
            WINDOW_CONTRACT_V1
        ):
            self._reject("runtime_window_contract_mismatch", "Runtime Envelope window contract is invalid")
        if not isinstance(envelope.candidate_contract, ContractRef) or not envelope.candidate_contract.normatively_equals(
            CANDIDATE_CONTRACT_V1
        ):
            self._reject("runtime_candidate_contract_mismatch", "Runtime Envelope Candidate contract is invalid")
        if not isinstance(envelope.feature_contract, ContractRef) or not envelope.feature_contract.normatively_equals(
            FEATURE_CONTRACT_V1
        ):
            self._reject("runtime_feature_contract_mismatch", "Runtime Envelope Feature contract is invalid")
        if envelope.candidate_abi != CANDIDATE_ABI_VERSION or envelope.feature_abi != "feature_abi.v1":
            self._reject("runtime_abi_version_mismatch", "Runtime Envelope ABI versions are invalid")
        if envelope.scoring_contract != STRICT_SCORING_CONTRACT:
            self._reject("runtime_scoring_contract_mismatch", "Runtime Envelope scoring contract is invalid")
        if envelope.ranking_contract != STRICT_RANKING_CONTRACT:
            self._reject("runtime_ranking_contract_mismatch", "Runtime Envelope ranking contract is invalid")
        if envelope.evaluation_contract is not None and (
            not isinstance(envelope.evaluation_contract, str)
            or not envelope.evaluation_contract.strip()
        ):
            self._reject("runtime_evaluation_contract_invalid", "Runtime Envelope evaluation contract is invalid")
        if not isinstance(envelope.backend, str) or not envelope.backend.strip():
            self._reject("runtime_backend_missing", "Runtime Envelope backend must be explicit")
        if expected_backend is not None and envelope.backend != expected_backend:
            self._reject(
                "runtime_backend_mismatch",
                "Runtime Envelope backend does not match the selected backend",
                expected_backend=expected_backend,
                actual_backend=envelope.backend,
            )
        if not isinstance(envelope.code_commit, str) or not _CODE_COMMIT_PATTERN.fullmatch(
            envelope.code_commit
        ):
            self._reject("runtime_code_commit_invalid", "Runtime Envelope requires a full code commit SHA")
        if (
            isinstance(envelope.feature_tile_count, bool)
            or not isinstance(envelope.feature_tile_count, int)
            or envelope.feature_tile_count < 1
        ):
            self._reject("runtime_feature_tile_count_invalid", "Runtime Envelope requires Feature tiles")
        if not isinstance(envelope.history_snapshot_id, str) or not envelope.history_snapshot_id.strip():
            self._reject("runtime_history_snapshot_id_missing", "Runtime Envelope snapshot id is required")
        if (
            isinstance(envelope.history_draw_count, bool)
            or not isinstance(envelope.history_draw_count, int)
            or envelope.history_draw_count < 0
        ):
            self._reject("runtime_history_draw_count_invalid", "Runtime Envelope draw_count is invalid")
        _require_digest("history_snapshot_digest", envelope.history_snapshot_digest)
        if envelope.history_draw_count == 0:
            if envelope.history_latest_issue is not None:
                self._reject("runtime_history_latest_issue_invalid", "empty history must have latest_issue=null")
        elif (
            not isinstance(envelope.history_latest_issue, str)
            or not _ISSUE_PATTERN.fullmatch(envelope.history_latest_issue)
        ):
            self._reject("runtime_history_latest_issue_invalid", "history latest_issue is invalid")
        expected_snapshot_id = (
            f"history_snapshot.v1-{envelope.history_latest_issue or 'empty'}-"
            f"{envelope.history_snapshot_digest[:16]}"
        )
        if envelope.history_snapshot_id != expected_snapshot_id:
            self._reject("runtime_history_snapshot_id_mismatch", "Runtime Envelope snapshot id is not canonical")
        for name, value in (
            ("window_artifact_digest", envelope.window_artifact_digest),
            ("window_spec_digest", envelope.window_spec_digest),
            ("candidate_digest", envelope.candidate_digest),
            ("candidate_layout_digest", envelope.candidate_layout_digest),
            ("candidate_package_digest", envelope.candidate_package_digest),
            ("feature_component_manifest_digest", envelope.feature_component_manifest_digest),
            ("feature_layout_digest", envelope.feature_layout_digest),
            ("feature_runtime_digest", envelope.feature_runtime_digest),
            ("abi_package_digest", envelope.abi_package_digest),
        ):
            _require_digest(name, value)
        if envelope.state is RuntimeState.ARTIFACT_PRODUCED:
            if envelope.artifact_payload_digest is None:
                self._reject("runtime_artifact_digest_missing", "produced artifacts require a payload digest")
            _require_digest("artifact_payload_digest", envelope.artifact_payload_digest)
        elif envelope.artifact_payload_digest is not None:
            self._reject("runtime_artifact_digest_premature", "payload digest is only valid for produced artifacts")

        if runtime is not None:
            runtime.verify()
            history = runtime.history_snapshot
            window = runtime.window_artifact
            candidate = runtime.candidate_package
            feature = runtime.feature_tiles[0]
            expected = {
                "history_snapshot_id": history.snapshot_id,
                "history_snapshot_digest": history.history_digest,
                "history_latest_issue": history.latest_issue,
                "history_draw_count": history.draw_count,
                "window_artifact_digest": window.artifact_digest,
                "window_spec_digest": window.spec.spec_digest,
                "candidate_digest": candidate.header.candidate_digest,
                "candidate_layout_digest": candidate.header.layout_digest,
                "candidate_package_digest": candidate.package_digest,
                "feature_component_manifest_digest": feature.header.component_manifest_digest,
                "feature_layout_digest": feature.header.layout_digest,
                "feature_runtime_digest": runtime.runtime_digest,
                "feature_tile_count": len(runtime.feature_tiles),
                "abi_package_digest": runtime.runtime_digest,
            }
            actual = {name: getattr(envelope, name) for name in expected}
            if actual != expected:
                self._reject("runtime_envelope_binding_mismatch", "Runtime Envelope does not match runtime inputs")

    def verify_artifact_payload(
        self,
        envelope: RuntimeEnvelopeV1,
        *,
        payload_digest: str,
        runtime: FeatureABIRuntime | None = None,
        expected_backend: str | None = None,
    ) -> None:
        self.verify(envelope, runtime=runtime, expected_backend=expected_backend)
        if envelope.state is not RuntimeState.ARTIFACT_PRODUCED:
            self._reject(
                "runtime_artifact_state_mismatch",
                "artifact payload verification requires artifact_produced state",
            )
        _require_digest("artifact_payload_digest", payload_digest)
        if envelope.artifact_payload_digest != payload_digest:
            self._reject(
                "runtime_artifact_payload_mismatch",
                "artifact payload does not match Runtime Envelope",
            )

    @staticmethod
    def _reject(code: str, message: str, **context: Any) -> None:
        raise RuntimeEnvelopeViolation(code, message, **context)
