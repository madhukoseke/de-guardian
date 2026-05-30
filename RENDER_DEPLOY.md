# Render deployment checklist

## 1. Push to GitHub

```bash
cd /Users/madhukoseke/Documents/Projects/superplane_hakathon_sfo
git init
git add .
git commit -m "DE-Guardian: pipeline incident demo for SuperPlane hackathon"
gh repo create de-guardian --public --source=. --push
```

Or create the repo manually on GitHub, then:

```bash
git remote add origin git@github.com:YOUR_USER/de-guardian.git
git push -u origin main
```

## 2. Deploy blueprint

1. [Render Dashboard](https://dashboard.render.com/) → **New +** → **Blueprint**
2. Connect the GitHub repo
3. Wait for: `bash-script-funeral` (web), `daily-revenue-aggregation` (cron), `pipeline-runs-db` (postgres)

## 3. Environment variables

Set on **bash-script-funeral** (web) and **daily-revenue-aggregation** (cron):

| Key | Value |
| --- | --- |
| `SUPERPLANE_WEBHOOK_URL` | From SuperPlane Canvas Webhook node (after Phase A in CANVAS_SETUP.md) |
| `SERVICE_BASE_URL` | `https://bash-script-funeral.onrender.com` (your actual web URL) |

`DATABASE_URL` is linked automatically by the blueprint.

## 4. Verify

```bash
curl https://YOUR-SERVICE.onrender.com/health
curl https://YOUR-SERVICE.onrender.com/status
```

## 5. Demo break (production)

```bash
BASE=https://YOUR-SERVICE.onrender.com
curl -X POST "$BASE/break?mode=schema_drift"
curl -X POST "$BASE/run"
```

Check SuperPlane for the new run.
