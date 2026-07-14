from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from typing import Iterable

import numpy as np

from dehps.research.models import HypothesisEvidence
from dehps.research.status import EvidenceDirection, HypothesisStatus, RejectionScope
from dehps.research_evidence.models import (
    DecisionDraft,
    EvidenceAggregation,
    EvidenceStrength,
    stable_hash,
)


PROHIBITED_RETRY_ONLY_CHANGES = (
    "seed",
    "epochs",
    "depth",
    "nearby_weights",
    "same_history_search_rounds",
    "rename",
)


class SequentialEvidenceAggregator:
    def aggregate(self, hypothesis_key: str, evidence: Iterable[HypothesisEvidence]) -> EvidenceAggregation:
        items = list(evidence)
        directions = Counter(item.direction for item in items)
        effect_sizes = [
            float(item.metrics.get("effect_size") or 0.0)
            for item in items
            if isinstance(item.metrics, dict)
        ]
        stages = [
            str(item.metadata.get("stage") or item.metrics.get("stage") or "")
            for item in items
        ]
        forward_coverage = sum(1 for stage in stages if "forward" in stage or "future" in stage)
        invalidating = directions[EvidenceDirection.INVALIDATING]
        supporting = directions[EvidenceDirection.SUPPORTING]
        contradicting = directions[EvidenceDirection.CONTRADICTING]
        neutral = directions[EvidenceDirection.NEUTRAL]
        total = max(1, len(items))
        if invalidating:
            overall = EvidenceDirection.INVALIDATING
            strength = EvidenceStrength.INVALID
        elif supporting > contradicting and supporting >= neutral:
            overall = EvidenceDirection.SUPPORTING
            strength = EvidenceStrength.MODERATE if forward_coverage else EvidenceStrength.INSUFFICIENT
        elif contradicting > supporting and contradicting >= neutral:
            overall = EvidenceDirection.CONTRADICTING
            strength = EvidenceStrength.MODERATE if forward_coverage else EvidenceStrength.INSUFFICIENT
        else:
            overall = EvidenceDirection.NEUTRAL
            strength = EvidenceStrength.INSUFFICIENT if not forward_coverage else EvidenceStrength.WEAK
        majority = max(supporting, contradicting, neutral, invalidating)
        heterogeneity = float(np.std(effect_sizes)) if effect_sizes else 0.0
        family_rejection = (
            len(items) >= 2
            and forward_coverage > 0
            and (contradicting + neutral) / total >= 0.75
            and abs(float(np.mean(effect_sizes))) < 0.10
        )
        parameter_rejection = (
            len(items) >= 2
            and forward_coverage > 0
            and contradicting / total >= 0.60
        )
        return EvidenceAggregation(
            hypothesis_key=hypothesis_key,
            evidence_count=len(items),
            supporting_count=supporting,
            contradicting_count=contradicting,
            neutral_count=neutral,
            invalidating_count=invalidating,
            overall_direction=overall,
            consistency=float(majority / total),
            heterogeneity=heterogeneity,
            evidence_strength=strength,
            forward_coverage=forward_coverage,
            windows={
                "historical": sum(1 for stage in stages if "historical" in stage or "search" in stage),
                "frozen": sum(1 for stage in stages if "frozen" in stage),
                "future": forward_coverage,
            },
            family_rejection_suggested=family_rejection,
            parameter_rejection_suggested=parameter_rejection,
            evidence_ids=tuple(item.id for item in items),
            evidence_keys=tuple(str(item.metadata.get("evidence_key") or item.content_hash or item.id) for item in items),
            reason={
                "direction_counts": {key.value: directions[key] for key in EvidenceDirection},
                "forward_coverage": forward_coverage,
                "heterogeneity": heterogeneity,
                "evidence_strength": strength.value,
            },
        )


