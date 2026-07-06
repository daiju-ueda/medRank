import sqlite3

import pytest
from fastapi.testclient import TestClient

from medrank.etl import build
from medrank import config

PART = "data/snapshot/updated_date=2026-06-26/part_0000.parquet"


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    p = tmp_path_factory.mktemp("d") / "researchers.db"
    build.build(PART, target_db=p, build_db=p.with_suffix(".build"))
    config.DB_PATH = p                       # ルートが読む DB を差し替え
    import medrank.web.app as appmod
    return TestClient(appmod.create_app())


def test_home_200(client):
    r = client.get("/")
    assert r.status_code == 200 and "MedRank" in r.text


def test_global_ranking_page(client):
    r = client.get("/rankings/h-index")
    assert r.status_code == 200
    assert "h-index" in r.text.lower()


def test_field_ranking_page(client):
    r = client.get("/rankings/h-index/medicine")
    assert r.status_code == 200


def test_researcher_page_and_404(client):
    c = sqlite3.connect(config.DB_PATH)
    c.row_factory = sqlite3.Row
    row = c.execute(
        "SELECT r.id,r.name FROM rankings k JOIN researchers r ON r.id=k.researcher_id "
        "WHERE k.ranking_key='h_index__global' AND k.rank=1"
    ).fetchone()
    from medrank.web.slug import researcher_slug
    r = client.get(f"/researcher/{researcher_slug(row['id'], row['name'])}")
    assert r.status_code == 200 and row["name"] in r.text
    assert client.get("/researcher/A0-nobody").status_code == 404


def test_search_json(client):
    r = client.get("/search?q=a&format=json")
    assert r.status_code == 200 and isinstance(r.json(), list)


def test_sitemap_index_and_shards(client):
    assert client.get("/methodology").status_code == 200
    sm = client.get("/sitemap.xml")
    assert sm.status_code == 200 and "sitemapindex" in sm.text
    assert "sitemap-researchers-0.xml" in sm.text
    core = client.get("/sitemap-core.xml")
    assert core.status_code == 200 and "/rankings/h-index" in core.text
    shard = client.get("/sitemap-researchers-0.xml")
    assert shard.status_code == 200 and "/researcher/A" in shard.text
    assert client.get("/sitemap-researchers-999.xml").status_code == 404


def test_html_404_page(client):
    r = client.get("/researcher/A0-nobody")
    assert r.status_code == 404
    assert "isn't in the map" in r.text          # 素のJSONでなくブランドされた404


def test_cache_headers(client):
    r = client.get("/rankings/h-index")
    assert "max-age" in r.headers.get("cache-control", "")


def test_ranking_pagination(client):
    p1 = client.get("/rankings/h-index")
    p2 = client.get("/rankings/h-index?page=2")
    assert p1.status_code == p2.status_code == 200
    assert p1.text != p2.text


def test_og_images(client):
    import sqlite3
    from medrank import config as cfg
    c = sqlite3.connect(cfg.DB_PATH)
    rid = c.execute("SELECT id FROM researchers LIMIT 1").fetchone()[0]
    r = client.get(f"/og/researcher/{rid}.png")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n"
    r2 = client.get("/og/ranking.png?key=h_index__global")
    assert r2.status_code == 200 and r2.content[:4] == b"\x89PNG"
