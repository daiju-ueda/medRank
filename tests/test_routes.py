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


def test_sitemap_and_methodology(client):
    assert client.get("/methodology").status_code == 200
    sm = client.get("/sitemap.xml")
    assert sm.status_code == 200 and "urlset" in sm.text
