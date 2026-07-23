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


def extract_researchers(parquet_glob, out_db: Path, batch_size: int = 40) -> int:
    """parquet(グロブ・単一ファイル・ファイルリスト)から医療著者を抽出して SQLite へ。

    53GB・約2000ファイルを1クエリで流すと DuckDB がメモリを使い切り OOM kill される
    ため、ファイルをバッチに分けて逐次 INSERT する。
    """
    import glob as globmod

    biomed_fields = ",".join(f"'{f.split('/')[-1]}'" for f in config.BIOMED_FIELDS)
    health_num = config.HEALTH_DOMAIN.split("/")[-1]
    biomed_num = config.BIOMED_DOMAIN.split("/")[-1]

    if isinstance(parquet_glob, (list, tuple)):
        files = list(parquet_glob)
    else:
        files = sorted(globmod.glob(str(parquet_glob))) or [str(parquet_glob)]

    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute("INSTALL sqlite; LOAD sqlite;")
    con.execute("SET s3_region='us-east-1'; SET enable_progress_bar=false;")
    con.execute("SET preserve_insertion_order=false;")
    con.execute("SET memory_limit='8GB';")
    con.execute(f"ATTACH '{out_db}' AS out (TYPE sqlite);")
    for i in range(0, len(files), batch_size):
        batch = files[i:i + batch_size]
        flist = ",".join(f"'{f}'" for f in batch)
        _insert_batch(con, flist, biomed_fields, health_num, biomed_num)
        print(f"  extract: {min(i + batch_size, len(files))}/{len(files)} files", flush=True)
    con.execute("DETACH out;")
    con.close()

    db = sqlite3.connect(out_db)
    n = db.execute("SELECT count(*) FROM researchers").fetchone()[0]
    db.close()
    return n


def _insert_batch(con, flist, biomed_fields, health_num, biomed_num):
    con.execute(f"""
        INSERT INTO out.researchers
          (id, name, orcid, h_index, cited_by_count, works_count, i10_index,
           two_year_mean_citedness, country_code, institution_id, institution_name,
           primary_field, primary_topic, first_pub_year, last_pub_year, counts_by_year,
           rising_score, consistency_score)
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
          list_min(list_transform(t.cby, x -> x.year)) AS first_pub_year,
          list_max(list_transform(t.cby, x -> x.year)) AS last_pub_year,
          to_json(t.cby) AS counts_by_year,
          0.0 AS rising_score,
          0.0 AS consistency_score
        FROM read_parquet([{flist}]) a,
        LATERAL (SELECT
          regexp_replace(a.topics[1].domain.id, '^.*/', '') AS domain_short,
          'fields/' || regexp_replace(a.topics[1].field.id, '^.*/', '') AS field_short,
          -- OpenAlex の counts_by_year には壊れた年(0, 1197 等)が混入するため除去
          list_filter(a.counts_by_year, x -> x.year >= 1900 AND x.year <= {config.CURRENT_YEAR}) AS cby
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
