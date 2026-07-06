import sqlite3
from pathlib import Path

SCHEMA = Path("medrank/etl/schema.sql").read_text()


def test_schema_creates_core_tables(tmp_path):
    db = sqlite3.connect(tmp_path / "t.db")
    db.executescript(SCHEMA)
    tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"researchers", "institutions", "countries", "rankings", "meta"} <= tables


def test_researchers_has_expected_columns(tmp_path):
    db = sqlite3.connect(tmp_path / "t.db")
    db.executescript(SCHEMA)
    cols = {r[1] for r in db.execute("PRAGMA table_info(researchers)")}
    expected = {"id", "name", "orcid", "h_index", "cited_by_count", "works_count",
                "i10_index", "two_year_mean_citedness", "country_code", "institution_id",
                "institution_name", "primary_field", "primary_topic", "first_pub_year",
                "last_pub_year", "counts_by_year", "rising_score", "consistency_score"}
    assert expected <= cols
