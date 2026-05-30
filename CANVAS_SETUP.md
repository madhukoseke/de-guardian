# DE-Guardian — SuperPlane Canvas Setup (event day)

Build on the **event-hosted** SuperPlane instance. Get URL + API token at check-in.

## Phase A — MVP (first green run)

### 1. Create canvas

Name: **DE-Guardian: Schema Drift Recovery**

### 2. Node 1 — Webhook trigger

- Add **Webhook** trigger
- Copy URL → set `SUPERPLANE_WEBHOOK_URL` on Render (web + cron)
- Set `SERVICE_BASE_URL` to your Render web URL (no trailing slash)

Test locally without webhook:

```bash
curl -X POST "http://localhost:8000/break?mode=schema_drift"
curl -X POST http://localhost:8000/run
# incident JSON is in the response under "incident"
```

Or use **Manual Run** with payload from [`fixtures/schema_drift_incident.json`](fixtures/schema_drift_incident.json).

### 3. Node 2 — Claude investigate

Add **Claude** (Text Prompt) component. Connect Webhook → Claude.

Paste the system prompt from [`canvas-spec.md`](canvas-spec.md) (Node 2 section). Map the webhook body into the prompt as `{{ trigger.body }}` or the equivalent expression for your SuperPlane version.

Expected output: JSON with `root_cause`, `evidence`, `blast_radius`, `correlated_change`, `recommended_remediation`, `remediation_is_safe_to_automate`, `confidence`, `runbook`.

### 4. Node 5 (stub) — Notify

Connect Claude → **HTTP Request** or **Slack**.

- Slack: post `root_cause` + link to SuperPlane run
- HTTP: POST to a webhook.site URL for demo if Slack unavailable

**Checkpoint:** Trigger fires → Claude returns RCA mentioning the v3 schema commit.

---

## Phase B — Full workflow

### 5. Node 3 — Approval

Insert **Approval** between Claude and remediation.

Approval message template:

```
DE-Guardian RCA
---
Root cause: {{ Claude output root_cause }}
Confidence: {{ confidence }}
Recommended: {{ recommended_remediation }}
Safe to automate: {{ remediation_is_safe_to_automate }}
```

### 6. Node 4 — Heal (on approve)

**HTTP Request** component:

- Method: `POST`
- URL: `{{ trigger.body.context.heal_url }}`
- Body: empty or `{}`

On Render, `heal_url` is set via `SERVICE_BASE_URL` env var.

### 7. Reject path

Approval **rejected** → Notify node:

```
DE-Guardian: remediation rejected — pipeline left broken, paging on-call.
Run: {{ run_id }}
```

### 8. Publish canvas

Publish draft before demo. Confirm run history shows full chain.

---

## Live demo sequence

```bash
export BASE=https://YOUR-SERVICE.onrender.com
curl "$BASE/status"
curl -X POST "$BASE/break?mode=schema_drift"
curl -X POST "$BASE/run"    # triggers SuperPlane
# In SuperPlane: approve → heal
curl -X POST "$BASE/run"    # should succeed
curl "$BASE/runs?limit=5"
```

---

## Troubleshooting

| Issue | Fix |
| --- | --- |
| Webhook not firing | Check `SUPERPLANE_WEBHOOK_URL`; use Manual Run + fixture JSON |
| Claude slow | Pre-run before stage; screenshot last RCA |
| Heal 404 | Set `SERVICE_BASE_URL` on Render to public web URL |
| Render track | Blueprint already has Web + Cron + Postgres |

---

## API keys checklist

- [ ] Anthropic / Claude (SuperPlane integration)
- [ ] SuperPlane API token (CLI: `superplane connect <url> <token>`)
- [ ] Slack bot token (optional)
- [ ] Render dashboard access + participant credits
