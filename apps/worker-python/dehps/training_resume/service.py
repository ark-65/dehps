from __future__ import annotations

from typing import Any

from dehps.training_resume.controller import TrainingResumeController
from dehps.training_resume.repository import TrainingResumeRepository


class TrainingResumeService:
    def __init__(
        self,
        *,
        controller: TrainingResumeController | None = None,
        repository: TrainingResumeRepository | None = None,
    ) -> None:
        self.controller = controller or TrainingResumeController()
        self.repository = repository or TrainingResumeRepository()

    def check(self, *, event_key: str | None = None) -> dict[str, Any]:
        return self.controller.check(event_key=event_key)

    def execute(self, *, event_key: str | None = None) -> dict[str, Any]:
        return self.controller.execute(event_key=event_key)

    def history(self, *, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        self.repository.ensure_schema()
        return {"items": self.repository.history(limit=limit, offset=offset), "limit": limit, "offset": offset}

    def status(self) -> dict[str, Any]:
        self.repository.ensure_schema()
        return self.repository.status()
