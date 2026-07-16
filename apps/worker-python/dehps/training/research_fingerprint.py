from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Literal, Mapping

from dehps.ranking_contract import normalize_ranking_contract


RESEARCH_EXECUTION_MODE = "research"
TaskExecutionMode = Literal["deterministic", "stochastic"]
SeedAggregation = Literal["mean_variance", "distribution"]
SeedSelectionPolicy = Literal["no_best_seed"]

RANDOM_CONFIG_FIELDS = frozenset(
    {
        "seed",
        "seeds",
        "random_seed",
        "random_seeds",
        "seed_policy",
        "random_algorithm_version",
        "sampling_method",
        "random_split",
        "bootstrap_iterations",
        "monte_carlo_trials",
        "permutation_count",
    }
)


def _stable_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _random_config_paths(value: Any, *, prefix: str = "") -> tuple[str, ...]:
    paths: list[str] = []
    if isinstance(value, Mapping):
        for raw_key, child in value.items():
            key = str(raw_key)
            path = f"{prefix}.{key}" if prefix else key
            if key.lower() in RANDOM_CONFIG_FIELDS:
                paths.append(path)
            paths.extend(_random_config_paths(child, prefix=path))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            path = f"{prefix}[{index}]"
            paths.extend(_random_config_paths(child, prefix=path))
    return tuple(paths)


@dataclass(frozen=True)
class SeedPolicy:
    seeds: tuple[int, ...]
    aggregation: SeedAggregation = "mean_variance"
    selection_policy: SeedSelectionPolicy = "no_best_seed"

    def __post_init__(self) -> None:
        normalized = tuple(sorted({int(seed) for seed in self.seeds}))
        if not normalized:
            raise ValueError("stochastic task seed policy requires at least one seed")
        if self.aggregation not in ("mean_variance", "distribution"):
            raise ValueError(f"unsupported seed aggregation: {self.aggregation}")
        if self.selection_policy != "no_best_seed":
            raise ValueError("stochastic task seed policy forbids best-seed selection")
        object.__setattr__(self, "seeds", normalized)

    def as_dict(self) -> dict[str, Any]:
        return {
            "seeds": list(self.seeds),
            "aggregation": self.aggregation,
            "selection_policy": self.selection_policy,
        }


@dataclass(frozen=True)
class ResearchTaskSpec:
    task_type: str
    execution_mode: TaskExecutionMode
    config: Mapping[str, Any]
    evaluation_contract: str
    ranking_contract: str | None = None
    seed_policy: SeedPolicy | None = None

    def __post_init__(self) -> None:
        if not self.task_type.strip():
            raise ValueError("research task type is required")
        if not self.evaluation_contract.strip():
            raise ValueError("research task evaluation contract is required")
        if self.ranking_contract is not None:
            object.__setattr__(
                self,
                "ranking_contract",
                normalize_ranking_contract(self.ranking_contract),
            )
        if self.execution_mode == "deterministic":
            if self.seed_policy is not None:
                raise ValueError("deterministic task cannot declare a seed policy")
            random_paths = _random_config_paths(self.config)
            if random_paths:
                raise ValueError(
                    "deterministic task config contains random fields: "
                    + ",".join(random_paths)
                )
        elif self.execution_mode == "stochastic":
            if self.seed_policy is None:
                raise ValueError("stochastic task requires an explicit seed policy")
        else:
            raise ValueError(f"unsupported research task execution mode: {self.execution_mode}")

    @property
    def config_hash(self) -> str:
        return _stable_hash(dict(self.config))


@dataclass(frozen=True)
class ResearchTaskFingerprint:
    history_max_issue: str
    history_fingerprint: str
    training_mode: str
    model_version: str
    feature_version: str
    candidate_algorithm_version: str
    code_commit: str
    spec: ResearchTaskSpec

    @property
    def payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "history_max_issue": self.history_max_issue,
            "history_fingerprint": self.history_fingerprint,
            "training_mode": self.training_mode,
            "task_type": self.spec.task_type,
            "execution_mode": self.spec.execution_mode,
            "model_version": self.model_version,
            "feature_version": self.feature_version,
            "candidate_algorithm_version": self.candidate_algorithm_version,
            "config_hash": self.spec.config_hash,
            "evaluation_contract": self.spec.evaluation_contract,
            "code_commit": self.code_commit,
        }
        if self.spec.seed_policy is not None:
            payload["seed_policy"] = self.spec.seed_policy.as_dict()
        if self.spec.ranking_contract is not None:
            payload["ranking_contract"] = self.spec.ranking_contract
        return payload

    @property
    def experiment_fingerprint(self) -> str:
        return _stable_hash(self.payload)

    @property
    def value(self) -> str:
        return self.experiment_fingerprint

    def run_fingerprint(self, seed: int | None = None) -> str:
        if self.spec.execution_mode == "deterministic":
            if seed is not None:
                raise ValueError("deterministic task does not accept a seed")
            return self.experiment_fingerprint
        policy = self.spec.seed_policy
        if policy is None:
            raise ValueError("stochastic task has no seed policy")
        if seed is None:
            raise ValueError("stochastic task replicate requires a seed")
        normalized_seed = int(seed)
        if normalized_seed not in policy.seeds:
            raise ValueError("replicate seed is outside the experiment seed policy")
        return _stable_hash(
            {
                "experiment_fingerprint": self.experiment_fingerprint,
                "seed": normalized_seed,
            }
        )

    def as_dict(self) -> dict[str, Any]:
        payload = {
            **self.payload,
            "experiment_fingerprint": self.experiment_fingerprint,
            "task_config": dict(self.spec.config),
        }
        if self.spec.seed_policy is not None:
            payload["replicates"] = [
                {
                    "seed": seed,
                    "run_fingerprint": self.run_fingerprint(seed),
                }
                for seed in self.spec.seed_policy.seeds
            ]
        return payload


@dataclass(frozen=True)
class ResearchTrainingFingerprint:
    """Suite identity composed from task-level experiment identities.

    The legacy name is retained for callers, but seed is intentionally absent.
    """

    training_mode: str
    suite_version: str
    tasks: tuple[ResearchTaskFingerprint, ...]

    def __post_init__(self) -> None:
        if not self.tasks:
            raise ValueError("research suite requires at least one task")
        task_types = tuple(task.spec.task_type for task in self.tasks)
        if len(set(task_types)) != len(task_types):
            raise ValueError("research suite task types must be unique")

    @property
    def payload(self) -> dict[str, Any]:
        return {
            "training_mode": self.training_mode,
            "suite_version": self.suite_version,
            "task_experiment_fingerprints": [
                {
                    "task_type": task.spec.task_type,
                    "experiment_fingerprint": task.experiment_fingerprint,
                }
                for task in self.tasks
            ],
        }

    @property
    def config_hash(self) -> str:
        return _stable_hash(
            {
                task.spec.task_type: task.spec.config_hash
                for task in self.tasks
            }
        )

    @property
    def value(self) -> str:
        return _stable_hash(self.payload)

    def as_dict(self) -> dict[str, Any]:
        return {
            **self.payload,
            "training_fingerprint": self.value,
            "config_hash": self.config_hash,
            "task_contracts": [task.as_dict() for task in self.tasks],
        }


def completed_manifest_matches(
    manifest: Any,
    *,
    lane_key: str,
    training_fingerprint: str,
) -> bool:
    return bool(
        isinstance(manifest, dict)
        and manifest.get("status") == "completed"
        and manifest.get("lane_key") == lane_key
        and manifest.get("training_fingerprint") == training_fingerprint
    )
