from __future__ import annotations

from enum import Enum


class AgentRole(str, Enum):
    RESEARCH = "research"
    ENGINEERING = "engineering"
    REVIEWER = "reviewer"
    OPERATOR = "operator"
