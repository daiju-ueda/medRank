import sqlite3
from pathlib import Path

import duckdb

from medrank import config


def field_slug(field_id):
    if not field_id:
        return None
    short = "fields/" + field_id.rsplit("/", 1)[-1]
    m = config.MEDICAL_FIELDS.get(short)
    return m[0] if m else None


# DuckDB SQL: field 短形 (例 'fields/27') -> slug
_SLUG_CASE = "\n".join(
    f"WHEN t.field_short='{fid}' THEN '{slug}'"
    for fid, (slug, _) in config.MEDICAL_FIELDS.items()
)


def extract_researchers(parquet_glob: str, out_db: Path) -> int:
    biomed_fields = ",".join(f"'{f.split('/')[-1]}'" for f in config.BIOMED_FIELDS)
    health_num = config.HEALTH_DOMAIN.split("/")[-1]
    biomed_num = config.BIOMED_DOMAIN.split("/")[-1]

    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute("INSTALL sqlite; LOAD sqlite;")
    con.execute("SET s3_region='us-east-1'; SET enable_progress_bar=false;")
    con.execute(f"ATTACH '{out_db}' AS out (TYPE sqlite);")
    con.execute(f"""
        INSERT INTO out.researchers
        SELECT
          regexp_replace(a.id, '^.*/', '') AS id,
          a.display_name AS name,
          regexp_replace(coalesce(a.orcid, ''), '^.*/', '') AS orcid,
          a.summary_stats.h_index AS h_index,
          a.cited_by_count AS cited_by_count,
          a.works_count AS works_count,
          a.summary_stats.i10_index AS i10_index,
          a.summary_stats."2yr_mean_citedness" AS two_year_mean_citedness,
          a.last_known_institutions[1].country_code AS country_code,
          regexp_replace(coalesce(a.last_known_institutions[1].id, ''), '^.*/', '') AS institution_id,
          a.last_known_institutions[1].display_name AS institution_name,
          CASE {_SLUG_CASE} ELSE NULL END AS primary_field,
          a.topics[1].display_name AS primary_topic,
          list_min(list_transform(a.counts_by_year, x -> x.year)) AS first_pub_year,
          list_max(list_transform(a.counts_by_year, x -> x.year)) AS last_pub_year,
          to_json(a.counts_by_year) AS counts_by_year,
          0.0 AS rising_score,
          0.0 AS consistency_score
        FROM read_parquet('{parquet_glob}') a,
        LATERAL (SELECT
          regexp_replace(a.topics[1].domain.id, '^.*/', '') AS domain_short,
          'fields/' || regexp_replace(a.topics[1].field.id, '^.*/', '') AS field_short
        ) t
        WHERE a.works_count >= {config.MIN_WORKS}
          AND a.summary_stats.h_index >= {config.MIN_H}
          AND len(a.topics) > 0
          AND (
            t.domain_short = '{health_num}'
            OR (t.domain_short = '{biomed_num}'
                AND regexp_replace(a.topics[1].field.id, '^.*/', '') IN ({biomed_fields}))
          )
          AND (CASE {_SLUG_CASE} ELSE NULL END) IS NOT NULL
    """)
    con.execute("DETACH out;")
    con.close()

    db = sqlite3.connect(out_db)
    n = db.execute("SELECT count(*) FROM researchers").fetchone()[0]
    db.close()
    return n
