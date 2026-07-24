from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from dehps.contracts import canonical_digest
from dehps.training.research_fingerprint import SeedPolicy


RUN_SCHEMA_VERSION = "dehps-m4-information-theory-synthetic-run.v1"
SCENARIO_SCHEMA_VERSION = "dehps-m4-information-theory-synthetic-scenario.v1"
TRUTH_SCHEMA_VERSION = "dehps-m4-information-theory-synthetic-truth.v1"
DATASET_SCHEMA_VERSION = "dehps-m4-information-theory-synthetic-dataset.v1"


def _digest(payload: Mapping[str, Any], *, domain: str) -> str:
    value = dict(payload)
    value.pop("artifact_digest", None)
    return canonical_digest(value, domain=domain)


@dataclass(frozen=True)
class SyntheticScale:
    scale_id: str
    sequence_length: int
    minimum_training_length: int
    outer_evaluation_length: int
    derivation: str

    def __post_init__(self) -> None:
        if self.sequence_length < 1 or self.minimum_training_length < 1:
            raise ValueError("synthetic scale lengths must be positive")
        if self.sequence_length - self.minimum_training_length != self.outer_evaluation_length:
            raise ValueError("outer evaluation length must equal sequence minus training length")

    def to_dict(self) -> dict[str, Any]:
        return {
            "scale_id": self.scale_id,
            "sequence_length": self.sequence_length,
            "minimum_training_length": self.minimum_training_length,
            "outer_evaluation_length": self.outer_evaluation_length,
            "derivation": self.derivation,
        }


@dataclass(frozen=True)
class SyntheticScenario:
    scenario_id: str
    mechanism: str
    signal_strength: str
    target_bits_per_issue: float
    implemented: bool
    data_source: str = "synthetic_only"

    def __post_init__(self) -> None:
        if self.data_source != "synthetic_only":
            raise ValueError("synthetic scenario cannot reference real data")
        if self.scenario_id == "NULL_UNIFORM" and self.mechanism != "uniform_choose_6_without_replacement_from_33":
            raise ValueError("NULL_UNIFORM must preserve the exact legal mechanism")
        expected_bits = {
            "ZERO": 0.0,
            "WEAK": 0.001,
            "MEDIUM_PRACTICAL": 0.01,
            "STRONG": 0.05,
        }
        if self.target_bits_per_issue != expected_bits.get(self.signal_strength):
            raise ValueError("signal strength must retain its preregistered target bits")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCENARIO_SCHEMA_VERSION,
            "scenario_id": self.scenario_id,
            "mechanism": self.mechanism,
            "signal_strength": self.signal_strength,
            "target_bits_per_issue": self.target_bits_per_issue,
            "implemented": self.implemented,
            "data_source": self.data_source,
        }


@dataclass(frozen=True)
class SyntheticTruth:
    scenario_id: str
    legal_combination_count: int
    number_marginal: tuple[int, int]
    pair_marginal: tuple[int, int]
    full_combination_probability: tuple[int, int]

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "schema_version": TRUTH_SCHEMA_VERSION,
            "scenario_id": self.scenario_id,
            "legal_combination_count": self.legal_combination_count,
            "number_marginal": {
                "numerator": self.number_marginal[0],
                "denominator": self.number_marginal[1],
                "formula": "6/33",
            },
            "pair_marginal": {
                "numerator": self.pair_marginal[0],
                "denominator": self.pair_marginal[1],
                "formula": "C(31,4)/C(33,6)",
            },
            "full_combination_probability": {
                "numerator": self.full_combination_probability[0],
                "denominator": self.full_combination_probability[1],
                "formula": "1/C(33,6)",
            },
        }
        payload["truth_digest"] = canonical_digest(
            payload, domain="dehps.m4.synthetic.truth.v1"
        )
        return payload


