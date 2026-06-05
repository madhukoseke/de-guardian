#!/usr/bin/env bash
# Idempotent SuperPlane import: update canvas if CANVAS_NAME exists, else create.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

CANVAS_NAME="${CANVAS_NAME:-DE-Guardian: Schema Drift Recovery}"

if ! command -v superplane >/dev/null 2>&1; then
  echo "Install CLI: https://docs.superplane.com/installation/cli"
  exit 1
fi

superplane whoami || {
  echo "Run: superplane connect https://app.superplane.com <API_TOKEN>"
  exit 1
}

for token in REPLACE_CLAUDE_INTEGRATION_ID REPLACE_SLACK_INTEGRATION_ID REPLACE_DE_GUARDIAN_API_KEY REPLACE_SLACK_CHANNEL_ID REPLACE_ONCALL_GROUP_ID; do
  if grep -q "$token" canvas.yaml; then
    echo "WARNING: Replace $token in canvas.yaml before production use"
  fi
done

if superplane canvases get "$CANVAS_NAME" >/dev/null 2>&1; then
  echo "Updating existing canvas: $CANVAS_NAME"
  superplane canvases update -f canvas.yaml --auto-layout horizontal
else
  echo "Creating canvas: $CANVAS_NAME"
  superplane canvases create --file canvas.yaml
fi

echo ""
echo "Next:"
echo "  1. Publish canvas in UI"
echo "  2. Copy Webhook URL → SUPERPLANE_WEBHOOK_URL on Render (web + cron)"
echo "  3. Set API_KEY on Render (same value as REPLACE_DE_GUARDIAN_API_KEY in canvas HTTP nodes)"
echo "  4. Connect Slack integration; set REPLACE_SLACK_INTEGRATION_ID and REPLACE_SLACK_CHANNEL_ID"
echo "  5. Update REPLACE_CANVAS_ID in console.yaml and attach console in UI"
echo "  6. Optional: set SLACK_WEBHOOK_URL on Render for direct service-side alerts"
echo "  7. Smoke test: curl -H \"Authorization: Bearer \$API_KEY\" \$SERVICE_BASE_URL/health"
