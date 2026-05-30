# DE-Guardian — 3-minute demo script

Print [`run-of-show-card.html`](run-of-show-card.html) or use this outline.

## Before stage

- [ ] Render `/health` returns ok
- [ ] `SUPERPLANE_WEBHOOK_URL` and `SERVICE_BASE_URL` set on Render
- [ ] SuperPlane Canvas published; one successful test run
- [ ] Tabs: Terminal, Render `/status`, SuperPlane Canvas, `/runs`
- [ ] `the-corpse.sh` ready in terminal
- [ ] Backup: screenshot of Claude RCA + 30s screen recording

## Script (180 seconds)

| Time | Action | Say |
| --- | --- | --- |
| 0:00 | Scroll `the-corpse.sh` EULOGY | "This is the bash script that ran our revenue pipeline. No audit trail. No guardrails. Today we bury it." |
| 0:15 | `curl $BASE/status` | "`daily_revenue_aggregation` — healthy. For now." |
| 0:35 | `POST /break?mode=schema_drift` + `POST /run` | "Upstream shipped source-api v3. Field `amount` is gone. Pipeline fails." |
| 0:55 | SuperPlane Canvas | "DE-Guardian caught `pipeline.failed`. Watch the agent investigate." |
| 1:15 | Point at Claude node output | "It correlated the KeyError to the schema commit from 2 hours ago — not generic AI fluff." |
| 1:35 | Approval card | "Agent proposes remediation. Human approves. Nothing touches prod without sign-off." |
| 1:50 | Approve → heal runs | "Approved. Canvas calls `/heal`." |
| 2:05 | `POST /run` → success | "Green run. Pipeline restored." |
| 2:20 | SuperPlane run history + `GET /runs` | "Every step logged — investigation, approval, remediation. That's DE-Guardian." |
| 2:45 | Close | "Built on SuperPlane and Render. First workflow in the OneAISpace vision — clone it, fork it, improve it." |

## Curl cheat sheet

```bash
export BASE=https://bash-script-funeral.onrender.com
./scripts/demo.sh "$BASE"
```

## If live demo fails

1. Show backup screenshot of Claude RCA
2. Manual Run in SuperPlane with [`fixtures/schema_drift_incident.json`](fixtures/schema_drift_incident.json)
3. `curl -X POST $BASE/heal` manually, then green `/run`

## Judge Q&A prep

**Why not just use Airflow alerts?**  
Airflow tells you *that* a task failed. DE-Guardian investigates *why*, correlates recent changes, gates remediation, and logs the full chain across tools.

**How is this different from a chatbot?**  
It's an auditable workflow graph — trigger, agent, approval, action — not a chat session.

**Production ready?**  
Hackathon MVP with simulated pipeline; pattern maps to real webhook sources (Airflow, Dagster, dbt Cloud).
