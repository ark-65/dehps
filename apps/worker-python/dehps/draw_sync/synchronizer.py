from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from dehps.crawler.ssq_sync import sync_ssq


class DrawSynchronizer(Protocol):
    def sync(
        self,
        *,
        source: str,
        history: bool,
        from_issue: str | None,
        to_issue: str | None,
        csv_file: str | None,
        dry_run: bool,
        run_key: str,
    ) -> dict:
        ...


@dataclass(frozen=True)
class SsqDrawSynchronizer:
    def sync(
        self,
        *,
        source: str,
        history: bool,
        from_issue: str | None,
        to_issue: str | None,
        csv_file: str | None,
        dry_run: bool,
        run_key: str,
    ) -> dict:
        return sync_ssq(
            source,
            history=history,
            from_issue=from_issue,
            to_issue=to_issue,
            csv_file=csv_file,
            dry_run=dry_run,
            run_key=run_key,
        )
