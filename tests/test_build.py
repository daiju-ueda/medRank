from pathlib import Path

import pytest

from medrank.etl import build

PART = "data/snapshot/updated_date=2026-06-26/part_0000.parquet"


def test_build_end_to_end(tmp_path):
    target = tmp_path / "researchers.db"
    work = tmp_path / "work.db"
    stats = build.build(PART, target_db=target, build_db=work)
    assert target.exists() and not work.exists()
    assert stats["researchers"] > 1000
    assert stats["rankings_keys"] > 0
    import sqlite3
    db = sqlite3.connect(target)
    assert db.execute("SELECT count(*) FROM rankings WHERE ranking_key='h_index__global'").fetchone()[0] > 0


def test_validate_rejects_empty(tmp_path):
    import sqlite3
    empty = tmp_path / "e.db"
    sqlite3.connect(empty).executescript(Path("medrank/etl/schema.sql").read_text())
    with pytest.raises(Exception):
        build.validate(empty)
