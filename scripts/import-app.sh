#!/usr/bin/env bash
# Import DE-Guardian Canvas + remind about placeholders.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! command -v superplane >/dev/null 2>&1; then
  echo "Install CLI: https://docs.superplane.com/installation/cli"
  exit 1
fi

superplane whoami || {
  echo "Run: superplane connect https://app.superplane.com <API_TOKEN>"
  exit 1
}

if grep -q 'REPLACE_CLAUDE_INTEGRATION_ID' canvas.yaml; then
  echo "WARNING: Set REPLACE_CLAUDE_INTEGRATION_ID in canvas.yaml (Settings → Integrations → Claude)"
  echo "  superplane integrations list"
fi

superplane canvases create --file canvas.yaml
echo ""
echo "Next:"
echo "  1. Publish canvas in UI"
echo "  2. Copy Webhook URL → SUPERPLANE_WEBHOOK_URL on Render"
echo "  3. Update REPLACE_CANVAS_ID in console.yaml and attach console in UI"
