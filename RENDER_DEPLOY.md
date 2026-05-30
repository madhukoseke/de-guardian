# Render deployment checklist

This repo ships a **Blueprint** (`render.yaml`) that creates all three services in one shot:

| Service | Type | Name |
| --- | --- | --- |
| Pipeline API | Web Service | `bash-script-funeral` |
| Daily cron run | Cron Job | `daily-revenue-aggregation` |
| Run history | Postgres | `pipeline-runs-db` |

---

## Step 1 — Push latest code to GitHub

```bash
cd /Users/madhukoseke/Documents/Projects/superplane_hakathon_sfo
git add .
git commit -m "Add HMAC webhook signing for SuperPlane"
git push origin main
```

Repo: https://github.com/madhukoseke/de-guardian

---

## Step 2 — Deploy the Blueprint (not a single Web Service)

On the Render screen you have open:

1. Click **← Back** or go to [dashboard.render.com](https://dashboard.render.com/)
2. Click **New +** → **Blueprint** (not "Web Services")
3. Connect GitHub → select **`madhukoseke/de-guardian`**
4. Render reads `render.yaml` and shows 3 resources to create
5. Click **Apply** / **Deploy Blueprint**
6. Wait ~5–10 min for all three to go green

> If you already created a standalone Web Service by mistake, delete it and use Blueprint instead — otherwise you duplicate work and miss Postgres + Cron.

---

## Step 3 — Copy your SuperPlane webhook credentials

From the **Pipeline Failed** node in SuperPlane:

1. **Webhook URL** — already published, e.g.  
   `https://app.superplane.com/api/v1/webhooks/4eef493c-42ca-4a71-b543-c7239cc6f66f`
2. **Signature key** — click **Reset Signature Key**, copy the value immediately (shown once)

---

## Step 4 — Set environment variables

Set these on **both** `bash-script-funeral` (web) **and** `daily-revenue-aggregation` (cron):

| Key | Value |
| --- | --- |
| `SUPERPLANE_WEBHOOK_URL` | Your webhook URL from Step 3 |
| `SUPERPLANE_WEBHOOK_SECRET` | Signature key from **Reset Signature Key** |
| `SERVICE_BASE_URL` | `https://bash-script-funeral.onrender.com` (use your actual web URL, no trailing slash) |

`DATABASE_URL` is linked automatically by the blueprint — do not set it manually.

In Render: open each service → **Environment** → **Add Environment Variable** → **Save Changes** (triggers redeploy).

---

## Step 5 — Verify

Replace `BASE` with your web service URL:

```bash
BASE=https://bash-script-funeral.onrender.com

curl "$BASE/health"
# {"ok":true}

curl "$BASE/"
# webhook_configured: true, webhook_signature_configured: true

curl "$BASE/status"
```

---

## Step 6 — End-to-end test (fires SuperPlane)

```bash
BASE=https://bash-script-funeral.onrender.com

curl -X POST "$BASE/break?mode=schema_drift"
curl -X POST "$BASE/run"
```

- `/run` response should include `"sent": true` under the incident block
- SuperPlane Canvas should show a new run on **Pipeline Failed**

Then in SuperPlane: approve → heal → verify green:

```bash
curl -X POST "$BASE/run"
curl "$BASE/runs?limit=5"
```

---

## Troubleshooting

| Issue | Fix |
| --- | --- |
| Webhook returns 401/403 | Re-copy `SUPERPLANE_WEBHOOK_SECRET` after Reset Signature Key; redeploy both services |
| `webhook_configured: false` | Set `SUPERPLANE_WEBHOOK_URL` on the web service |
| Canvas heal step fails | Set `SERVICE_BASE_URL` to the public web URL (https, no slash) |
| Cron doesn't support free tier | Blueprint uses `plan: starter` (~$1/mo minimum for cron) |
| First request slow | Free tier cold-starts ~30s; hit `/health` before demo |

---

## Render partner track checklist

- [x] Web Service (`bash-script-funeral`)
- [x] Cron Job (`daily-revenue-aggregation`)
- [x] Postgres (`pipeline-runs-db`)
- [ ] Env vars set on web + cron
- [ ] SuperPlane webhook fires on failed run
