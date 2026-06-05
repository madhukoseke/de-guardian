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
| `API_KEY` | Shared secret — canvas HTTP nodes send `Authorization: Bearer <key>` |
| `SUPERPLANE_WEBHOOK_URL` | Webhook URL from the **Pipeline Failed** node (after publish) |
| `SUPERPLANE_WEBHOOK_SECRET` | Signature key from **Reset Signature Key** on that node |
| `SERVICE_BASE_URL` | Public web URL, e.g. `https://bash-script-funeral.onrender.com` |

`DATABASE_URL` is linked automatically by the blueprint. Render sets `ENV=production` behavior via the `RENDER` env var.

## Verify

```bash
BASE=https://bash-script-funeral.onrender.com
KEY=your-api-key

curl "$BASE/health"                                    # database: ok
curl -H "Authorization: Bearer $KEY" -X POST "$BASE/break?mode=schema_drift"
curl -H "Authorization: Bearer $KEY" -X POST "$BASE/run"   # incident_emitted: true
curl "$BASE/incidents"                                 # synced from canvas after remediate
```

After approving in SuperPlane:

```bash
curl -H "Authorization: Bearer $KEY" -X POST "$BASE/run"     # should succeed
curl "$BASE/runs?limit=5"
curl "$BASE/memory?mode=schema_drift"
```

## Troubleshooting

| Issue | Fix |
| --- | --- |
| Startup crash | `API_KEY` required on Render; set before first deploy |
| Webhook 401/403 | Re-copy `SUPERPLANE_WEBHOOK_SECRET`; redeploy both services |
| Heal 401 | `API_KEY` must match canvas `REPLACE_DE_GUARDIAN_API_KEY` |
| Canvas heal fails | `SERVICE_BASE_URL` must match the public web URL |
| Cold start | Free tier may take ~30s; canvas HTTP nodes retry 3× |
