from __future__ import annotations

from collections import OrderedDict
from hashlib import sha256

import orjson

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.walk_forward.contracts import (
    BlindTestFeatureView,
    SyntheticDataset,
    TrainFeatureView,
    TrainingDatasetView,
)
from dehps.research_os.information_theory.walk_forward.errors import (
    WalkForwardError,
)
from dehps.research_os.information_theory.walk_forward.feature_view import (
    FEATURE_MANIFEST_DIGEST,
    FEATURE_NAMES,
)

_TRAIN_FEATURE_VIEW_DOMAIN = "dehps.m4.walk-forward.train-feature-view.v1"
_BLIND_FEATURE_VIEW_DOMAIN = "dehps.m4.walk-forward.blind-feature-view.v1"
STATE_NUMBER_INTERACTION_NAMES = tuple(
    f"prior_state_x_red_{number:02d}" for number in range(1, 34)
)
STATE_VISIBLE_FEATURE_NAMES = (
    *FEATURE_NAMES,
    "prior_mechanism_state",
    *STATE_NUMBER_INTERACTION_NAMES,
)
STATE_VISIBLE_FEATURE_CONTRACT = {
    "feature_view_id": "FV2_SYNTHETIC_PRIOR_STATE_INSTRUMENT",
    "base_feature_manifest_digest": FEATURE_MANIFEST_DIGEST,
    "feature_names": list(STATE_VISIBLE_FEATURE_NAMES),
    "prior_mechanism_state": (
        "synthetic generator state available strictly before target issue"
    ),
    "state_number_interactions": (
        "one coordinate per red number, equal to prior state only for that "
        "number-event row; required for number-specific conditional marginals"
    ),
    "null_state_encoding": 0.5,
    "real_history_access": "forbidden",
    "scope": "P2.6.1 synthetic measurement validation only",
    "joint_or_pair_features": "forbidden_under_scheme_A",
}
STATE_VISIBLE_FEATURE_MANIFEST_DIGEST = canonical_digest(
    STATE_VISIBLE_FEATURE_CONTRACT,
    domain="dehps.m4-p2.state-visible-feature-view.v1",
)


def _exact_feature_digest(value: object, *, domain: str) -> str:
    """Serialize the internal ASCII primitive tree with canonical JSON bytes."""

    serialized = orjson.dumps(value, option=orjson.OPT_SORT_KEYS)
    return sha256(domain.encode("ascii") + b"\x00" + serialized).hexdigest()


