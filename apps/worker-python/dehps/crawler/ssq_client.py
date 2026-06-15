from __future__ import annotations

import csv
import json
import logging
import time
from abc import ABC, abstractmethod
from datetime import date
from pathlib import Path
from typing import Any

import requests

from dehps.config import ROOT_DIR, get_settings

logger = logging.getLogger(__name__)


class SsqDataSource(ABC):
    name: str

    @abstractmethod
    def fetch_latest(self) -> dict[str, Any] | None:
        raise NotImplementedError

    @abstractmethod
    def fetch_history(self, start_issue: str | None = None, end_issue: str | None = None) -> list[dict[str, Any]]:
        raise NotImplementedError


class ZhcwSsqDataSource(SsqDataSource):
    name = "zhcw"
    latest_url = "https://www.zhcw.com/kjxx/ssq/"
    history_url = "https://jc.zhcw.com/port/client_json.php"
    lottery_id = "1"
    default_history_years = 10
    page_size = 100

    def __init__(self) -> None:
        self.settings = get_settings()

    def _get_json_or_html(self, url: str, params: dict[str, Any] | None = None) -> Any:
        headers = {
            "Referer": self.latest_url,
            "User-Agent": self.settings.ssq_crawler_user_agent,
        }
        last_error: Exception | None = None
        for attempt in range(self.settings.ssq_crawler_max_retries + 1):
            try:
                response = requests.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=self.settings.ssq_crawler_timeout_seconds,
                )
                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
                if "json" in content_type:
                    return response.json()
                text = response.text.strip()
                if text.startswith("{"):
                    return json.loads(text)
                if "(" in text and text.endswith(")"):
                    return json.loads(text[text.find("(") + 1 : -1])
                return response.text
            except Exception as exc:
                last_error = exc
                if attempt < self.settings.ssq_crawler_max_retries:
                    time.sleep(1.5)
        raise RuntimeError(f"failed to fetch {url}: {last_error}")

    def fetch_latest(self) -> dict[str, Any] | None:
        rows = self._fetch_history_page(query_type=0, page_num=1, page_size=1, issue_count=1)
        return _normalize_remote_record(rows[0], self.name) if rows else None

    def fetch_history(self, start_issue: str | None = None, end_issue: str | None = None) -> list[dict[str, Any]]:
        if start_issue or end_issue:
            first = self._fetch_history_response(
                query_type=1,
                page_num=1,
                page_size=self.page_size,
                start_issue=start_issue or "0",
                end_issue=end_issue or "0",
            )
        else:
            today = date.today()
            start_date = _subtract_years(today, self.default_history_years).isoformat()
            first = self._fetch_history_response(
                query_type=2,
                page_num=1,
                page_size=self.page_size,
                start_date=start_date,
                end_date=today.isoformat(),
            )

        rows = [_normalize_remote_record(record, self.name) for record in first.get("data", [])]
        pages = int(first.get("pages") or 1)
        for page_num in range(2, pages + 1):
            if start_issue or end_issue:
                page = self._fetch_history_response(
                    query_type=1,
                    page_num=page_num,
                    page_size=self.page_size,
                    start_issue=start_issue or "0",
                    end_issue=end_issue or "0",
                )
            else:
                page = self._fetch_history_response(
                    query_type=2,
                    page_num=page_num,
                    page_size=self.page_size,
                    start_date=start_date,
                    end_date=today.isoformat(),
                )
            rows.extend(_normalize_remote_record(record, self.name) for record in page.get("data", []))
        return rows

    def _fetch_history_page(
        self,
        *,
        query_type: int,
        page_num: int,
        page_size: int,
        issue_count: int = 0,
        start_issue: str = "0",
        end_issue: str = "0",
        start_date: str = "",
        end_date: str = "",
    ) -> list[dict[str, Any]]:
        return self._fetch_history_response(
            query_type=query_type,
            page_num=page_num,
            page_size=page_size,
            issue_count=issue_count,
            start_issue=start_issue,
            end_issue=end_issue,
            start_date=start_date,
            end_date=end_date,
        ).get("data", [])

    def _fetch_history_response(
        self,
        *,
        query_type: int,
        page_num: int,
        page_size: int,
        issue_count: int = 0,
        start_issue: str = "0",
        end_issue: str = "0",
        start_date: str = "",
        end_date: str = "",
    ) -> dict[str, Any]:
        payload = self._get_json_or_html(
            self.history_url,
            {
                "transactionType": "10001001",
                "lotteryId": self.lottery_id,
                "type": query_type,
                "pageNum": page_num,
                "pageSize": page_size,
                "issueCount": issue_count,
                "startIssue": start_issue,
                "endIssue": end_issue,
                "startDate": start_date,
                "endDate": end_date,
                "tt": time.time(),
            },
        )
        if not isinstance(payload, dict) or payload.get("resCode") not in (None, "000000"):
            snippet = str(payload)[:500]
            logger.error("failed to parse zhcw history response snippet: %s", snippet)
            raise RuntimeError("unable to parse zhcw history draw data")
        return payload


class CsvSsqDataSource(SsqDataSource):
    name = "csv"

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or ROOT_DIR / "data/raw/ssq_history_sample.csv"

    def fetch_latest(self) -> dict[str, Any] | None:
        rows = self.fetch_history()
        return rows[-1] if rows else None

    def fetch_history(self, start_issue: str | None = None, end_issue: str | None = None) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        with self.path.open(newline="") as fh:
            for row in csv.DictReader(fh):
                issue = row["issue"]
                if start_issue and issue < start_issue:
                    continue
                if end_issue and issue > end_issue:
                    continue
                rows.append(
                    {
                        "issue": issue,
                        "draw_date": row.get("draw_date"),
                        "red_numbers": [row[f"r{i}"] for i in range(1, 7)],
                        "blue_number": row.get("blue_number"),
                        "source": row.get("source") or self.name,
                    }
                )
        return rows


def get_data_source(source: str) -> SsqDataSource:
    if source == "zhcw":
        return ZhcwSsqDataSource()
    if source == "csv":
        return CsvSsqDataSource()
    raise ValueError(f"unsupported source: {source}")


def _normalize_remote_record(record: dict[str, Any], source: str) -> dict[str, Any]:
    red = record.get("red") or record.get("red_numbers") or record.get("redBalls") or record.get("frontWinningNum")
    if isinstance(red, str):
        red_numbers = red.replace(",", " ").split()
    else:
        red_numbers = red
    return {
        "issue": record.get("issue") or record.get("code") or record.get("term"),
        "draw_date": record.get("date") or record.get("draw_date") or record.get("openTime"),
        "red_numbers": red_numbers,
        "blue_number": record.get("blue") or record.get("blue_number") or record.get("blueBall") or record.get("backWinningNum"),
        "source": source,
    }


def _subtract_years(value: date, years: int) -> date:
    try:
        return value.replace(year=value.year - years)
    except ValueError:
        return value.replace(year=value.year - years, day=28)
