from datetime import date

import pytest
from dehps.crawler import ssq_client
from dehps.crawler.ssq_client import (
    CsvSsqDataSource,
    ZhcwSsqDataSource,
    _normalize_remote_record,
    _subtract_years,
)
from dehps.crawler.ssq_parser import validate_ssq_draw


def test_normalize_zhcw_record():
    draw = _normalize_remote_record(
        {
            "issue": "2026068",
            "openTime": "2026-06-15",
            "frontWinningNum": "01 02 03 04 05 06",
            "backWinningNum": "07",
        },
        "zhcw",
    )

    assert draw == {
        "issue": "2026068",
        "draw_date": "2026-06-15",
        "red_numbers": ["01", "02", "03", "04", "05", "06"],
        "blue_number": "07",
        "source": "zhcw",
    }


def test_normalize_remote_record_preserves_zero_blue_for_validation():
    draw = _normalize_remote_record(
        {
            "issue": "2026068",
            "frontWinningNum": "01 02 03 04 05 06",
            "blue": 0,
        },
        "zhcw",
    )

    assert draw["blue_number"] == 0
    with pytest.raises(ValueError, match="blue_number must be between 1 and 16"):
        validate_ssq_draw(draw)


def test_subtract_years_handles_leap_day():
    assert _subtract_years(date(2024, 2, 29), 10) == date(2014, 2, 28)


def test_zhcw_history_defaults_to_last_ten_years_until_system_date(monkeypatch):
    captured_params = []

    class FixedDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 6, 15)

    def fake_get_json(self, url, params=None):
        captured_params.append(params)
        return {
            "pageNum": "1",
            "pageSize": "100",
            "total": "1",
            "pages": "1",
            "data": [
                {
                    "issue": "2026068",
                    "openTime": "2026-06-15",
                    "frontWinningNum": "01 02 03 04 05 06",
                    "backWinningNum": "07",
                }
            ],
        }

    monkeypatch.setattr(ssq_client, "date", FixedDate)
    monkeypatch.setattr(ZhcwSsqDataSource, "_get_json_or_html", fake_get_json)

    rows = ZhcwSsqDataSource().fetch_history()

    assert rows[0]["issue"] == "2026068"
    assert captured_params[0]["type"] == 2
    assert captured_params[0]["startDate"] == "2016-06-15"
    assert captured_params[0]["endDate"] == "2026-06-15"


def test_zhcw_exact_issue_prize_record_is_reporting_only(monkeypatch):
    captured_params = []
    raw = {
        "issue": "2026097",
        "frontWinningNum": "01 02 03 04 05 06",
        "backWinningNum": "07",
        "winnerDetails": [
            {
                "awardEtc": tier,
                "baseBetWinner": {"awardMoney": amount, "awardNum": 1},
            }
            for tier, amount in enumerate(
                ("10000000", "264245", "3000", "200", "10", "5"), start=1
            )
        ],
    }

    def fake_get_json(self, url, params=None):
        captured_params.append(params)
        return {"resCode": "000000", "data": [raw]}

    monkeypatch.setattr(ZhcwSsqDataSource, "_get_json_or_html", fake_get_json)

    source = ZhcwSsqDataSource()
    assert source.fetch_issue_with_prizes("2026097") == raw
    assert captured_params == [
        {
            "transactionType": "10001001",
            "lotteryId": "1",
            "type": 1,
            "pageNum": 1,
            "pageSize": 10,
            "issueCount": 0,
            "startIssue": "2026097",
            "endIssue": "2026097",
            "startDate": "",
            "endDate": "",
            "tt": captured_params[0]["tt"],
        }
    ]
    assert source.fetch_latest() != raw


def test_zhcw_exact_issue_prize_record_rejects_duplicates(monkeypatch):
    monkeypatch.setattr(
        ZhcwSsqDataSource,
        "_fetch_history_response",
        lambda *args, **kwargs: {"data": [{"issue": "2026097"}, {"issue": "2026097"}]},
    )

    with pytest.raises(RuntimeError, match="duplicate exact issue prize records"):
        ZhcwSsqDataSource().fetch_issue_with_prizes("2026097")


def test_csv_source_requires_explicit_path(monkeypatch):
    monkeypatch.delenv("SSQ_CSV_PATH", raising=False)

    with pytest.raises(ValueError, match="CSV source requires"):
        CsvSsqDataSource()


def test_csv_source_reads_explicit_file(tmp_path):
    csv_path = tmp_path / "history.csv"
    csv_path.write_text(
        "\n".join(
            [
                "issue,draw_date,r1,r2,r3,r4,r5,r6,blue_number,source",
                "2026001,2026-01-04,1,6,10,17,22,30,8,test",
            ]
        )
    )

    rows = CsvSsqDataSource(csv_path).fetch_history()

    assert rows == [
        {
            "issue": "2026001",
            "draw_date": "2026-01-04",
            "red_numbers": ["1", "6", "10", "17", "22", "30"],
            "blue_number": "8",
            "source": "test",
        }
    ]


def test_csv_source_latest_uses_highest_issue_not_file_order(tmp_path):
    csv_path = tmp_path / "history.csv"
    csv_path.write_text(
        "\n".join(
            [
                "issue,draw_date,r1,r2,r3,r4,r5,r6,blue_number,source",
                "2026003,2026-01-11,3,7,11,18,23,31,10,test",
                "2026001,2026-01-04,1,6,10,17,22,30,8,test",
                "2026002,2026-01-08,2,7,11,18,23,31,9,test",
            ]
        ),
        encoding="utf-8",
    )

    latest = CsvSsqDataSource(csv_path).fetch_latest()

    assert latest is not None
    assert latest["issue"] == "2026003"
    assert latest["blue_number"] == "10"


def test_csv_source_trims_issue_before_range_filtering(tmp_path):
    csv_path = tmp_path / "history.csv"
    csv_path.write_text(
        "\n".join(
            [
                "issue,draw_date,r1,r2,r3,r4,r5,r6,blue_number,source",
                "2026001,2026-01-04,1,6,10,17,22,30,8,test",
                " 2026002 ,2026-01-08,2,7,11,18,23,31,9,test",
            ]
        ),
        encoding="utf-8",
    )

    rows = CsvSsqDataSource(csv_path).fetch_history(
        start_issue=" 2026002 ", end_issue="2026002"
    )

    assert [row["issue"] for row in rows] == ["2026002"]
    assert rows[0]["blue_number"] == "9"


def test_csv_source_reports_missing_required_columns(tmp_path):
    csv_path = tmp_path / "history.csv"
    csv_path.write_text(
        "\n".join(
            [
                "issue,draw_date,r1,r2,r3,r4,r5,blue_number,source",
                "2026001,2026-01-04,1,6,10,17,22,8,test",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"missing required columns: r6"):
        CsvSsqDataSource(csv_path).fetch_history()
