import os
import sqlite3
import time
from pathlib import Path

from medrank import config
from medrank.etl import extract, scores, aggregate, rankings, search

SCHEMA = Path(__file__).parent / "schema.sql"


def validate(db_path: Path) -> dict:
    db = sqlite3.connect(db_path)
    n = db.execute("SELECT count(*) FROM researchers").fetchone()[0]
    if n < 1000:
        raise ValueError(f"too few researchers: {n}")
    null_name = db.execute("SELECT count(*) FROM researchers WHERE name IS NULL OR name=''").fetchone()[0]
    if null_name > 0:
        raise ValueError(f"{null_name} researchers with empty name")
    nr = db.execute("SELECT count(DISTINCT ranking_key) FROM rankings").fetchone()[0]
    if nr < 1:
        raise ValueError("no rankings")
    db.close()
    return {"researchers": n, "ranking_keys": nr}


def build(parquet_glob: str, target_db: Path = None, build_db: Path = None) -> dict:
    target_db = Path(target_db or config.DB_PATH)
    build_db = Path(build_db or config.DB_BUILD_PATH)
    if build_db.exists():
        build_db.unlink()
    build_db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(build_db)
    con.executescript(SCHEMA.read_text())
    con.commit()
    con.close()

    t0 = time.time()
    n = extract.extract_researchers(parquet_glob, build_db)
    scores.update_scores(build_db)
    ninst, ncty = aggregate.aggregate(build_db)
    nkeys = rankings.build_rankings(build_db)
    nfts = search.build_fts(build_db)
    validate(build_db)

    db = sqlite3.connect(build_db)
    db.execute("INSERT OR REPLACE INTO meta VALUES ('built_at', datetime('now'))")
    db.execute("INSERT OR REPLACE INTO meta VALUES ('researcher_count', ?)", (str(n),))
    db.commit()
    db.close()

    os.replace(build_db, target_db)   # アトミック差し替え
    return {"researchers": n, "institutions": ninst, "countries": ncty,
            "rankings_keys": nkeys, "fts": nfts, "seconds": round(time.time() - t0, 1)}


if __name__ == "__main__":
    import sys
    from medrank.etl import sync
    glob = sys.argv[1] if len(sys.argv) > 1 else sync.latest_partition_glob()
    print(build(glob))
