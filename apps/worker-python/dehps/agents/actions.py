from __future__ import annotations

from enum import Enum


class AgentAction(str, Enum):
    READ_HYPOTHESIS = "read_hypothesis"
    CREATE_HYPOTHESIS_PROPOSAL = "create_hypothesis_proposal"
    CREATE_EXPERIMENT_PLAN = "create_experiment_plan"
    SUBMIT_PREREGISTRATION = "submit_preregistration"
    ADD_EVIDENCE_PROPOSAL = "add_evidence_proposal"
    SUBMIT_HYPOTHESIS_DECISION = "submit_hypothesis_decision"
    SCHEDULE_RESEARCH = "schedule_research"
    CREATE_ENGINEERING_REQUEST = "create_engineering_request"
    MODIFY_CODE = "modify_code"
    RUN_TESTS = "run_tests"
    RUN_ISOLATED_EXPERIMENT = "run_isolated_experiment"
    CREATE_PULL_REQUEST = "create_pull_request"
    REVIEW_REQUEST = "review_request"
    APPROVE_REQUEST = "approve_request"
    REJECT_REQUEST = "reject_request"
    CANCEL_REQUEST = "cancel_request"
    RESTART_PRODUCTION_SUPERVISOR = "restart_production_supervisor"
    APPLY_DATABASE_MIGRATION = "apply_database_migration"
    PUBLISH_RELEASE = "publish_release"
    PROMOTE_PRODUCTION_STRATEGY = "promote_production_strategy"
