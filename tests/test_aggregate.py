import sqlite3
from pathlib import Path

from medrank.etl import aggregate


def _seed(tmp_path):
    db = sqlite3.connect(tmp_path / "a.db")
    db.executescript(Path("medrank/etl/schema.sql").read_text())
    db.executemany("""INSERT INTO researchers
      (id,name,h_index,cited_by_count,works_count,i10_index,country_code,institution_id,institution_name,primary_field)
      VALUES (?,?,?,?,?,?,?,?,?,?)""", [
        ("A1", "X", 30, 1000, 50, 20, "JP", "I1", "Univ A", "medicine"),
        ("A2", "Y", 20, 500, 40, 10, "JP", "I1", "Univ A", "neuroscience"),
        ("A3", "Z", 10, 100, 20, 5, "US", "I2", "Univ B", "medicine"),
    ])
    db.commit()
    db.close()
    return tmp_path / "a.db"


def test_aggregate_counts(tmp_path):
    p = _seed(tmp_path)
    ninst, ncty = aggregate.aggregate(p)
    db = sqlite3.connect(p)
    assert ninst == 2 and ncty == 2
    inst = db.execute("SELECT researcher_count,total_citations FROM institutions WHERE id='I1'").fetchone()
    assert inst == (2, 1500)
    jp = db.execute("SELECT researcher_count FROM countries WHERE code='JP'").fetchone()[0]
    assert jp == 2


def test_country_name_covers_iso_and_prefers_short():
    from medrank.etl.aggregate import country_name
    assert country_name("BD") == "Bangladesh"      # pycountry fallback
    assert country_name("RU") == "Russia"          # curated short name wins
    assert country_name("ET") == "Ethiopia"
    assert country_name("ZZ") == "ZZ"              # unknown -> raw code
