from dehps.research_scheduler.priority import ResearchPriorityEngine
from dehps.research_scheduler.state import QueueStatus, ResearchAction
from test_priority import state


def test_next_action_for_accepted_hypothesis_is_followup_planning() -> None:
    action = ResearchPriorityEngine().next_action(
        state(
            active_hypotheses=(
                {
                    "hypothesis_key": "hypothesis-accepted",
                    "family_key": "family-1",
                    "status": "accepted_for_followup",
                },
            )
        )
    )

    assert action.action == ResearchAction.CREATE_PLANNING_REQUEST
    assert action.queue_status == QueueStatus.PLANNING
    assert action.target_hypothesis_key == "hypothesis-accepted"


def test_next_action_for_preregistered_hypothesis_with_experiment_needs_engineering() -> None:
    base = state(
        active_hypotheses=(
            {
                "hypothesis_key": "hypothesis-preregistered",
                "family_key": "family-1",
                "status": "preregistered",
            },
        )
    )
    patched = type(base)(
        **{
            **base.__dict__,
            "recent_experiments": (
                {
                    "hypothesis_key": "hypothesis-preregistered",
                    "experiment_key": "experiment-1",
                    "status": "planned",
                },
            ),
        }
    )

    action = ResearchPriorityEngine().next_action(patched)

    assert action.action == ResearchAction.CREATE_ENGINEERING_REQUEST
    assert action.queue_status == QueueStatus.ENGINEERING
