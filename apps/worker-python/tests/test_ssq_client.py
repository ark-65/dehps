from datetime import date

from dehps.crawler import ssq_client
from dehps.crawler.ssq_client import ZhcwSsqDataSource, _normalize_remote_record, _subtract_years


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
