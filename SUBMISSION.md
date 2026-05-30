# Hackathon submission — DE-Guardian

## Project

**DE-Guardian: Schema Drift Recovery** — AI incident response for data pipelines, built on SuperPlane + Render.

## Links

| Item | URL |
| --- | --- |
| GitHub | https://github.com/madhukoseke/de-guardian |
| Render web | `https://bash-script-funeral.onrender.com` (set after blueprint deploy) |
| SuperPlane Canvas | *Add canvas URL from event instance* |

## One-liner

Data pipeline incidents still rely on logs, bash scripts, and tribal knowledge. DE-Guardian detects failures, runs an AI investigation workflow with human approval, remediates safely, and logs every step — the first shareable workflow for OneAISpace.

## What we built

- **Simulated pipeline** (`daily_revenue_aggregation`) with 5 realistic failure modes
- **SuperPlane Canvas**: Webhook → Claude RCA → Approval → HTTP heal → Notify (+ reject path)
- **Render**: Web Service + Cron Job + Postgres (`render.yaml` blueprint)

## Demo scenario

`schema_drift` — upstream renamed `amount` → `txn_amount`. Claude correlates to the source-api v3 commit from `recent_changes`.

## Prizes targeted

| Track | Evidence |
| --- | --- |
| Main | Live demo, DataOps realism, multi-node workflow |
| Best Use of AI Agents | Claude autonomous RCA with evidence + confidence |
| Render | 3 services in blueprint (2+ required) |

## Team

Solo / *update at event*

## Setup docs

- [`CANVAS_SETUP.md`](CANVAS_SETUP.md) — SuperPlane build steps
- [`RENDER_DEPLOY.md`](RENDER_DEPLOY.md) — Render blueprint
- [`canvas-spec.md`](canvas-spec.md) — Node graph + Claude prompt
- [`scripts/demo.sh`](scripts/demo.sh) — Live demo curls
