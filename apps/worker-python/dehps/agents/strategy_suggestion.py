from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


STRATEGY_KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")
VERSION_RE = re.compile(r"^v[0-9]+$")


class StrategySuggestion(BaseModel):
    proposal_key: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    base_strategy_key: str = Field(pattern=STRATEGY_KEY_RE.pattern)
    proposed_version: str = Field(pattern=VERSION_RE.pattern)
    hypothesis: str = Field(min_length=40)
    rationale: str = Field(min_length=20)
    baseline: str = Field(min_length=3)
    expected_keep_rate_min: float = Field(ge=0.0, le=1.0)
    expected_keep_rate_max: float = Field(ge=0.0, le=1.0)
    expected_coverage_rate_min: float = Field(ge=0.0, le=1.0)
    failure_conditions: list[str] = Field(min_length=1)
    config_snapshot: dict[str, Any] = Field(default_factory=dict)
    implementation_notes: list[str] = Field(default_factory=list)
    advisory_only: bool = True

    @field_validator("failure_conditions")
    @classmethod
    def require_measurable_failures(cls, values: list[str]) -> list[str]:
        weak = [value for value in values if len(value.strip()) < 12]
        if weak:
            raise ValueError("failure conditions must be measurable and specific")
        return values

    @model_validator(mode="after")
    def validate_scientific_bounds(self) -> "StrategySuggestion":
        if self.expected_keep_rate_min > self.expected_keep_rate_max:
            raise ValueError("expected_keep_rate_min cannot exceed expected_keep_rate_max")
        if not self.advisory_only:
            raise ValueError("agent suggestions must remain advisory until backtested and accepted")
        return self

    @property
    def strategy_key(self) -> str:
        return f"{self.base_strategy_key}_{self.proposed_version}"

    def to_review_markdown(self) -> str:
        failures = "\n".join(f"- {condition}" for condition in self.failure_conditions)
        notes = "\n".join(f"- {note}" for note in self.implementation_notes) or "- None"
        return f"""# Strategy Suggestion

- Proposal: `{self.proposal_key}`
- Strategy key: `{self.strategy_key}`
- Base strategy: `{self.base_strategy_key}`
- Advisory only: {self.advisory_only}

## Hypothesis

{self.hypothesis}

## Rationale

{self.rationale}

## Measurement

- baseline: {self.baseline}
- expected_keep_rate_min: {self.expected_keep_rate_min}
- expected_keep_rate_max: {self.expected_keep_rate_max}
- expected_coverage_rate_min: {self.expected_coverage_rate_min}

## Failure Conditions

{failures}

## Config Snapshot

```json
{json.dumps(self.config_snapshot, ensure_ascii=False, indent=2)}
```

## Implementation Notes

{notes}

## Risk Note

This is a hypothesis proposal, not a prediction or betting recommendation.
"""
