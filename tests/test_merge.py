import json
import sqlite3
from pathlib import Path

from medrank.etl import merge

SCHEMA = Path("medrank/etl/schema.sql").read_text()


def _db(tmp_path, rows):
    p = tmp_path / "m.db"
    db = sqlite3.connect(p)
    db.executescript(SCHEMA)
    db.executemany(
        """INSERT INTO researchers
           (id,name,orcid,h_index,cited_by_count,works_count,i10_index,
            institution_id,primary_field,counts_by_year)
           VALUES (?,?,?,?,?,?,?,?,?,?)""", rows)
    db.commit()
    db.close()
    return p


def test_merges_same_name_institution_field(tmp_path):
    p = _db(tmp_path, [
        ("A1", "Eugene Braunwald", "", 157, 90000, 900, 700, "I1", "medicine",
         json.dumps([{"year": 2020, "works_count": 10, "cited_by_count": 5000}])),
        ("A2", "Eugene Braunwald", "", 127, 40000, 300, 250, "I1", "medicine",
         json.dumps([{"year": 2020, "works_count": 4, "cited_by_count": 2000}])),
    ])
    stats = merge.merge_duplicates(p)
    assert stats["people_merged"] == 1 and stats["fragments_removed"] == 1
    db = sqlite3.connect(p)
    rows = db.execute("SELECT id,h_index,cited_by_count,works_count,i10_index,merged_from FROM researchers").fetchall()
    assert len(rows) == 1
    rid, h, cites, works, i10, mf = rows[0]
    assert rid == "A1"              # 最大 works の断片が生存
    assert h == 157                 # h は最大(下界)
    assert cites == 130000 and works == 1200 and i10 == 950   # 加算
    assert mf == 1
    assert db.execute("SELECT canonical_id FROM aliases WHERE old_id='A2'").fetchone()[0] == "A1"


def test_orcid_conflict_blocks_merge(tmp_path):
    p = _db(tmp_path, [
        ("A1", "Wei Zhang", "0000-0001", 40, 5000, 100, 50, "I1", "medicine", "[]"),
        ("A2", "Wei Zhang", "0000-0002", 30, 3000, 80, 40, "I1", "medicine", "[]"),
    ])
    stats = merge.merge_duplicates(p)
    assert stats["people_merged"] == 0            # 異なるORCID=別人、併合しない
    db = sqlite3.connect(p)
    assert db.execute("SELECT count(*) FROM researchers").fetchone()[0] == 2


def test_shared_orcid_merges_across_institutions(tmp_path):
    p = _db(tmp_path, [
        ("A1", "Jane Roe", "0000-0009", 214, 60000, 500, 400, "I1", "medicine", "[]"),
        ("A2", "Jane Roe", "0000-0009", 8, 200, 9, 5, "I2", "neuroscience", "[]"),
    ])
    stats = merge.merge_duplicates(p)
    assert stats["people_merged"] == 1            # ORCID一致は機関/分野をまたいで併合
    db = sqlite3.connect(p)
    assert db.execute("SELECT id FROM researchers").fetchone()[0] == "A1"


def test_transitive_two_orcids_component_rejected(tmp_path):
    # A1(orcid a)-A2(none) は名前群、A2-A3(orcid b) も名前群 → 連結すると a,b 併存
    p = _db(tmp_path, [
        ("A1", "Li Na", "0000-000a", 50, 9000, 120, 60, "I1", "medicine", "[]"),
        ("A2", "Li Na", "", 20, 2000, 40, 20, "I1", "medicine", "[]"),
        ("A3", "Li Na", "0000-000b", 45, 8000, 110, 55, "I1", "medicine", "[]"),
    ])
    stats = merge.merge_duplicates(p)
    assert stats["people_merged"] == 0            # 成分に2つのORCID → 安全弁で不併合
    db = sqlite3.connect(p)
    assert db.execute("SELECT count(*) FROM researchers").fetchone()[0] == 3
