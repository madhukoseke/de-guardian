# SuperPlane setup

Reference app: [app_preview-env-digitalocean](https://github.com/superplanehq/app_preview-env-digitalocean)

## Import (recommended)

```bash
superplane connect https://app.superplane.com <API_TOKEN>
./scripts/import-app.sh
```

1. Replace `REPLACE_CLAUDE_INTEGRATION_ID` in `canvas.yaml` with your Claude integration UUID.
2. Publish the canvas and copy the **Pipeline Failed** webhook URL → `SUPERPLANE_WEBHOOK_URL` on Render (web + cron).
3. Set `REPLACE_CANVAS_ID` in `console.yaml` and attach the console in the UI.

## Manual UI build

If YAML import fails, create a canvas named **DE-Guardian: Schema Drift Recovery** with this flow:

```
Webhook → Claude (text prompt) → Approval → HTTP POST heal → upsertMemory
                              └→ (rejected) → upsertMemory
```

Use the node configuration from [`canvas.yaml`](./canvas.yaml). The webhook payload shape is defined in [`app/events.py`](./app/events.py).

Test without a webhook using **Manual Run** and [`fixtures/schema_drift_incident.json`](./fixtures/schema_drift_incident.json).

## Troubleshooting

| Issue | Fix |
| --- | --- |
| Webhook not firing | Check `SUPERPLANE_WEBHOOK_URL` and `SUPERPLANE_WEBHOOK_SECRET` on Render |
| Heal step fails | Set `SERVICE_BASE_URL` to your public web URL (https, no trailing slash) |
| Claude slow | Pre-run once before demo; keep a screenshot of the last RCA |