class DecisionBuilder:
    def build(self, aggregation: EvidenceAggregation) -> DecisionDraft:
        if aggregation.invalidating_count:
            proposed = HypothesisStatus.INVALIDATED
            summary = "Artifact validation invalidated the experiment evidence"
            code = "autonomous_evidence_invalidated"
            scope = RejectionScope.NONE
            family_action = "none"
            reason = {**aggregation.reason, "decision_basis": "invalidating_evidence"}
            reopen_condition = None
            rejection_reason = None
        elif aggregation.forward_coverage <= 0:
            proposed = HypothesisStatus.INCONCLUSIVE
            summary = "Evidence is insufficient because no forward/future window is available"
            code = "autonomous_evidence_inconclusive"
            scope = RejectionScope.NONE
            family_action = "none"
            reason = {**aggregation.reason, "decision_basis": "no_forward_coverage"}
            reopen_condition = None
            rejection_reason = None
        elif aggregation.family_rejection_suggested:
            proposed = HypothesisStatus.REJECTED
            summary = "Evidence consistently failed across experiments; mechanism family rejection is suggested"
            code = "autonomous_mechanism_family_rejection"
            scope = RejectionScope.MECHANISM_FAMILY
            family_action = "mechanism_family_rejected"
            reason = self._rejection_reason(aggregation, mechanism=True)
            reopen_condition = "Only reopen if a new mechanism changes the preregistered causal signature and passes a fresh plan review."
            rejection_reason = summary
        elif aggregation.parameter_rejection_suggested or aggregation.overall_direction == EvidenceDirection.CONTRADICTING:
            proposed = HypothesisStatus.REJECTED
            summary = "Evidence contradicts the preregistered parameter region"
            code = "autonomous_parameter_region_rejection"
            scope = RejectionScope.PARAMETER_REGION
            family_action = "parameter_region_rejected"
            reason = self._rejection_reason(aggregation, mechanism=False)
            reopen_condition = "Only reopen after a new preregistered parameter region and fresh isolated execution."
            rejection_reason = summary
        elif aggregation.overall_direction == EvidenceDirection.SUPPORTING and aggregation.evidence_strength in {
            EvidenceStrength.MODERATE,
            EvidenceStrength.STRONG,
        }:
            proposed = HypothesisStatus.ACCEPTED_FOR_FOLLOWUP
            summary = "Evidence supports follow-up under the preregistered criteria"
            code = "autonomous_evidence_accept_followup"
            scope = RejectionScope.NONE
            family_action = "none"
            reason = {**aggregation.reason, "decision_basis": "supporting_with_forward_coverage"}
            reopen_condition = None
            rejection_reason = None
        else:
            proposed = HypothesisStatus.INCONCLUSIVE
            summary = "Evidence is mixed or underpowered"
            code = "autonomous_evidence_inconclusive"
            scope = RejectionScope.NONE
            family_action = "none"
            reason = {**aggregation.reason, "decision_basis": "mixed_or_underpowered"}
            reopen_condition = None
            rejection_reason = None

        payload = {
            "hypothesis_key": aggregation.hypothesis_key,
            "proposed_status": proposed.value,
            "evidence_ids": aggregation.evidence_ids,
            "aggregation": asdict(aggregation),
            "decision_code": code,
            "summary": summary,
        }
        return DecisionDraft(
            decision_key=stable_hash(payload),
            hypothesis_key=aggregation.hypothesis_key,
            proposed_status=proposed,
            evidence_ids=aggregation.evidence_ids,
            evidence_keys=aggregation.evidence_keys,
            reason=reason,
            summary=summary,
            decision_code=code,
            rejection_scope=scope,
            rejection_reason=rejection_reason,
            reopen_condition=reopen_condition,
            family_action=family_action,
        )

    @staticmethod
    def _rejection_reason(aggregation: EvidenceAggregation, *, mechanism: bool) -> dict[str, object]:
        base = {
            "failed_metrics": ["paired_target_hit_lift", "effect_size", "adjusted_p_value"],
            "data_boundary": "isolated audited experiment artifacts only",
            "prohibited_parameter_only_changes": list(PROHIBITED_RETRY_ONLY_CHANGES),
            "aggregation": asdict(aggregation),
        }
        if mechanism:
            base["mechanism_signature"] = "ranking_model_disagreement"
        else:
            base["parameter_region"] = "preregistered ranking disagreement strata and baselines"
        return base
