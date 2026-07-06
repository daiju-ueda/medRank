import sqlite3
from pathlib import Path

from medrank.etl import rankings


def _seed(tmp_path):
    db = sqlite3.connect(tmp_path / "r.db")
    db.executescript(Path("medrank/etl/schema.sql").read_text())
    data = []
    for i in range(1, 21):
        data.append((f"A{i}", f"R{i}", i, i * 100, i * 5, i, 2000 + i % 5,
                     "JP", f"I{i%3}", f"Inst{i%3}",
                     "medicine" if i % 2 else "neuroscience", float(i), float(20 - i)))
    db.executemany("""INSERT INTO researchers
      (id,name,h_index,cited_by_count,works_count,i10_index,last_pub_year,country_code,
       institution_id,institution_name,primary_field,rising_score,consistency_score)
      VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", data)
    db.commit()
    db.close()
    return tmp_path / "r.db"


def test_build_rankings_global_h_index(tmp_path):
    p = _seed(tmp_path)
    rankings.build_rankings(p, top_n=10)
    db = sqlite3.connect(p)
    top = db.execute("""SELECT researcher_id,rank,value FROM rankings
      WHERE ranking_key='h_index__global' ORDER BY rank LIMIT 1""").fetchone()
    assert top[0] == "A20" and top[1] == 1 and top[2] == 20.0
    n = db.execute("SELECT count(*) FROM rankings WHERE ranking_key='h_index__global'").fetchone()[0]
    assert n == 10


def test_field_and_country_rankings_exist(tmp_path):
    p = _seed(tmp_path)
    rankings.build_rankings(p, top_n=10)
    db = sqlite3.connect(p)
    keys = {r[0] for r in db.execute("SELECT DISTINCT ranking_key FROM rankings")}
    assert "h_index__field=medicine" in keys
    assert "h_index__country=JP" in keys
    assert "rising__global" in keys
    meta_keys = {r[0] for r in db.execute("SELECT ranking_key FROM ranking_meta")}
    assert meta_keys == keys
