import sqlite3
from pathlib import Path


def build_fts(db_path: Path) -> int:
    db = sqlite3.connect(db_path)
    db.execute("DROP TABLE IF EXISTS researchers_fts")
    db.execute("""CREATE VIRTUAL TABLE researchers_fts USING fts5(
      id UNINDEXED, name, institution_name, primary_field, tokenize='unicode61')""")
    db.execute("""INSERT INTO researchers_fts (id, name, institution_name, primary_field)
      SELECT id, name, coalesce(institution_name, ''), coalesce(primary_field, '') FROM researchers""")
    n = db.execute("SELECT count(*) FROM researchers_fts").fetchone()[0]
    db.commit()
    db.close()
    return n


def search(db_path: Path, q: str, limit: int = 20):
    db = sqlite3.connect(db_path)
    q = q.replace('"', " ").strip()
    if not q:
        db.close()
        return []
    rows = db.execute(
        """SELECT id, name, institution_name FROM researchers_fts
           WHERE researchers_fts MATCH ? ORDER BY rank LIMIT ?""",
        (q + "*", limit),
    ).fetchall()
    db.close()
    return rows
