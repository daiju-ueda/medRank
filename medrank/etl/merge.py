"""Consolidate OpenAlex author fragments that are clearly one person.

Two edges link records into a single person:
  ② shared non-empty ORCID (a person keeps their ORCID across institutions)
  ① identical name + same institution_id + same primary_field, when the group
     carries at most one distinct ORCID (guards against same-name different-people)

Edges feed a union-find. Any resulting component that still contains two
distinct ORCIDs is rejected (left unmerged) — never glue two real people.

Merging disjoint publication sets: works_count, cited_by_count, i10_index and
per-year counts are additive. h_index is NOT (needs the paper-level citation
distribution we don't have), so the merged record keeps the max fragment
h_index as a flagged lower bound.
"""
import json
import sqlite3
from pathlib import Path


class _UF:
    def __init__(self):
        self.p = {}

    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[ra] = rb


def _components(db):
    uf = _UF()
    # ② ORCID edges
    for (ids,) in db.execute(
        "SELECT group_concat(id) FROM researchers WHERE orcid<>'' "
        "GROUP BY orcid HAVING count(*)>1"
    ):
        parts = ids.split(",")
        for x in parts[1:]:
            uf.union(parts[0], x)
    # ① name+institution+field edges, only when <=1 distinct ORCID in the group
    for (ids,) in db.execute(
        """SELECT group_concat(id) FROM researchers
           WHERE institution_id<>'' AND primary_field IS NOT NULL
           GROUP BY name, institution_id, primary_field
           HAVING count(*)>1 AND count(DISTINCT CASE WHEN orcid<>'' THEN orcid END)<=1"""
    ):
        parts = ids.split(",")
        for x in parts[1:]:
            uf.union(parts[0], x)

    comps = {}
    for node in list(uf.p):
        comps.setdefault(uf.find(node), []).append(node)
    return [c for c in comps.values() if len(c) > 1]


def _merge_counts(rows):
    """複数 counts_by_year(JSON)を年ごとに合算。"""
    acc = {}
    for cby in rows:
        for c in json.loads(cby) if cby else []:
            y = c["year"]
            a = acc.setdefault(y, {"year": y, "works_count": 0, "cited_by_count": 0})
            a["works_count"] += c.get("works_count", 0)
            a["cited_by_count"] += c.get("cited_by_count", 0)
    return [acc[y] for y in sorted(acc)]


def merge_duplicates(db_path: Path) -> dict:
    db = sqlite3.connect(db_path)
    db.execute("DELETE FROM aliases")
    comps = _components(db)

    merged_people = 0
    removed = 0
    for comp in comps:
        qs = ",".join("?" * len(comp))
        recs = db.execute(
            f"SELECT id, orcid, h_index, cited_by_count, works_count, i10_index, "
            f"counts_by_year FROM researchers WHERE id IN ({qs})", comp
        ).fetchall()
        orcids = {r[1] for r in recs if r[1]}
        if len(orcids) > 1:
            continue  # 安全弁: 別人が混じった成分は触らない

        # 代表 = works 最大の断片(その id を生存させ URL を保つ)
        keep = max(recs, key=lambda r: r[4])
        keep_id = keep[0]
        others = [r for r in recs if r[0] != keep_id]

        works = sum(r[4] for r in recs)
        cites = sum(r[3] for r in recs)
        i10 = sum(r[5] for r in recs)
        h = max(r[2] for r in recs)                 # 下界(概算)
        counts = _merge_counts([r[6] for r in recs])
        years = [c["year"] for c in counts]
        first_y, last_y = (min(years), max(years)) if years else (None, None)

        db.execute(
            "UPDATE researchers SET h_index=?, cited_by_count=?, works_count=?, i10_index=?, "
            "counts_by_year=?, first_pub_year=?, last_pub_year=?, merged_from=? WHERE id=?",
            (h, cites, works, i10, json.dumps(counts), first_y, last_y, len(others), keep_id),
        )
        db.executemany("INSERT INTO aliases (old_id, canonical_id) VALUES (?,?)",
                       [(r[0], keep_id) for r in others])
        db.execute(f"DELETE FROM researchers WHERE id IN ({','.join('?' * len(others))})",
                   [r[0] for r in others])
        merged_people += 1
        removed += len(others)

    db.commit()
    db.close()
    return {"people_merged": merged_people, "fragments_removed": removed}
