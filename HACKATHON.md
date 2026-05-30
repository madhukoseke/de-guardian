# Bash Script Funeral /w Render — Hackathon Instructions

Source: [AleksandarCole gist](https://gist.github.com/AleksandarCole/f13c68cb9e91594cb7dbdb4cd5218be7) · Discord: [#hackaton-supersf-0526](https://discord.com/channels/1409914582239023200/1510264754130915420)

## Overview

Build on **SuperPlane** — workflows, automations, integrations, or tooling for platform engineering.

Choose one of two tracks below.

---

## Track 1: Build a SuperPlane App (Recommended)

Build a working SuperPlane App: **Canvas** + **Console** on [app.superplane.com](https://app.superplane.com).

### Setup

1. Register at [app.superplane.com](https://app.superplane.com)
2. Create an organization: `hackatonsf-<team-name>`
3. Connect integrations your canvas needs (for DE-Guardian: **Claude**; optional **Slack**)
4. Reference app: [superplanehq/app_preview-env-digitalocean](https://github.com/superplanehq/app_preview-env-digitalocean)

### Submission

- **Live demo** of your working app
- **GitHub repository** with:
  - `canvas.yaml`
  - `console.yaml`
  - README with **Launch in SuperPlane** import button

**This repo (DE-Guardian)** ships all three. After import, replace `REPLACE_*` placeholders in `canvas.yaml` with your integration IDs from Settings → Integrations.

---

## Track 2: Extend SuperPlane

Local dev instance + PR to [superplanehq/superplane](https://github.com/superplanehq/superplane).

---

## Render Partner Track

Use at least **two Render Services**. DE-Guardian uses **Web + Cron + Postgres** via `render.yaml`.

Register: [Render](https://dashboard.render.com/register?utm_source=supersf01&utm_medium=events) ($50 credits for participants).

---

## Prizes

| Main | Amount |
| --- | --- |
| 1st | $1,600 |
| 2nd | $750 |
| 3rd | $500 |
| Best Use of AI Agents | $250 |

| Render track | Credits |
| --- | --- |
| 1st | $500 |
| 2nd | $300 |
| 3rd | $100 |

---

## DE-Guardian quick path

1. Import canvas + console (README badge)
2. Connect **Claude** integration → paste ID into `canvas.yaml`
3. Copy Webhook URL → `SUPERPLANE_WEBHOOK_URL` on Render
4. Deploy Render blueprint → set `SERVICE_BASE_URL`
5. Demo: `schema_drift` → SuperPlane RCA → approve → heal

See [`CANVAS_SETUP.md`](./CANVAS_SETUP.md) and [`DEMO_SCRIPT.md`](./DEMO_SCRIPT.md).
