# Canvas Spec — DE-Guardian: Schema Drift Recovery

This is the SuperPlane Canvas you build on the day. The demo service in this
repo emits a `pipeline.failed` event; this Canvas catches it, has the Claude
component investigate, gates remediation behind a human approval, then heals
the pipeline and logs the whole thing.

> Build the graph left-to-right. Get **Trigger -> Claude -> Notify** working
> end-to-end *first* (one green run), then add the approval gate and the
> remediation call. Don't build the whole graph before testing it.

---

## The graph

```
[1 Webhook Trigger]  ->  [2 Claude: Investigate]  ->  [3 Approval Gate]  ->  [4 Heal (HTTP/Render)]  ->  [5 Notify (Slack)]
   pipeline.failed          root-cause RCA              human sign-off         POST /heal                post RCA + outcome
                                                              |
                                                       (reject) -> [5 Notify: "left broken, paging on-call"]
```

Every node's run is captured in SuperPlane's execution history — that queryable
audit trail IS the "safe agents near prod" story. Show it on stage.

---

## Node 1 — Webhook Trigger

- Add a **Webhook** trigger node. Copy its URL.
- Set it as `SUPERPLANE_WEBHOOK_URL` on the Render web service + cron job.
- Incoming payload shape (from `app/events.py`):

```json
{
  "event": "pipeline.failed",
  "severity": "P2",
  "job_name": "daily_revenue_aggregation",
  "run_id": "run_xxxxxxxx",
  "failed_at": "2026-05-30T06:00:01Z",
  "error": {
    "type": "SchemaDrift",
    "message": "KeyError: 'amount' — field missing from source payload (found 'txn_amount')",
    "failure_mode": "schema_drift",
    "offending_record": { "transaction_id": "…", "merchant": "…", "txn_amount": 20.47 },
    "traceback": "…"
  },
  "context": {
    "last_success_at": "2026-05-29T06:00:00Z",
    "recent_changes": [
      { "sha": "a3f91c2", "author": "data-platform-bot", "when": "2h ago",
        "message": "feat(ingest): bump source-api client to v3 (response schema changed)" }
    ],
    "heal_endpoint": "/heal"
  }
}
```

## Node 2 — Claude: Investigate (this is your "Best Use of AI Agents" play)

Add the **Claude** component. Feed it the trigger payload. System/instruction
prompt to paste:

```
You are an on-call data-platform incident investigator. A pipeline run just
failed. Using ONLY the evidence in the event, produce a root-cause analysis.

Event:
{{ root().data.body }}

Return STRICT JSON, no prose, with this shape:
{
  "root_cause": "<one-sentence plain-English cause>",
  "evidence": ["<the specific fields/log lines that prove it>"],
  "blast_radius": "<what downstream is affected, e.g. revenue dashboards stale>",
  "correlated_change": "<the recent_changes entry most likely responsible, or null>",
  "recommended_remediation": "<the single safest next action>",
  "remediation_is_safe_to_automate": true,
  "confidence": "<low|medium|high>",
  "runbook": ["<step>", "<step>"]
}

Rules: tie the failure to a specific recent change when one fits (e.g. a schema
change shipped 2h ago explains a missing-field error). Be conservative:
set remediation_is_safe_to_automate=false for anything destructive or ambiguous.
```

> The magic moment: for `schema_drift`, the agent correlates the error to the
> "bump source-api client to v3" commit from 2h ago — a human-quality RCA in
> seconds. That's the demo screenshot you want.

## Node 3 — Approval Gate

- Add a **human approval / manual-approval** node after Claude.
- Show Claude's RCA in the approval message so the human approves *with context*.
- This is the SuperPlane thesis made literal: an agent investigates, a human
  decides, nothing touches prod without sign-off.

## Node 4 — Heal (remediation)

On approval, call the demo service's heal endpoint. Two equally good ways:

- **Render component**: trigger a redeploy/rollback of the `bash-script-funeral`
  service (great for the Render track narrative), **or**
- **HTTP request component**: `POST {{ trigger.body.context.heal_url }}`
  (full URL is set via `SERVICE_BASE_URL` on Render, e.g. `https://bash-script-funeral.onrender.com/heal`)

Then re-run to prove green: `POST .../run`.

## Node 5 — Notify

- **Slack** (or Discord) component. Post the RCA + the action taken + a link
  back to the SuperPlane run.

### Reject path (required for full workflow)

Wire **Approval → rejected** to a second Notify node (or a Filter + Notify branch):

```
[3 Approval] --approved--> [4 Heal HTTP] --> [5 Notify: healed]
            --rejected--> [5b Notify: "left broken, paging on-call"]
```

Reject message template:

```
DE-Guardian: remediation rejected for {{ trigger.body.run_id }}.
Root cause (unresolved): {{ Claude.root_cause }}
Pipeline remains in failure mode. Paging on-call.
```

---

## How this maps to the judging criteria

| Criterion | How this scores |
| --- | --- |
| Real-world usefulness | A real fintech failure pattern (schema drift / null violation) you've lived at scale. |
| Technical implementation | A genuine multi-node Canvas with triggers, an agent, an approval gate, remediation, and audit history — not a toy. |
| Use of AI / agents | Claude does autonomous root-cause correlation against recent changes → targets the **$250 Best Use of AI Agents** prize. |
| Creativity | The literal "funeral" framing: pick one named bash script, bury it on stage. |
| Demo quality | Break it live → agent investigates → approve → self-heals. A story, not a feature tour. |
| Render track | Web service + Cron job + Postgres (see `render.yaml`) → 3 services, only 2 required. |

## 3-minute demo run-of-show

1. **(15s)** "This is `daily_revenue_aggregation`. It's woken me up at 2am. Today it dies." Show `/status`.
2. **(20s)** `POST /break?mode=schema_drift`, then `POST /run` → it fails. Show the error.
3. **(60s)** Flip to SuperPlane: the Canvas already fired. Walk the graph: trigger → Claude's RCA (it fingered the 2h-old schema commit) → the approval card.
4. **(30s)** Approve → Node 4 heals → `POST /run` → green.
5. **(25s)** Show the run-history audit trail. "Agent investigated, human approved, every step logged — that's how you put an agent near prod safely."
6. **(15s)** "One script buried. DE-Guardian is the first workflow for OneAISpace." Name Render services (web + cron + postgres).
