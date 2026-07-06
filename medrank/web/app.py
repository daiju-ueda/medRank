from pathlib import Path

from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.gzip import GZipMiddleware

from medrank import config
from medrank.web import db as dbm, queries, slug as slugm, og
from medrank.web.sparkline import sparkline

BASE = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE / "templates"))
templates.env.filters["sparkline"] = sparkline
templates.env.globals["slug"] = slugm
templates.env.globals["field_names"] = config.FIELD_NAMES
templates.env.globals["field_short"] = config.FIELD_SHORT
templates.env.filters["ord"] = ord
templates.env.filters["chr"] = chr

# URL(ハイフン)-> 内部 metric key(アンダースコア)
METRIC_SLUGS = {
    "h-index": "h_index", "citations": "citations", "publications": "works",
    "rising-stars": "rising", "consistency": "consistency", "young-guns": "young_guns",
}
METRIC_URLS = {v: k for k, v in METRIC_SLUGS.items()}
templates.env.globals["metric_urls"] = METRIC_URLS
SITE_URL = "https://researchers.med-ai.tech"
PAGE_SIZE = 100
SITEMAP_SHARD = 50_000


def ranking_url(key: str) -> str:
    metric = key.split("__")[0]
    base = METRIC_URLS.get(metric, metric.replace("_", "-"))
    if "__field=" in key:
        return f"/rankings/{base}/{key.split('=')[1]}"
    if "__country=" in key:
        return f"/rankings/{base}/all/{key.split('=')[1]}"
    return f"/rankings/{base}"


templates.env.globals["ranking_url"] = ranking_url


