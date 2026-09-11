#!/usr/bin/env bash
# Wake the app from scale-to-zero. Run this about FIVE MINUTES before any live
# demo: with min-replicas 0, a cold start on Container Apps takes 20-40 seconds,
# and the first person to open the URL otherwise pays that wait in front of the room.
# Usage: bash deploy/warm.sh [fqdn]   (defaults to looking the FQDN up with az)
curl -sS -o /dev/null --max-time 120 -w "warm: HTTP %{http_code} in %{time_total}s\n" "https://${1:-$(az containerapp show -n "${APP_NAME:-payee-demo}" -g "${RESOURCE_GROUP:-payee-demo-rg}" --query properties.configuration.ingress.fqdn -o tsv)}/_stcore/health"
