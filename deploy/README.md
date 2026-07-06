# MedRank deployment

Live URL: **https://researchers.med-ai.tech** · local port **8110**

## One-time setup (requires sudo — run these yourself)

DNS is already routed (`cloudflared tunnel route dns medai-digest researchers.med-ai.tech`).
Three steps remain, all needing root:

### 1. Add the tunnel ingress rule

Edit `/etc/cloudflared/config.yml` and insert this block **before** the final
`- service: http_status:404` line (i.e. right after the `funds.med-ai.tech` block):

```yaml
  - hostname: researchers.med-ai.tech
    service: http://127.0.0.1:8110
```

Then restart the tunnel:

```bash
sudo systemctl restart cloudflared
```

### 2. Install and start the web service

```bash
sudo cp /srv/apps/researchers/deploy/medrank-web.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now medrank-web
curl -s localhost:8110/ | head -c 100     # sanity check
```

### 3. Schedule the monthly ETL (as user d-ueda, no sudo)

```bash
crontab -e
# add:
17 4 1 * * /srv/apps/researchers/deploy/medrank-etl.sh >> /srv/apps/researchers/data/etl.log 2>&1
```

## How it runs

- **Web**: `uvicorn medrank.web.app:app` on `127.0.0.1:8110`, 2 workers, read-only SQLite.
- **Data**: `data/researchers.db`, rebuilt monthly by `deploy/medrank-etl.sh`
  (sync OpenAlex snapshot → rebuild → atomic swap). The web app opens a fresh
  read-only connection per request, so the swap needs no restart.
- **Snapshot**: `data/snapshot/` (~53 GB, git-ignored). `aws s3 sync` only pulls
  changed partitions on later runs.
