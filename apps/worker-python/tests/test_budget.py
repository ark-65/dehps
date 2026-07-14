from dehps.research_scheduler.budget import BudgetManager, SchedulerBudget
from dehps.research_scheduler.state import ResearchAction


def test_budget_manager_stops_unlimited_proposal_generation() -> None:
    manager = BudgetManager(SchedulerBudget(proposal_quota=1, proposal_used=1))

    decision = manager.authorize(ResearchAction.CREATE_PROPOSAL_REQUEST)

    assert decision.allowed is False
    assert decision.reason_code == "proposal_quota_exhausted"


def test_budget_manager_blocks_experiment_actions_when_daily_limit_is_spent() -> None:
    manager = BudgetManager(SchedulerBudget(daily_experiment_limit=1, daily_experiments_used=1))

    decision = manager.authorize(ResearchAction.CREATE_ENGINEERING_REQUEST)

    assert decision.allowed is False
    assert decision.reason_code == "daily_experiment_quota_exhausted"


def test_budget_manager_reports_stop_when_all_research_actions_are_exhausted() -> None:
    manager = BudgetManager(
        SchedulerBudget(
            daily_experiment_limit=1,
            daily_experiments_used=1,
            proposal_quota=1,
            proposal_used=1,
            forward_quota=1,
            forward_used=1,
        )
    )

    stop = manager.stop_if_exhausted()

    assert stop is not None
    assert stop.reason_code == "all_action_budgets_exhausted"
