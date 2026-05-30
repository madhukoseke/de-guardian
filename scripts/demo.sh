#!/usr/bin/env bash
# DE-Guardian live demo curls. Usage: ./scripts/demo.sh [BASE_URL]
set -euo pipefail

BASE="${1:-http://localhost:8000}"
BASE="${BASE%/}"

echo "=== DE-Guardian demo @ $BASE ==="
echo ""
echo "1. Status (healthy)"
curl -s "$BASE/status" | python3 -m json.tool
echo ""
echo "2. Arm schema_drift"
curl -s -X POST "$BASE/break?mode=schema_drift" | python3 -m json.tool
echo ""
echo "3. Run (expect failure + incident)"
curl -s -X POST "$BASE/run" | python3 -m json.tool
echo ""
echo ">>> Switch to SuperPlane Canvas: approve remediation <<<"
read -r -p "Press Enter after approving in SuperPlane..."
echo ""
echo "4. Heal (if Canvas did not call /heal yet)"
curl -s -X POST "$BASE/heal" | python3 -m json.tool
echo ""
echo "5. Run (expect success)"
curl -s -X POST "$BASE/run" | python3 -m json.tool
echo ""
echo "6. Audit trail"
curl -s "$BASE/runs?limit=5" | python3 -m json.tool
