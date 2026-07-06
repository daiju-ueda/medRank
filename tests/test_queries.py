import sqlite3

import pytest

from medrank.web import queries
from medrank.etl import build

PART = "data/snapshot/updated_date=2026-06-26/part_0000.parquet"


@pytest.fixture(scope="module")
def real_db(tmp_path_factory):
    p = tmp_path_factory.mktemp("db") / "researchers.db"
    build.build(PART, target_db=p, build_db=p.with_suffix(".build"))
    return p


def _con(p):
    c = sqlite3.connect(p)
    c.row_factory = sqlite3.Row
    return c


def test_ranking_page_joined(real_db):
    c = _con(real_db)
    rows = queries.ranking_page(c, "h_index__global", limit=10)
    assert len(rows) == 10
    assert rows[0]["rank"] == 1 and rows[0]["name"]
    assert rows[0]["h_index"] >= rows[1]["h_index"]


def test_researcher_and_their_rankings(real_db):
    c = _con(real_db)
    rid = queries.ranking_page(c, "h_index__global", limit=1)[0]["researcher_id"]
    r = queries.researcher(c, rid)
    assert r["id"] == rid
    appears = queries.researcher_rankings(c, rid)
    assert any(x["ranking_key"] == "h_index__global" for x in appears)
