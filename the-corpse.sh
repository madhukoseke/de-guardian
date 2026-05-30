#!/usr/bin/env bash
#
# daily_revenue_aggregation.sh
# -----------------------------------------------------------------------------
# THE DECEASED.  Born ~2019. Cause of death: schema drift, May 30 2026.
#
# Crontab (do not touch, nobody remembers why it's 6am):
#   0 6 * * *  /opt/etl/daily_revenue_aggregation.sh >> /var/log/rev.log 2>&1
#
# This is the script we are burying. Open with this on stage, scroll slowly,
# let the room recognize their own infrastructure. Then kill it.
# -----------------------------------------------------------------------------

# No `set -euo pipefail`. Errors are a problem for future me.

SOURCE_API="https://source-api.internal/v3/transactions"   # bumped to v3 last week, surely fine
PGHOST="prod-analytics-db.internal"
PGUSER="etl_svc"
PGPASSWORD="hunter2_prod"        # TODO: move to vault (ticket DATA-114, opened 2021)
SLACK_HOOK="https://hooks.slack.com/services/T000/B000/xxxxx"
TODAY=$(date +%F)

echo "[$(date)] starting daily_revenue_aggregation for $TODAY"

# 1) Pull transactions. No retry. No timeout. If the API is slow, we hang.
RAW=$(curl -s "$SOURCE_API?date=$TODAY")

# 2) "Parse" the JSON. We don't have jq on the prod box, so... cut.
#    This is the line that dies when someone renames a field upstream.
AMOUNTS=$(echo "$RAW" | grep -o '"amount":[0-9.]*' | cut -d: -f2)
MERCHANTS=$(echo "$RAW" | grep -o '"merchant":"[^"]*"' | cut -d: -f2 | tr -d '"')

# 3) Sum it up in awk because installing pandas needed approval.
TOTAL=$(echo "$AMOUNTS" | awk '{s+=$1} END {print s}')

# 4) Did we get anything? Eh. If TOTAL is empty we just load 0 and move on.
if [ -z "$TOTAL" ]; then
  TOTAL=0   # "temporary" — added during the Q4 2022 incident, never removed
fi

# 5) Load. String-interpolated SQL straight into prod. What could go wrong.
PGPASSWORD=$PGPASSWORD psql -h "$PGHOST" -U "$PGUSER" -d analytics -c \
  "INSERT INTO revenue (run_date, revenue) VALUES ('$TODAY', $TOTAL);" \
  > /dev/null 2>&1   # silence the duplicate-key errors, they're "expected"

# 6) Alerting: a Slack ping that only fires if the *insert* exit code is seen,
#    which it never is because of the 2>&1 above. So it pages... never.
if [ $? -ne 0 ]; then
  curl -s -X POST "$SLACK_HOOK" -d "{\"text\":\"revenue job maybe failed?\"}" >/dev/null
fi

echo "[$(date)] done. loaded total=$TOTAL"

# -----------------------------------------------------------------------------
# EULOGY  (read this part out loud)
# -----------------------------------------------------------------------------
# Here lies daily_revenue_aggregation.sh. It glued five systems together with
# grep, hope, and a hardcoded password. It had no retries, no timeouts, no
# observability, and an alert that fired exactly zero times in seven years.
#
# When the source API renamed `amount` to `txn_amount`, it didn't error. It
# quietly loaded $0 in revenue and told no one. Someone found out from a
# dashboard three days later.
#
# It is survived by a SuperPlane Canvas that catches the failure, asks Claude
# what broke, waits for a human to say yes, fixes it, and writes down every
# step. May it rest. The graveyard is large; this is the first headstone.
# -----------------------------------------------------------------------------
