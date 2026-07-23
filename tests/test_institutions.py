import sqlite3
from pathlib import Path

from medrank.etl import institutions


def _seed(tmp_path):
    db = sqlite3.connect(tmp_path / "i.db")
    db.executescript(Path("medrank/etl/schema.sql").read_text())
    # 同一機関 I1 が新旧2名で混在
    db.executemany("""INSERT INTO researchers
      (id,name,h_index,cited_by_count,works_count,i10_index,institution_id,institution_name)
      VALUES (?,?,?,?,?,?,?,?)""", [
        ("A1", "X", 30, 900, 50, 20, "I1", "Osaka University"),
        ("A2", "Y", 20, 500, 40, 10, "I1", "The University of Osaka"),
        ("A3", "Z", 10, 100, 20, 5, "I2", "Somewhere"),
    ])
    db.commit()
    db.close()
    return tmp_path / "i.db"


def test_canonicalize_unifies_names(tmp_path, monkeypatch):
    p = _seed(tmp_path)
    monkeypatch.setattr(institutions, "canonical_names",
                        lambda source=None: {"I1": "The University of Osaka"})
    n = institutions.canonicalize(p, source="x")
    assert n == 1
    db = sqlite3.connect(p)
    names = {r[0] for r in db.execute(
        "SELECT DISTINCT institution_name FROM researchers WHERE institution_id='I1'")}
    assert names == {"The University of Osaka"}      # 揺れが解消
    # 未収載の機関はそのまま
    assert db.execute("SELECT institution_name FROM researchers WHERE id='A3'").fetchone()[0] == "Somewhere"