@dataclass(frozen=True)
class SyntheticIssue:
    issue_index: int
    red_mask: int
    sorted_red_numbers: tuple[int, ...]
    target_vector: tuple[int, ...]

    def __post_init__(self) -> None:
        if self.issue_index < 1:
            raise ValueError("issue_index is one-based")
        if (
            len(self.sorted_red_numbers) != 6
            or tuple(sorted(set(self.sorted_red_numbers))) != self.sorted_red_numbers
            or any(number < 1 or number > 33 for number in self.sorted_red_numbers)
        ):
            raise ValueError("issue must contain six unique sorted numbers in [1,33]")
        if len(self.target_vector) != 33 or sum(self.target_vector) != 6:
            raise ValueError("target vector must contain 33 entries and six positives")
        expected_target = tuple(
            1 if number in self.sorted_red_numbers else 0 for number in range(1, 34)
        )
        expected_mask = sum(1 << (number - 1) for number in self.sorted_red_numbers)
        if self.target_vector != expected_target or self.red_mask != expected_mask:
            raise ValueError("red mask and target vector must encode the same numbers")

    def to_dict(self) -> dict[str, Any]:
        return {
            "issue_index": self.issue_index,
            "red_mask": self.red_mask,
            "sorted_red_numbers": list(self.sorted_red_numbers),
            "target_vector": list(self.target_vector),
        }


@dataclass(frozen=True)
class SyntheticDatasetArtifact:
    scenario: SyntheticScenario
    scale: SyntheticScale
    truth: SyntheticTruth
    seed_policy: SeedPolicy
    replicate_seed: int
    issues: tuple[SyntheticIssue, ...]
    preregistration_digest: str
    decision_policy_digest: str
    config_digest: str

    def __post_init__(self) -> None:
        if self.replicate_seed not in self.seed_policy.seeds:
            raise ValueError("replicate seed is outside the normalized SeedPolicy")
        if len(self.issues) != self.scale.sequence_length:
            raise ValueError("dataset issue count does not match the selected scale")

    def to_dict(self) -> dict[str, Any]:
        issue_payloads = [issue.to_dict() for issue in self.issues]
        draw_digest = canonical_digest(
            [
                {
                    "issue_index": item["issue_index"],
                    "sorted_red_numbers": item["sorted_red_numbers"],
                }
                for item in issue_payloads
            ],
            domain="dehps.m4.synthetic.draws.v1",
        )
        target_digest = canonical_digest(
            [item["target_vector"] for item in issue_payloads],
            domain="dehps.m4.synthetic.targets.v1",
        )
        seed_policy_payload = self.seed_policy.as_dict()
        payload: dict[str, Any] = {
            "schema_version": DATASET_SCHEMA_VERSION,
            "artifact_type": "synthetic_dataset",
            "data_source": "synthetic_only",
            "real_dataset_reference": None,
            "scenario": self.scenario.to_dict(),
            "scale": self.scale.to_dict(),
            "truth": self.truth.to_dict(),
            "seed_policy": seed_policy_payload,
            "seed_policy_digest": canonical_digest(
                seed_policy_payload, domain="dehps.m4.synthetic.seed-policy.v1"
            ),
            "replicate_seed": self.replicate_seed,
            "issue_count": len(issue_payloads),
            "draw_digest": draw_digest,
            "target_digest": target_digest,
            "preregistration_digest": self.preregistration_digest,
            "decision_policy_digest": self.decision_policy_digest,
            "config_digest": self.config_digest,
            "issues": issue_payloads,
        }
        payload["artifact_digest"] = _digest(
            payload, domain="dehps.m4.synthetic.dataset.v1"
        )
        return payload


@dataclass(frozen=True)
class SyntheticRunManifest:
    payload: Mapping[str, Any]
    artifact_digest: str
    seed_policy: SeedPolicy
    scenarios: tuple[SyntheticScenario, ...]
    scales: tuple[SyntheticScale, ...]

    def scenario(self, scenario_id: str) -> SyntheticScenario:
        try:
            return next(item for item in self.scenarios if item.scenario_id == scenario_id)
        except StopIteration as exc:
            raise ValueError(f"unknown synthetic scenario: {scenario_id}") from exc

    def scale(self, scale_id: str) -> SyntheticScale:
        try:
            return next(item for item in self.scales if item.scale_id == scale_id)
        except StopIteration as exc:
            raise ValueError(f"unknown synthetic scale: {scale_id}") from exc
