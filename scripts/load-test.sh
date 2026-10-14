#!/usr/bin/env bash
# Generate traffic so Grafana panels populate and the HPA has CPU to react to.
# Usage: scripts/load-test.sh http://<ingress-host-or-elb> [seconds] [parallel]
set -euo pipefail

BASE="${1:?usage: $0 <base-url> [seconds] [parallel]}"
DURATION="${2:-120}"
PARALLEL="${3:-20}"
END=$((SECONDS + DURATION))

worker() {
  while [ "$SECONDS" -lt "$END" ]; do
    curl -s -o /dev/null "$BASE/api/appointments"
    curl -s -o /dev/null "$BASE/api/appointments/stats"
    curl -s -o /dev/null "$BASE/api/doctors"
  done
}

echo "Hitting $BASE for ${DURATION}s with $PARALLEL workers..."
for _ in $(seq "$PARALLEL"); do worker & done
wait
echo "Done. Check: kubectl get hpa -n clinicq -w"
