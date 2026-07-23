"""Canonical institution names.

The author snapshot stores each researcher's *cached* institution name, so a
single institution can appear under stale and current names at once (e.g. Osaka
University → "The University of Osaka" after its 2025 rename). The institutions
snapshot (~96 MB) is the authoritative current name per institution id.
"""
import sqlite3
from pathlib import Path

import duckdb

INSTITUTIONS_S3 = "s3://openalex/data/parquet/institutions/*/*.parquet"


def canonical_names(source: str = INSTITUTIONS_S3) -> dict:
    """institution id(短形)-> 現行の display_name。"""
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; SET s3_region='us-east-1'; SET enable_progress_bar=false;")
    rows = con.execute(
        f"SELECT regexp_replace(id, '^.*/', ''), display_name "
        f"FROM read_parquet('{source}') WHERE display_name IS NOT NULL"
    ).fetchall()
    con.close()
    return {rid: name for rid, name in rows}


def canonicalize(db_path: Path, source: str = INSTITUTIONS_S3) -> int:
    """researchers.institution_name を正規名に統一する。更新した行数を返す。

    これを aggregate の前に走らせると、institutions テーブルの名前も自動的に揃う。
    """
    names = canonical_names(source)
    db = sqlite3.connect(db_path)
    ids = [r[0] for r in db.execute(
        "SELECT DISTINCT institution_id FROM researchers "
        "WHERE institution_id IS NOT NULL AND institution_id <> ''")]
    updates = [(names[i], i) for i in ids if i in names]
    db.executemany(
        "UPDATE researchers SET institution_name=? WHERE institution_id=?", updates)
    db.commit()
    db.close()
    return len(updates)
