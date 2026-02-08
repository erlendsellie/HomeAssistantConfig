#!/bin/bash
# Helper script for AI to call HA services with proper auth
# Usage: ha_service.sh <domain> <service> <entity_id> [delay_seconds] [extra_json]
# Examples:
#   ha_service.sh light turn_off light.kjøkkenbord 60
#   ha_service.sh light turn_on light.living_room 0 '{"brightness_pct":10}'
#   ha_service.sh script playmessage script.playmessage 60 '{"message":"Hello world"}'

DOMAIN="$1"
SERVICE="$2"
ENTITY_ID="$3"
DELAY="${4:-0}"
EXTRA_JSON="${5:-}"

TOKEN="REDACTED_HA_TOKEN"

if [ -z "$DOMAIN" ] || [ -z "$SERVICE" ] || [ -z "$ENTITY_ID" ]; then
  echo "Usage: ha_service.sh <domain> <service> <entity_id> [delay_seconds] [extra_json]"
  exit 1
fi

if [ "$DELAY" -gt 0 ] 2>/dev/null; then
  sleep "$DELAY"
fi

# Build JSON body: start with entity_id, merge extra_json if provided
if [ -n "$EXTRA_JSON" ]; then
  BODY=$(python3 -c 'import json,sys; b={"entity_id":sys.argv[1]}; b.update(json.loads(sys.argv[2])); print(json.dumps(b))' "$ENTITY_ID" "$EXTRA_JSON" 2>/dev/null)
  if [ -z "$BODY" ]; then
    BODY="{\"entity_id\":\"$ENTITY_ID\"}"
  fi
else
  BODY="{\"entity_id\":\"$ENTITY_ID\"}"
fi

curl -s -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "$BODY" \
  "http://localhost:8123/api/services/$DOMAIN/$SERVICE"
