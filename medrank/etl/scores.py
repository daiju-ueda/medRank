import json
import math
import sqlite3
import statistics
from pathlib import Path

from medrank.config import CURRENT_YEAR, RISING_MIN_RECENT


def _cites(counts):
    return {c["year"]: c.get("cited_by_count", 0) for c in counts}


def career_start(counts):
    """Robust first-active year.

    OpenAlex counts_by_year carries misattributed 1-work entries decades before a
    researcher's real career. Return the earliest year at which cumulative output
    first reaches 5% of the total — skipping that noisy tail.
    """
    ws = sorted((c["year"], c.get("works_count", 0)) for c in counts if c.get("works_count", 0) > 0)
    total = sum(w for _, w in ws)
    if not ws or total == 0:
        return None
    cum = 0
    for y, w in ws:
        cum += w
        if cum >= 0.05 * total:
            return y
    return ws[0][0]


def rising_score(counts, now_year: int = CURRENT_YEAR) -> float:
    if not counts:
        return 0.0
    c = _cites(counts)
    recent = sum(c.get(y, 0) for y in range(now_year - 2, now_year + 1))
    if recent < RISING_MIN_RECENT:
        # 母数が小さい「新規参入」は伸び率が無限大に見えるだけでノイズ。対象外。
        return 0.0
    prior = sum(c.get(y, 0) for y in range(now_year - 5, now_year - 2))
    growth = (recent + 1) / (prior + 1)
    return round(growth * math.log10(recent + 10), 4)


def consistency_score(counts, now_year: int = CURRENT_YEAR) -> float:
    if not counts:
        return 0.0
    c = _cites(counts)
    years = [c.get(y, 0) for y in range(now_year - 9, now_year + 1)]
    active = [v for v in years if v > 0]
    if len(active) < 2:
        return 0.0
    mean = statistics.mean(years)
    if mean == 0:
        return 0.0
    cv = statistics.pstdev(years) / mean       # 変動係数
    coverage = len(active) / len(years)         # 何年埋まっているか
    return round(coverage / (1 + cv), 4)


def update_scores(db_path: Path, now_year: int = CURRENT_YEAR, batch: int = 50_000) -> int:
    """rowid キーセットページングで一定メモリのまま全行を更新する(数百万行対応)。"""
    db = sqlite3.connect(db_path)
    total = 0
    last_rowid = 0
    while True:
        rows = db.execute(
            "SELECT rowid, id, counts_by_year FROM researchers "
            "WHERE rowid > ? ORDER BY rowid LIMIT ?", (last_rowid, batch),
        ).fetchall()
        if not rows:
            break
        last_rowid = rows[-1][0]
        updates = []
        for _, rid, cby in rows:
            counts = json.loads(cby) if cby else []
            updates.append((rising_score(counts, now_year), consistency_score(counts, now_year),
                            career_start(counts), rid))
        db.executemany(
            "UPDATE researchers SET rising_score=?, consistency_score=?, "
            "first_pub_year=coalesce(?, first_pub_year) WHERE id=?",
            updates,
        )
        db.commit()
        total += len(updates)
    db.close()
    return total
