import sqlite3
from pathlib import Path

from medrank.etl import extract
from medrank import config

PART = "data/snapshot/updated_date=2026-06-26/part_0000.parquet"


def _fresh_db(tmp_path):
    db = sqlite3.connect(tmp_path / "b.db")
    db.executescript(Path("medrank/etl/schema.sql").read_text())
    db.commit()
    db.close()
    return tmp_path / "b.db"


def test_field_slug():
    assert extract.field_slug("https://openalex.org/fields/27") == "medicine"
    assert extract.field_slug("https://openalex.org/fields/28") == "neuroscience"
    assert extract.field_slug("https://openalex.org/fields/99") is None


def test_extract_only_medical(tmp_path):
    out = _fresh_db(tmp_path)
    n = extract.extract_researchers(PART, out)
    db = sqlite3.connect(out)
    total = db.execute("SELECT count(*) FROM researchers").fetchone()[0]
    assert total == n and n > 1000
    fields = {r[0] for r in db.execute("SELECT DISTINCT primary_field FROM researchers")}
    assert fields <= set(s for s, _ in config.MEDICAL_FIELDS.values())
    bad = db.execute("SELECT count(*) FROM researchers WHERE works_count<5 OR h_index<2").fetchone()[0]
    assert bad == 0
    assert db.execute("SELECT id FROM researchers LIMIT 1").fetchone()[0].startswith("A")
