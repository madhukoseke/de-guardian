# SuperPlane setup

Reference app: [app_preview-env-digitalocean](https://github.com/superplanehq/app_preview-env-digitalocean)

## Import (recommended)

```bash
superplane connect https://app.superplane.com <API_TOKEN>
./scripts/import-app.sh
```

1. Replace placeholders in `canvas.yaml`:
   - `REPLACE_CLAUDE_INTEGRATION_ID`
   - `REPLACE_SLACK_INTEGRATION_ID` and `REPLACE_SLACK_CHANNEL_ID` (Slack alerts)
   - `REPLACE_DE_GUARDIAN_API_KEY` (must match Render `API_KEY`)
   - `REPLACE_ONCALL_GROUP_ID` (approval + email paging)
2. Publish the canvas and copy the **Pipeline Failed** webhook URL → `SUPERPLANE_WEBHOOK_URL` on Render (web + cron).
3. Set `REPLACE_CANVAS_ID` in `console.yaml` and attach the console in the UI.

## Slack integration

Two layers — use either or both:

| Layer | Config | When it fires |
| --- | --- | --- |
| **Service** (this repo) | `SLACK_WEBHOOK_URL` on Render | Immediately after SuperPlane webhook succeeds on `/run` |
| **Canvas** (`canvas.yaml`) | Slack integration + `REPLACE_SLACK_CHANNEL_ID` | Incident alert, rejection page, verified remediation |

### Canvas setup

1. In SuperPlane → **Integrations** → add **Slack** (OAuth; needs `chat:write`).
2. Copy the integration ID → `REPLACE_SLACK_INTEGRATION_ID` in `canvas.yaml`.
3. Pick a channel ID (e.g. `#de-guardian-alerts`) → `REPLACE_SLACK_CHANNEL_ID`.
4. Re-import: `./scripts/import-app.sh`

Canvas Slack nodes:

- **Slack: Incident Alert** — fires on every `pipeline.failed` webhook
- **Slack: Page On-call** — fires when approval is rejected
- **Slack: Remediated** — fires after verify + sync succeeds

### Service-side webhook (optional)

1. Create a Slack app with **Incoming Webhooks** enabled.
2. Add webhook to your alerts channel.
3. Set `SLACK_WEBHOOK_URL` on the Render web + cron services.

## Workflow

```
Webhook → P1? → Claude (always for P1)
         └→ Known failure? → Auto-heal eligible? → Heal → Verify → Save
                              └→ Claude → Approval → Heal → Verify → Save
         Rejected → Save + Page on-call (email + Slack)
```

Production canvas adds: HTTP retries, verify-after-heal, heal-failure branch, sync to `POST /incidents/status`, and heal-then-run console Re-run.

## Manual Run fixtures

| Fixture | Use |
| --- | --- |
| [`fixtures/schema_drift_incident.json`](./fixtures/schema_drift_incident.json) | Known failure — memory fast path (`skip_claude: true`) |
| [`fixtures/schema_drift_incident_novel.json`](./fixtures/schema_drift_incident_novel.json) | Novel failure — Claude path |
| [`fixtures/schema_drift_incident_cloud.json`](./fixtures/schema_drift_incident_cloud.json) | Cloud Manual Run — replace URLs with your `SERVICE_BASE_URL` |

For SuperPlane cloud Manual Run, use the **cloud** fixture (not localhost URLs).

After **Heal Pipeline**, `root()` points at the HTTP response — not the original incident. Memory nodes must reference `$['Pipeline Failed'].data.body.*` for incident fields.

## Troubleshooting

| Issue | Fix |
| --- | --- |
| Webhook not firing | Check `SUPERPLANE_WEBHOOK_URL` and `SUPERPLANE_WEBHOOK_SECRET` on Render |
| Heal step 401 | Set `API_KEY` on Render; match `REPLACE_DE_GUARDIAN_API_KEY` in canvas HTTP nodes |
| Heal step fails | Set `SERVICE_BASE_URL` to your public web URL (https, no trailing slash) |
| Verify run fails | Armed mode may still be set — check `/status`; ensure heal succeeded first |
| Claude slow | Novel failures always hit Claude; known failures skip when `auto_remediation_success_rate >= 0.5` |
