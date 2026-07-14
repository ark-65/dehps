from __future__ import annotations

from dehps.research_runtime.models import (
    EvidenceSource,
    HistorySnapshot,
    ResearchRuntimeQueueItem,
    stable_hash,
)


RESEARCH_ACTIONS = frozenset(
    {
        "proposal_generation",
        "pattern_mining",
        "feature_synthesis",
        "strategy_synthesis",
        "isolated_experiment",
        "engineering_planning",
        "evidence_aggregation",
    }
)


class ContinuousResearchQueue:
    """Snapshot-scoped queue for research work; it never represents forward wait."""

    def create_item(
        self,
        *,
        action: str,
        snapshot: HistorySnapshot,
        priority_score: float = 0.5,
        payload: dict | None = None,
    ) -> ResearchRuntimeQueueItem:
        if action not in RESEARCH_ACTIONS:
            raise ValueError(f"invalid continuous research action: {action}")
        digest = stable_hash(
            {
                "action": action,
                "snapshot": snapshot.snapshot_key,
                "history_fingerprint": snapshot.history_fingerprint,
                "payload": payload or {},
            }
        )[:16]
        return ResearchRuntimeQueueItem(
            queue_key=f"research-runtime-{action}-{digest}",
            action=action,
            status="queued",
            snapshot_key=snapshot.snapshot_key,
            history_fingerprint=snapshot.history_fingerprint,
            evidence_source=EvidenceSource.RESEARCH,
            priority_score=priority_score,
            payload=dict(payload or {}),
        )
