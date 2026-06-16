from __future__ import annotations

import pytest

from dehps.storage.postgres_store import load_red_combination_universe


class FakeConn:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, sql, params=None):
        return FakeResult(self.rows)


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows


def test_load_red_combination_universe_rejects_incomplete_table():
    with pytest.raises(ValueError, match="full C\\(33,6\\) universe"):
        load_red_combination_universe(FakeConn([([1, 2, 3, 4, 5, 6],)]))
