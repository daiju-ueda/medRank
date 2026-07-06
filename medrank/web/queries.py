def ranking_page(db, ranking_key, offset=0, limit=100):
    return db.execute(
        """SELECT k.rank, k.value, k.researcher_id, r.* FROM rankings k
           JOIN researchers r ON r.id = k.researcher_id
           WHERE k.ranking_key = ? ORDER BY k.rank LIMIT ? OFFSET ?""",
        (ranking_key, limit, offset),
    ).fetchall()


def ranking_meta(db, ranking_key):
    return db.execute("SELECT * FROM ranking_meta WHERE ranking_key=?", (ranking_key,)).fetchone()


def researcher(db, id):
    return db.execute("SELECT * FROM researchers WHERE id=?", (id,)).fetchone()


def researcher_rankings(db, id):
    return db.execute(
        """SELECT k.ranking_key, k.rank, m.title, m.category FROM rankings k
           JOIN ranking_meta m ON m.ranking_key = k.ranking_key
           WHERE k.researcher_id = ? ORDER BY k.rank""",
        (id,),
    ).fetchall()


def list_rankings(db, category=None):
    if category:
        return db.execute(
            "SELECT * FROM ranking_meta WHERE category=? ORDER BY ranking_key", (category,)
        ).fetchall()
    return db.execute("SELECT * FROM ranking_meta ORDER BY category, ranking_key").fetchall()


def institution(db, id):
    return db.execute("SELECT * FROM institutions WHERE id=?", (id,)).fetchone()


def country(db, code):
    return db.execute("SELECT * FROM countries WHERE code=?", (code,)).fetchone()


def top_countries(db, limit=50):
    return db.execute(
        "SELECT * FROM countries ORDER BY researcher_count DESC LIMIT ?", (limit,)
    ).fetchall()


def search_researchers(db, q, limit=20):
    q = (q or "").replace('"', " ").strip()
    if not q:
        return []
    return db.execute(
        """SELECT r.* FROM researchers_fts f JOIN researchers r ON r.id = f.id
           WHERE researchers_fts MATCH ? ORDER BY rank LIMIT ?""",
        (q + "*", limit),
    ).fetchall()
