from __future__ import annotations

import re
from typing import Iterable

from dehps.research_autonomy.context import HypothesisSummary, ResearchContext
from dehps.research_autonomy.proposal_models import HypothesisProposal, NoveltyReport


PSEUDO_INNOVATION_CHANGES = {
    "seed": "seed_only_change",
    "random_seed": "seed_only_change",
    "epochs": "epoch_only_change",
    "epoch": "epoch_only_change",
    "hidden_layers": "hidden_layer_only_change",
    "depth": "hidden_layer_only_change",
    "nearby_weights": "nearby_weight_only_change",
    "weights": "nearby_weight_only_change",
    "search_rounds": "same_history_search_round_expansion",
    "same_history_search_rounds": "same_history_search_round_expansion",
    "rename": "rename_only_change",
    "name": "rename_only_change",
}


class HypothesisNoveltyDetector:
    def compare(
        self,
        proposal: HypothesisProposal,
        context: ResearchContext,
    ) -> NoveltyReport:
        hypotheses = (*context.active_hypotheses, *context.rejected_hypotheses)
        closest = self._closest(proposal, hypotheses)
        mechanism_distance = self._mechanism_distance(
            proposal.mechanism,
            None if closest is None else closest.mechanism,
        )
        feature_distance = self._set_distance(
            self._features(proposal),
            () if closest is None else closest.feature_keys,
        )
        validation_distance = self._validation_distance(
            proposal,
            None if closest is None else closest.validation_protocol,
        )
        reasons = list(self._parameter_only_reasons(proposal))
        rejected_reuse = False
        for rejected in context.rejected_hypotheses:
            same_mechanism = self._mechanism_distance(proposal.mechanism, rejected.mechanism) == 0.0
            same_features = self._set_distance(self._features(proposal), rejected.feature_keys) == 0.0
            if same_mechanism:
                rejected_reuse = True
                reasons.append(f"rejected_mechanism_rewrapped:{rejected.hypothesis_key}")
            elif same_features and rejected.feature_keys:
                rejected_reuse = True
                reasons.append(f"rejected_features_rewrapped:{rejected.hypothesis_key}")
        for family in context.rejected_families:
            if self._mechanism_distance(proposal.mechanism, family.mechanism) == 0.0:
                rejected_reuse = True
                reasons.append(f"rejected_family_reuse:{family.family_key}")
        if closest is not None:
            same_inputs = set(proposal.input_boundary.get("allowed_fields", ())) == set(
                closest.input_fields
            )
            same_target = proposal.metric_contract.get("primary") in {
                "time_isolated_exact_target_rank",
                "exact_target_rank",
            }
            if (
                same_inputs
                and same_target
                and mechanism_distance == 0.0
                and feature_distance == 0.0
                and validation_distance == 0.0
            ):
                reasons.append(f"same_input_target_validation:{closest.hypothesis_key}")
        unique_reasons = tuple(sorted(set(reasons)))
        return NoveltyReport(
            is_novel=not unique_reasons,
            mechanism_distance=round(mechanism_distance, 6),
            feature_distance=round(feature_distance, 6),
            validation_distance=round(validation_distance, 6),
            closest_hypothesis_key=None if closest is None else closest.hypothesis_key,
            closest_family_key=None if closest is None else closest.family_key,
            duplicate_reasons=unique_reasons,
            rejected_reuse_detected=rejected_reuse,
        )

    def _closest(
        self,
        proposal: HypothesisProposal,
        hypotheses: Iterable[HypothesisSummary],
    ) -> HypothesisSummary | None:
        scored = []
        for hypothesis in hypotheses:
            score = (
                self._mechanism_distance(proposal.mechanism, hypothesis.mechanism)
                + self._set_distance(self._features(proposal), hypothesis.feature_keys)
                + self._validation_distance(proposal, hypothesis.validation_protocol)
            )
            scored.append((score, hypothesis.hypothesis_key, hypothesis))
        return min(scored, default=(0.0, "", None))[2]

    @staticmethod
    def _features(proposal: HypothesisProposal) -> tuple[str, ...]:
        return tuple(sorted(str(value) for value in proposal.feature_contract.get("feature_keys", ())))

    @staticmethod
    def _parameter_only_reasons(proposal: HypothesisProposal) -> tuple[str, ...]:
        change = str(proposal.model_contract.get("only_change") or "").strip().lower()
        normalized = change.replace("-", "_").replace(" ", "_")
        reason = PSEUDO_INNOVATION_CHANGES.get(normalized)
        if reason:
            return (reason,)
        basis = {_tokens(value) for value in proposal.novelty_basis}
        if basis == {"rename only"}:
            return ("rename_only_change",)
        return ()

    @staticmethod
    def _mechanism_distance(left: str, right: str | None) -> float:
        if right is None:
            return 1.0
        left_tokens = set(_tokens(left).split())
        right_tokens = set(_tokens(right).split())
        aliases = {
            "feature interaction nonlinearity": {"generic structural mlp", "neural kdj interaction"},
            "multi scale frequency residual": {"univariate temporal residual"},
        }
        left_name = _tokens(left)
        right_name = _tokens(right)
        if left_name == right_name or right_name in aliases.get(left_name, set()):
            return 0.0
        return HypothesisNoveltyDetector._set_distance(left_tokens, right_tokens)

    @staticmethod
    def _set_distance(left: Iterable[str], right: Iterable[str]) -> float:
        left_set = {str(value) for value in left}
        right_set = {str(value) for value in right}
        if not left_set and not right_set:
            return 0.0
        union = left_set | right_set
        return 1.0 - len(left_set & right_set) / len(union)

    @staticmethod
    def _validation_distance(proposal: HypothesisProposal, protocol: str | None) -> float:
        if protocol is None:
            return 1.0
        proposal_kind = _tokens(str(proposal.validation_protocol.get("kind") or ""))
        existing = _tokens(protocol)
        if proposal_kind == existing:
            return 0.0
        if "walk forward" in proposal_kind and "walk forward" in existing:
            return 0.0
        return 1.0


def _tokens(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.lower().replace("_", " ")))