def create_app() -> FastAPI:
    app = FastAPI(title="MedRank")
    app.add_middleware(GZipMiddleware, minimum_size=500)
    app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")

    @app.middleware("http")
    async def cache_headers(request: Request, call_next):
        resp = await call_next(request)
        if "cache-control" not in resp.headers:
            if request.url.path.startswith("/static") or request.url.path.startswith("/og/"):
                resp.headers["cache-control"] = "public, max-age=604800, immutable"
            elif resp.status_code == 200:
                # 月次更新の読み取り専用サイト。ブラウザ10分・エッジ1日。
                resp.headers["cache-control"] = "public, max-age=600, s-maxage=86400"
        return resp

    def render(name, request, status_code=200, **ctx):
        ctx.setdefault("site_url", SITE_URL)
        ctx.setdefault("og_image", None)
        return templates.TemplateResponse(request, name, ctx, status_code=status_code)

    @app.exception_handler(404)
    async def not_found(request: Request, exc):
        if request.url.path.startswith(("/search", "/og/", "/static")):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        return render("404.html", request, status_code=404)

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request):
        db = dbm.get_db()
        feats = {
            "h_index__global": queries.ranking_page(db, "h_index__global", limit=10),
            "rising__global": queries.ranking_page(db, "rising__global", limit=10),
        }
        stats = {r["key"]: r["value"] for r in db.execute("SELECT key,value FROM meta")}
        return render("home.html", request, feats=feats,
                      countries=queries.top_countries(db, 12), stats=stats)

    @app.get("/rankings", response_class=HTMLResponse)
    def rankings_index(request: Request):
        db = dbm.get_db()
        cnames = {r["code"]: r["name"] for r in db.execute("SELECT code,name FROM countries")}
        corder = [r["code"] for r in db.execute(
            "SELECT code FROM countries ORDER BY researcher_count DESC")]
        trends = queries.list_rankings(db, "trend") + queries.list_rankings(db, "story")
        fields_by_metric, countries_by_metric = {}, {}
        for row in queries.list_rankings(db, "classic"):
            m = row["metric"]
            if row["field"]:
                fields_by_metric.setdefault(m, []).append(row["field"])
            elif row["country"]:
                countries_by_metric.setdefault(m, []).append(row["country"])
        for m, codes in countries_by_metric.items():
            codes.sort(key=lambda c: corder.index(c) if c in corder else 999)
        metrics = [("h_index", "H-index"), ("citations", "Total citations"),
                   ("works", "Publications")]
        return render("rankings_index.html", request, trends=trends, metrics=metrics,
                      fields_by_metric=fields_by_metric,
                      countries_by_metric=countries_by_metric, cnames=cnames)

    def _ranking_or_404(request, key, page=1):
        db = dbm.get_db()
        meta = queries.ranking_meta(db, key)
        if not meta:
            raise HTTPException(404)
        pages = max(1, -(-meta["size"] // PAGE_SIZE))
        page = max(1, min(page, pages))
        rows = queries.ranking_page(db, key, offset=(page - 1) * PAGE_SIZE, limit=PAGE_SIZE)
        # 姉妹ランキングへのピル
        fields = sorted({r["field"] for r in queries.list_rankings(db, "classic") if r["field"]})
        top_countries = queries.top_countries(db, 16)
        return render("ranking.html", request, meta=meta, rows=rows,
                      page=page, pages=pages, path=request.url.path,
                      fields=fields, top_countries=top_countries,
                      og_image=f"{SITE_URL}/og/ranking.png?key={key}")

    @app.get("/rankings/{metric}", response_class=HTMLResponse)
    def rank_global(request: Request, metric: str, page: int = 1):
        m = METRIC_SLUGS.get(metric) or metric
        return _ranking_or_404(request, f"{m}__global", page)

    @app.get("/rankings/{metric}/{field}", response_class=HTMLResponse)
    def rank_field(request: Request, metric: str, field: str, page: int = 1):
        m = METRIC_SLUGS.get(metric) or metric
        return _ranking_or_404(request, f"{m}__field={field}", page)

    @app.get("/rankings/{metric}/{field}/{country}", response_class=HTMLResponse)
    def rank_field_country(request: Request, metric: str, field: str, country: str, page: int = 1):
        m = METRIC_SLUGS.get(metric) or metric
        key = f"{m}__country={country.upper()}" if field == "all" else f"{m}__field={field}"
        return _ranking_or_404(request, key, page)

    @app.get("/researcher/{slug}", response_class=HTMLResponse)
    def researcher_page(request: Request, slug: str):
        db = dbm.get_db()
        r = queries.researcher(db, slugm.id_from_slug(slug))
        if not r:
            raise HTTPException(404)
        return render("researcher.html", request, r=r,
                      appears=queries.researcher_rankings(db, r["id"]),
                      og_image=f"{SITE_URL}/og/researcher/{r['id']}.png")

    @app.get("/institutions", response_class=HTMLResponse)
    def institutions_index(request: Request):
        db = dbm.get_db()
        rows = db.execute(
            "SELECT * FROM institutions ORDER BY total_citations DESC LIMIT 200"
        ).fetchall()
        return render("institutions.html", request, rows=rows)

    @app.get("/institutions/{slug}", response_class=HTMLResponse)
    def institution_page(request: Request, slug: str):
        db = dbm.get_db()
        inst = queries.institution(db, slugm.id_from_slug(slug))
        if not inst:
            raise HTTPException(404)
        members = db.execute(
            "SELECT * FROM researchers WHERE institution_id=? ORDER BY h_index DESC LIMIT 100",
            (inst["id"],),
        ).fetchall()
        return render("institution.html", request, inst=inst, members=members)

    @app.get("/countries", response_class=HTMLResponse)
    def countries_index(request: Request):
        return render("countries.html", request, rows=queries.top_countries(dbm.get_db(), 100))

    @app.get("/countries/{code}", response_class=HTMLResponse)
    def country_page(request: Request, code: str):
        db = dbm.get_db()
        c = queries.country(db, code.upper())
        if not c:
            raise HTTPException(404)
        top = queries.ranking_page(db, f"h_index__country={code.upper()}", limit=50)
        return render("country.html", request, c=c, top=top)

    @app.get("/search")
    def search(request: Request, q: str = "", format: str = "html"):
        db = dbm.get_db()
        res = queries.search_researchers(db, q, 30)
        if format == "json":
            return JSONResponse([
                {"id": r["id"], "name": r["name"], "institution": r["institution_name"],
                 "field": r["primary_field"], "h_index": r["h_index"],
                 "slug": slugm.researcher_slug(r["id"], r["name"])}
                for r in res
            ])
        return render("search.html", request, q=q, res=res)

    @app.get("/methodology", response_class=HTMLResponse)
    def methodology(request: Request):
        return render("methodology.html", request)

    # ---------- OGP images ----------
    @app.get("/og/researcher/{rid}.png")
    def og_researcher(rid: str):
        db = dbm.get_db()
        r = queries.researcher(db, rid)
        if not r:
            raise HTTPException(404)
        sub = " · ".join(x for x in [r["institution_name"] or "Unaffiliated",
                                     config.FIELD_NAMES.get(r["primary_field"], ""),
                                     r["country_code"]] if x)
        png = og.render_card(r["name"], sub, str(r["h_index"]), "h-index",
                             counts=r["counts_by_year"])
        return Response(png, media_type="image/png")

    @app.get("/og/ranking.png")
    def og_ranking(key: str):
        db = dbm.get_db()
        meta = queries.ranking_meta(db, key)
        if not meta:
            raise HTTPException(404)
        top = queries.ranking_page(db, key, limit=1)
        counts = top[0]["counts_by_year"] if top else None
        png = og.render_card(meta["title"], f"Top {meta['size']} · updated monthly",
                             "", "", counts=counts)
        return Response(png, media_type="image/png")

    # ---------- SEO plumbing ----------
    @app.get("/robots.txt", response_class=PlainTextResponse)
    def robots():
        return f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n"

    def _xml(body: str, root: str) -> PlainTextResponse:
        xml = (f'<?xml version="1.0" encoding="UTF-8"?>'
               f'<{root} xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</{root}>')
        return PlainTextResponse(xml, media_type="application/xml")

    @app.get("/sitemap.xml")
    def sitemap_index():
        db = dbm.get_db()
        n = db.execute("SELECT count(*) FROM researchers").fetchone()[0]
        shards = max(1, -(-n // SITEMAP_SHARD))
        body = f"<sitemap><loc>{SITE_URL}/sitemap-core.xml</loc></sitemap>"
        body += "".join(
            f"<sitemap><loc>{SITE_URL}/sitemap-researchers-{i}.xml</loc></sitemap>"
            for i in range(shards))
        return _xml(body, "sitemapindex")

    @app.get("/sitemap-core.xml")
    def sitemap_core():
        db = dbm.get_db()
        urls = ["/", "/rankings", "/institutions", "/countries", "/methodology"]
        urls += [ranking_url(row["ranking_key"]) for row in queries.list_rankings(db)]
        urls += [f"/countries/{r['code']}" for r in db.execute("SELECT code FROM countries")]
        body = "".join(f"<url><loc>{SITE_URL}{u}</loc></url>" for u in urls)
        return _xml(body, "urlset")

    @app.get("/sitemap-researchers-{shard}.xml")
    def sitemap_researchers(shard: int):
        db = dbm.get_db()
        # ETL は毎回新規 DB に INSERT のみ → rowid は 1..N の密な連番。範囲で O(件数) 取得。
        rows = db.execute(
            "SELECT id, name FROM researchers WHERE rowid > ? AND rowid <= ? ORDER BY rowid",
            (shard * SITEMAP_SHARD, (shard + 1) * SITEMAP_SHARD)).fetchall()
        if not rows:
            raise HTTPException(404)
        body = "".join(
            f"<url><loc>{SITE_URL}/researcher/{slugm.researcher_slug(r['id'], r['name'])}</loc></url>"
            for r in rows)
        return _xml(body, "urlset")

    return app


app = create_app()
