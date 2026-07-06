import sqlite3
from pathlib import Path

from medrank import config
from medrank.etl.aggregate import COUNTRY_NAMES

CLASSIC = {  # metric -> (列, 表示名)
    "h_index": ("h_index", "H-index"),
    "citations": ("cited_by_count", "Total Citations"),
    "works": ("works_count", "Publications"),
}
TREND = {
    "rising": ("rising_score", "Rising Stars"),
    "consistency": ("consistency_score", "Most Consistent"),
}


def _insert(db, key, col, where, top_n, meta) -> int:
    sql = f"""INSERT INTO rankings (ranking_key, rank, researcher_id, value)
      SELECT ?, row_number() OVER (ORDER BY {col} DESC, id), id, {col}
      FROM researchers {where} ORDER BY {col} DESC, id LIMIT ?"""
    cur = db.execute(sql, (key, top_n))
    inserted = cur.rowcount
    if inserted <= 0:
        return 0
    # meta の size は実際に入った件数
    meta = meta[:-1] + (inserted,)
    db.execute(
        """INSERT OR REPLACE INTO ranking_meta
           (ranking_key, title, category, field, country, metric, size) VALUES (?,?,?,?,?,?,?)""",
        meta,
    )
    return inserted


def build_rankings(db_path: Path, top_n: int = config.RANKING_SIZE) -> int:
    db = sqlite3.connect(db_path)
    db.execute("DELETE FROM rankings")
    db.execute("DELETE FROM ranking_meta")
    fields = [r[0] for r in db.execute(
        "SELECT DISTINCT primary_field FROM researchers WHERE primary_field IS NOT NULL")]
    countries = [r[0] for r in db.execute(
        """SELECT country_code FROM researchers
           WHERE country_code IS NOT NULL AND country_code <> ''
           GROUP BY country_code HAVING count(*) >= 20""")]
    keys = set()

    def emit(key, col, where, title, cat, field=None, country=None, metric=None):
        inserted = _insert(db, key, col, where, top_n, (key, title, cat, field, country, metric, top_n))
        if inserted > 0:
            keys.add(key)

    for m, (col, label) in CLASSIC.items():
        emit(f"{m}__global", col, "",
             f"World's Top Medical Researchers by {label}", "classic", metric=m)
        for f in fields:
            fname = config.FIELD_NAMES.get(f, f.replace("-", " ").title())
            emit(f"{m}__field={f}", col, f"WHERE primary_field='{f}'",
                 f"Top {fname} Researchers by {label}",
                 "classic", field=f, metric=m)
        for c in countries:
            cname = COUNTRY_NAMES.get(c, c)
            emit(f"{m}__country={c}", col, f"WHERE country_code='{c}'",
                 f"Top Medical Researchers in {cname} by {label}",
                 "classic", country=c, metric=m)

    for m, (col, label) in TREND.items():
        cat = "trend" if m == "rising" else "story"
        emit(f"{m}__global", col, f"WHERE {col} > 0", label, cat, metric=m)

    # Young Guns: キャリア10年以内 かつ 現役(直近2年に出版あり)で h_index 上位
    emit("young_guns__global", "h_index",
         "WHERE last_pub_year IS NOT NULL AND first_pub_year IS NOT NULL "
         f"AND (last_pub_year - first_pub_year) <= 10 "
         f"AND last_pub_year >= {config.CURRENT_YEAR - 2}",
         "Young Guns — High Impact Early in Career", "trend", metric="young_guns")

    db.commit()
    db.close()
    return len(keys)
