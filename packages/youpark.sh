#!/bin/bash
# Check YouPark for pending payments for a license plate.
# Usage: ./youpark.sh [LICENSE_PLATE]
# Set DEBUG=1 to print request/response details to stderr while keeping stdout machine-readable.

set -u

LICENSE_PLATE="${1:-${LICENSE_PLATE:-EN52492}}"
DEBUG="${DEBUG:-0}"

debug() {
  if [ "$DEBUG" = "1" ]; then
    echo "[youpark] $*" >&2
  fi
}

COOKIE_JAR=$(mktemp)
RESPONSE_FILE=$(mktemp)
trap 'rm -f "$COOKIE_JAR" "$RESPONSE_FILE"' EXIT

debug "Checking plate: $LICENSE_PLATE"

# Fetch a fresh XSRF token and session cookies first.
TOKEN_HTTP_CODE=$(curl -sS -m 10 -c "$COOKIE_JAR" -L -o /dev/null -w '%{http_code}' \
  "https://www.youpark.no/dashboard/payment")
TOKEN_EXIT_CODE=$?
debug "Token request exit=$TOKEN_EXIT_CODE http=$TOKEN_HTTP_CODE"

if [ $TOKEN_EXIT_CODE -ne 0 ]; then
  echo "error"
  exit 1
fi

XSRF=$(awk '$6 == "X-XSRF-Token" { print $7 }' "$COOKIE_JAR" | tail -n 1)
if [ -n "$XSRF" ]; then
  debug "XSRF token found: ${XSRF:0:8}..."
else
  debug "No XSRF token found in cookie jar"
  echo "error"
  exit 1
fi

PAY_HTTP_CODE=$(curl -sS -m 10 -X POST "https://www.youpark.no/api/account/paywithin48/search" \
  -H "accept: application/json" \
  -H "content-type: application/json" \
  -H "x-requested-with: XMLHttpRequest" \
  -H "x-xsrf-token: $XSRF" \
  -b "$COOKIE_JAR" \
  -o "$RESPONSE_FILE" \
  -w '%{http_code}' \
  --data-raw "{\"licensePlate\":\"$LICENSE_PLATE\"}")

EXIT_CODE=$?
RESPONSE=$(cat "$RESPONSE_FILE")
debug "Search request exit=$EXIT_CODE http=$PAY_HTTP_CODE"
debug "Raw response: $RESPONSE"

if [ $EXIT_CODE -ne 0 ]; then
  echo "error"
  exit 1
fi

# Check if response is valid JSON
if ! echo "$RESPONSE" | jq empty 2>/dev/null; then
  debug "Response was not valid JSON"
  echo "error"
  exit 1
fi

# YouPark API returns:
#   {"success":false,"data":null,"errors":[{"key":"ERR_NoTransactionFound",...}]} = no payments
#   {"success":true,"data":[...]} = payments found
# Anything else = unexpected response format
HAS_SUCCESS=$(echo "$RESPONSE" | jq 'has("success")' 2>/dev/null)
if [ "$HAS_SUCCESS" != "true" ]; then
  debug "Response did not contain a success field"
  echo "api_changed"
  exit 0
fi

SUCCESS=$(echo "$RESPONSE" | jq -r '.success')
if [ "$SUCCESS" = "false" ]; then
  ERR_KEY=$(echo "$RESPONSE" | jq -r '.errors[0].key // ""' 2>/dev/null)
  debug "API reported success=false error_key=$ERR_KEY"
  if [ "$ERR_KEY" = "ERR_NoTransactionFound" ]; then
    echo "0"
  else
    echo "api_changed"
  fi
else
  COUNT=$(echo "$RESPONSE" | jq '.data | if type == "array" then length else 1 end' 2>/dev/null)
  debug "API reported success=true count=$COUNT"
  if [ -z "$COUNT" ] || [ "$COUNT" = "null" ]; then
    echo "api_changed"
  else
    echo "$COUNT"
  fi
fi
