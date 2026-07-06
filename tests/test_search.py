import sqlite3
from pathlib import Path

from medrank.etl import search


def _seed(tmp_path):
    db = sqlite3.connect(tmp_path / "s.db")
    db.executescript(Path("medrank/etl/schema.sql").read_text())
    db.executemany("""INSERT INTO researchers
      (id,name,h_index,cited_by_count,works_count,i10_index,institution_name,primary_field)
      VALUES (?,?,?,?,?,?,?,?)""", [
        ("A1", "Kazuo Tanaka", 30, 900, 50, 20, "Osaka University", "medicine"),
        ("A2", "Jane Smith", 25, 700, 40, 15, "Harvard University", "neuroscience")])
    db.commit()
    db.close()
    return tmp_path / "s.db"


def test_search_by_name(tmp_path):
    p = _seed(tmp_path)
    search.build_fts(p)
    res = search.search(p, "Tanaka")
    assert res and res[0][0] == "A1"


def test_search_by_institution(tmp_path):
    p = _seed(tmp_path)
    search.build_fts(p)
    res = search.search(p, "Harvard")
    assert any(r[0] == "A2" for r in res)
