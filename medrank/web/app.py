from pathlib import Path

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from medrank import config
from medrank.web import db as dbm, queries, slug as slugm
from medrank.web.sparkline import sparkline

BASE = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE / "templates"))
templates.env.filters["sparkline"] = sparkline
templates.env.globals["slug"] = slugm

# URL(ハイフン)-> 内部 metric key(アンダースコア)
METRIC_SLUGS = {
    "h-index": "h_index", "citations": "citations", "publications": "works",
    "rising-stars": "rising", "consistency": "consistency", "young-guns": "young_guns",
}
SITE_URL = "https://researchers.med-ai.tech"


def create_app() -> FastAPI:
    app = FastAPI(title="MedRank")
    app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")

    def render(name, request, **ctx):
        ctx.setdefault("site_url", SITE_URL)
        return templates.TemplateResponse(request, name, ctx)

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request):
        db = dbm.get_db()
        feats = {
            "h_index__global": queries.ranking_page(db, "h_index__global", limit=10),
            "rising__global": queries.ranking_page(db, "rising__global", limit=10),
            "consistency__global": queries.ranking_page(db, "consistency__global", limit=10),
        }
        meta = {k: queries.ranking_meta(db, k) for k in feats}
        stats = {r["key"]: r["value"] for r in db.execute("SELECT key,value FROM meta")}
        return render("home.html", request, feats=feats, meta=meta,
                      countries=queries.top_countries(db, 12), stats=stats)

    @app.get("/rankings", response_class=HTMLResponse)
    def rankings_index(request: Request):
        db = dbm.get_db()
        return render("rankings_index.html", request, groups={
            "classic": queries.list_rankings(db, "classic"),
            "trend": queries.list_rankings(db, "trend"),
            "story": queries.list_rankings(db, "story"),
        })

    def _ranking_or_404(request, key):
        db = dbm.get_db()
        meta = queries.ranking_meta(db, key)
        if not meta:
            raise HTTPException(404)
        rows = queries.ranking_page(db, key, limit=100)
        return render("ranking.html", request, meta=meta, rows=rows)

    @app.get("/rankings/{metric}", response_class=HTMLResponse)
    def rank_global(request: Request, metric: str):
        m = METRIC_SLUGS.get(metric) or metric
        return _ranking_or_404(request, f"{m}__global")

    @app.get("/rankings/{metric}/{field}", response_class=HTMLResponse)
    def rank_field(request: Request, metric: str, field: str):
        m = METRIC_SLUGS.get(metric) or metric
        return _ranking_or_404(request, f"{m}__field={field}")

    @app.get("/rankings/{metric}/{field}/{country}", response_class=HTMLResponse)
    def rank_field_country(request: Request, metric: str, field: str, country: str):
        m = METRIC_SLUGS.get(metric) or metric
        key = f"{m}__country={country.upper()}" if field == "all" else f"{m}__field={field}"
        return _ranking_or_404(request, key)

    @app.get("/researcher/{slug}", response_class=HTMLResponse)
    def researcher_page(request: Request, slug: str):
        db = dbm.get_db()
        r = queries.researcher(db, slugm.id_from_slug(slug))
        if not r:
            raise HTTPException(404)
        return render("researcher.html", request, r=r,
                      appears=queries.researcher_rankings(db, r["id"]))

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

    @app.get("/robots.txt", response_class=PlainTextResponse)
    def robots():
        return f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n"

    @app.get("/sitemap.xml")
    def sitemap():
        db = dbm.get_db()
        urls = ["/", "/rankings", "/institutions", "/countries", "/methodology"]
        urls += [f"/rankings/{m}" for m in METRIC_SLUGS]
        for row in queries.list_rankings(db):
            k = row["ranking_key"]
            metric_url = k.split("__")[0].replace("_", "-")
            if "__field=" in k:
                urls.append(f"/rankings/{metric_url}/{k.split('=')[1]}")
            elif "__country=" in k:
                urls.append(f"/rankings/{metric_url}/all/{k.split('=')[1]}")
        body = "".join(f"<url><loc>{SITE_URL}{u}</loc></url>" for u in urls)
        xml = ('<?xml version="1.0" encoding="UTF-8"?>'
               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
               f'{body}</urlset>')
        return PlainTextResponse(xml, media_type="application/xml")

    return app


app = create_app()
