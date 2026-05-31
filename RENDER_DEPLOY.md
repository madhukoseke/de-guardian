# Render deployment

[`render.yaml`](./render.yaml) provisions three services:

| Service | Type | Name |
| --- | --- | --- |
| Pipeline API | Web Service | `bash-script-funeral` |
| Daily cron run | Cron Job | `daily-revenue-aggregation` |
| Run history | Postgres | `pipeline-runs-db` |

## Deploy

1. [dashboard.render.com](https://dashboard.render.com/) → **New +** → **Blueprint**
2. Connect GitHub → select **`madhukoseke/de-guardian`**
3. **Apply** and wait for all three services to deploy

## Environment variables

Set on **both** the web service and cron job:

| Key | Value |
| --- | --- |
| `SUPERPLANE_WEBHOOK_URL` | Webhook URL from the **Pipeline Failed** node |
| `SUPERPLANE_WEBHOOK_SECRET` | Signature key from **Reset Signature Key** on that node |
| `SERVICE_BASE_URL` | Public web URL, e.g. `https://bash-script-funeral.onrender.com` |

`DATABASE_URL` is linked automatically by the blueprint.

## Verify

```bash
BASE=https://bash-script-funeral.onrender.com

curl "$BASE/health"
curl "$BASE/"          # webhook_configured: true
curl -X POST "$BASE/break?mode=schema_drift"
curl -X POST "$BASE/run"   # incident_emitted: true
```

After approving in SuperPlane:

```bash
curl -X POST "$BASE/run"                    # should succeed
curl "$BASE/runs?limit=5"
curl "$BASE/memory?mode=schema_drift"        # track record grows as incidents recover
```

## Troubleshooting

| Issue | Fix |
| --- | --- |
| Webhook 401/403 | Re-copy `SUPERPLANE_WEBHOOK_SECRET`; redeploy both services |
| Canvas heal fails | `SERVICE_BASE_URL` must match the public web URL |
| Cold start | Free tier may take ~30s; warm up with `/health` first |