class StrictPriorFeatureCache:
    """Incremental, target-gated equivalent of the accepted P2.3 feature builder.

    The cache never reads a target through ``SyntheticDataset``. New rows enter
    the cache only through a ``TrainingDatasetView`` whose access boundary has
    already advanced past that issue. Blind rows are derived from accumulated
    prior state before the current target is exposed.
    """

    def __init__(
        self,
        dataset: SyntheticDataset,
        *,
        include_prior_state: bool = False,
    ) -> None:
        self._dataset_digest = dataset.artifact_digest
        self._issue_count = dataset.issue_count
        self._revealed_through = 0
        self._counts = [0] * 33
        self._last_seen = [0] * 33
        self._previous_target = [0] * 33
        self._rows: dict[int, tuple[tuple[float, ...], ...]] = {}
        self._targets: dict[int, tuple[int, ...]] = {}
        self._training_views: OrderedDict[
            tuple[int, ...],
            TrainFeatureView,
        ] = OrderedDict()
        self._include_prior_state = include_prior_state
        self._feature_names = (
            STATE_VISIBLE_FEATURE_NAMES if include_prior_state else FEATURE_NAMES
        )
        self._feature_manifest_digest = (
            STATE_VISIBLE_FEATURE_MANIFEST_DIGEST
            if include_prior_state
            else FEATURE_MANIFEST_DIGEST
        )
        raw_states = dataset.raw_payload.get("prior_states")
        if include_prior_state:
            if (
                dataset.raw_payload.get("data_source") != "synthetic_only"
                or dataset.raw_payload.get("dataset_role")
                not in {
                    "P2_6_1_STATE_VISIBLE_SYNTHETIC_INSTRUMENT",
                    "P2_6_1_HYPERPARAMETER_DEVELOPMENT",
                }
                or dataset.raw_payload.get("prior_state_for_real_history")
                != "forbidden"
                or dataset.raw_payload.get(
                    "prior_state_available_strictly_before_target"
                )
                is not True
                or dataset.raw_payload.get("prior_state_access")
                != "synthetic_instrument_only_strictly_before_target"
                or not isinstance(raw_states, list)
                or len(raw_states) != dataset.issue_count
                or any(value not in (None, 0, 1) for value in raw_states)
            ):
                raise WalkForwardError(
                    "prior_state_contract_missing",
                    "state-visible P2.6.1 features require frozen prior states",
                )
            expected_state_digest = canonical_digest(
                raw_states,
                domain="dehps.m4-p2.evaluation-prior-states.v1",
            )
            if dataset.raw_payload.get("prior_state_digest") != expected_state_digest:
                raise WalkForwardError(
                    "prior_state_digest_mismatch",
                    "synthetic prior-state sequence changed",
                )
            self._prior_states = tuple(raw_states)
        else:
            self._prior_states = ()

    def _state_values(
        self,
        issue_index: int,
        red_number: int,
    ) -> tuple[float, ...]:
        if not self._include_prior_state:
            return ()
        value = self._prior_states[issue_index - 1]
        encoded = 0.5 if value is None else float(value)
        interactions = tuple(
            encoded if candidate == red_number else 0.0 for candidate in range(1, 34)
        )
        return (encoded, *interactions)

    @property
    def revealed_through_issue(self) -> int:
        return self._revealed_through

    def reveal_training_history(
        self,
        dataset: TrainingDatasetView,
        *,
        through_issue: int,
    ) -> None:
        if (
            dataset.artifact_digest != self._dataset_digest
            or through_issue > dataset.available_through_issue
            or through_issue >= self._issue_count
            or through_issue < self._revealed_through
        ):
            raise WalkForwardError(
                "target_access_boundary_violation",
                "feature cache may advance only through an authorized training view",
            )
        for issue_index in range(self._revealed_through + 1, through_issue + 1):
            history_count = issue_index - 1
            rows: list[tuple[float, ...]] = []
            for offset, red_number in enumerate(range(1, 34)):
                gap = (
                    history_count - self._last_seen[offset] + 1
                    if self._last_seen[offset] > 0
                    else history_count
                )
                rows.append(
                    (
                        float(self._previous_target[offset]),
                        (
                            self._counts[offset] / history_count
                            if history_count
                            else 0.0
                        ),
                        float(gap),
                        red_number / 33.0,
                        *self._state_values(issue_index, red_number),
                    )
                )
            target = dataset.issue(issue_index).target_vector
            self._rows[issue_index] = tuple(rows)
            self._targets[issue_index] = target
            for offset, value in enumerate(target):
                if value:
                    self._counts[offset] += 1
                    self._last_seen[offset] = issue_index
            self._previous_target = list(target)
            self._revealed_through = issue_index

    def build_train_feature_view(
        self,
        dataset: TrainingDatasetView,
        issue_ids: tuple[int, ...],
    ) -> TrainFeatureView:
        if (
            not issue_ids
            or tuple(sorted(set(issue_ids))) != issue_ids
            or dataset.artifact_digest != self._dataset_digest
            or max(issue_ids) > self._revealed_through
            or max(issue_ids) > dataset.available_through_issue
        ):
            raise WalkForwardError(
                "target_access_boundary_violation",
                "cached train rows must be ordered and already revealed",
            )
        cached = self._training_views.get(issue_ids)
        if cached is not None:
            self._training_views.move_to_end(issue_ids)
            return cached
        red_numbers = tuple(
            red_number for _issue_id in issue_ids for red_number in range(1, 34)
        )
        rows = tuple(row for issue_id in issue_ids for row in self._rows[issue_id])
        targets = tuple(
            value for issue_id in issue_ids for value in self._targets[issue_id]
        )
        availability = tuple((issue_id, issue_id - 1) for issue_id in issue_ids)
        identity = {
            "dataset_digest": dataset.artifact_digest,
            "issue_ids": issue_ids,
            "available_through_by_issue": availability,
            "construction_start_issue": 1,
            "construction_end_issue": issue_ids[-1] - 1,
            "feature_manifest_digest": self._feature_manifest_digest,
            "feature_names": self._feature_names,
            "values": rows,
            "target_access": "outer_training_targets_only",
        }
        view = TrainFeatureView(
            issue_ids=issue_ids,
            red_numbers=red_numbers,
            feature_names=self._feature_names,
            values=rows,
            targets=targets,
            available_through_by_issue=availability,
            construction_start_issue=1,
            construction_end_issue=issue_ids[-1] - 1,
            feature_manifest_digest=self._feature_manifest_digest,
            feature_view_digest=_exact_feature_digest(
                identity,
                domain=_TRAIN_FEATURE_VIEW_DOMAIN,
            ),
        )
        self._training_views[issue_ids] = view
        self._training_views.move_to_end(issue_ids)
        while len(self._training_views) > 32:
            self._training_views.popitem(last=False)
        return view

    def build_blind_test_feature_view(
        self,
        *,
        target_issue: int,
    ) -> BlindTestFeatureView:
        if (
            target_issue != self._revealed_through + 1
            or target_issue > self._issue_count
        ):
            raise WalkForwardError(
                "target_access_boundary_violation",
                "blind feature cache must be exactly one issue ahead",
            )
        history_count = target_issue - 1
        rows: list[tuple[float, ...]] = []
        for offset, red_number in enumerate(range(1, 34)):
            gap = (
                history_count - self._last_seen[offset] + 1
                if self._last_seen[offset] > 0
                else history_count
            )
            rows.append(
                (
                    float(self._previous_target[offset]),
                    (self._counts[offset] / history_count if history_count else 0.0),
                    float(gap),
                    red_number / 33.0,
                    *self._state_values(target_issue, red_number),
                )
            )
        values = tuple(rows)
        red_numbers = tuple(range(1, 34))
        identity = {
            "dataset_digest": self._dataset_digest,
            "target_issue": target_issue,
            "available_through_issue": history_count,
            "construction_start_issue": 1,
            "construction_end_issue": history_count,
            "feature_manifest_digest": self._feature_manifest_digest,
            "feature_names": self._feature_names,
            "red_numbers": red_numbers,
            "values": values,
            "target_access": "forbidden",
        }
        return BlindTestFeatureView(
            target_issue=target_issue,
            red_numbers=red_numbers,
            feature_names=self._feature_names,
            values=values,
            available_through_issue=history_count,
            construction_start_issue=1,
            construction_end_issue=history_count,
            feature_manifest_digest=self._feature_manifest_digest,
            feature_view_digest=_exact_feature_digest(
                identity,
                domain=_BLIND_FEATURE_VIEW_DOMAIN,
            ),
        )
