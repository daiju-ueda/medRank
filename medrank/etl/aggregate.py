import sqlite3
import statistics
from pathlib import Path

COUNTRY_NAMES = {
    "JP": "Japan", "US": "United States", "GB": "United Kingdom", "CN": "China",
    "DE": "Germany", "FR": "France", "CA": "Canada", "IT": "Italy", "AU": "Australia",
    "IN": "India", "KR": "South Korea", "ES": "Spain", "NL": "Netherlands", "BR": "Brazil",
    "CH": "Switzerland", "SE": "Sweden", "BE": "Belgium", "DK": "Denmark", "NO": "Norway",
    "FI": "Finland", "AT": "Austria", "PL": "Poland", "IL": "Israel", "TR": "Turkey",
    "IR": "Iran", "RU": "Russia", "TW": "Taiwan", "SG": "Singapore", "HK": "Hong Kong",
    "PT": "Portugal", "GR": "Greece", "MX": "Mexico", "AR": "Argentina", "ZA": "South Africa",
    "EG": "Egypt", "SA": "Saudi Arabia", "TH": "Thailand", "MY": "Malaysia", "ID": "Indonesia",
    "NZ": "New Zealand", "IE": "Ireland", "CZ": "Czechia", "HU": "Hungary", "CL": "Chile",
    "CO": "Colombia", "PK": "Pakistan", "NG": "Nigeria", "UA": "Ukraine", "RO": "Romania",
}


def aggregate(db_path: Path):
    db = sqlite3.connect(db_path)
    db.execute("DELETE FROM institutions")
    db.execute("DELETE FROM countries")
    db.execute("""
        INSERT INTO institutions (id, name, country_code, researcher_count, total_citations, top_field)
        SELECT institution_id, max(institution_name), max(country_code),
               count(*), sum(cited_by_count),
               (SELECT primary_field FROM researchers r2
                WHERE r2.institution_id = r1.institution_id
                GROUP BY primary_field ORDER BY count(*) DESC LIMIT 1)
        FROM researchers r1
        WHERE institution_id IS NOT NULL AND institution_id <> ''
        GROUP BY institution_id
    """)
    rows = db.execute("""
        SELECT country_code, group_concat(h_index), count(*), sum(cited_by_count)
        FROM researchers
        WHERE country_code IS NOT NULL AND country_code <> ''
        GROUP BY country_code
    """).fetchall()
    for code, hs, cnt, cites in rows:
        med = statistics.median(int(x) for x in hs.split(","))
        db.execute(
            "INSERT INTO countries (code, name, researcher_count, median_h_index, total_citations) VALUES (?,?,?,?,?)",
            (code, COUNTRY_NAMES.get(code, code), cnt, med, cites),
        )
    ninst = db.execute("SELECT count(*) FROM institutions").fetchone()[0]
    ncty = db.execute("SELECT count(*) FROM countries").fetchone()[0]
    db.commit()
    db.close()
    return ninst, ncty
