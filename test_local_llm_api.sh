#!/usr/bin/env bash

set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8317}"
API_KEY="${API_KEY:-your-api-key-1}"
MODEL="${MODEL:-coder-model}"

auth_header="Authorization: Bearer ${API_KEY}"

echo "== Models =="
curl -sS "${BASE_URL}/v1/models" \
  -H "${auth_header}" \
  -H 'Content-Type: application/json'
echo
echo

echo "== Chat Completion =="
curl -sS "${BASE_URL}/v1/chat/completions" \
  -H "${auth_header}" \
  -H 'Content-Type: application/json' \
  -d "{
    \"model\": \"${MODEL}\",
    \"messages\": [
      {\"role\": \"user\", \"content\": \"Reply with exactly: local api ok\"}
    ],
    \"temperature\": 0
  }"
echo
