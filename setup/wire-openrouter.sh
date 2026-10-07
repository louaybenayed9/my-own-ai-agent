#!/usr/bin/env bash
# Wires your OpenRouter key (from .env) into n8n, relinks the workflow,
# activates it, injects the key into the browser sidecar, and sends a test
# message through the agent. Run from anywhere: bash setup/wire-openrouter.sh
set -euo pipefail
cd "$(dirname "$0")/.."

KEY=$(grep -E '^OPENROUTER_API_KEY=' .env | cut -d= -f2- | tr -d '\r' | tr -d '"')
if [ -z "$KEY" ] || [ "$KEY" = "sk-or-v1-xxxxxxxxxxxxxxxxxxxxxxxx" ]; then
  echo "ERROR: put your real OpenRouter key in .env first (OPENROUTER_API_KEY=...)"
  exit 1
fi
WF_ID="9f1e2d3c-4b5a-6789-8abc-def012345678"
CRED_ID="a7c3e5f9-1234-4abc-9def-0123456789ab"
mkdir -p data

echo "==> 1/5 Importing OpenRouter credential into n8n"
python - "$KEY" "$CRED_ID" <<'EOF'
import json, sys
json.dump([{"id": sys.argv[2], "name": "OpenRouter account", "type": "openRouterApi",
            "data": {"apiKey": sys.argv[1]}}], open("data/openrouter-credential.json", "w"))
EOF
docker cp data/openrouter-credential.json agent-n8n:/tmp/cred.json
MSYS_NO_PATHCONV=1 docker exec agent-n8n n8n import:credentials --input=/tmp/cred.json
MSYS_NO_PATHCONV=1 docker exec agent-n8n sh -c "rm -f /tmp/cred.json" || true
rm -f data/openrouter-credential.json

echo "==> 2/5 Relinking workflow to the credential"
python - "$CRED_ID" <<'EOF'
import json, sys
p = "n8n/workflows/agent.json"
d = json.load(open(p, encoding="utf-8"))
for n in d["nodes"]:
    if n.get("credentials") and "openRouterApi" in n["credentials"]:
        n["credentials"]["openRouterApi"]["id"] = sys.argv[1]
json.dump(d, open(p, "w", encoding="utf-8"), indent=2)
print("   workflow relinked to credential", sys.argv[1])
EOF
docker cp n8n/workflows/agent.json agent-n8n:/tmp/agent.json
MSYS_NO_PATHCONV=1 docker exec agent-n8n n8n import:workflow --input=/tmp/agent.json
MSYS_NO_PATHCONV=1 docker exec agent-n8n sh -c "rm -f /tmp/agent.json" || true

echo "==> 3/5 Activating workflow"
if MSYS_NO_PATHCONV=1 docker exec agent-n8n n8n update:workflow --id="$WF_ID" --active=true >/dev/null 2>&1; then
  echo "   activated via CLI"
else
  echo "   CLI activation not available — click the Active toggle in the n8n UI:"
  echo "   http://localhost:5678 -> Personal AI Agent -> toggle top-right"
fi

echo "==> 4/5 Injecting key into the browser sidecar"
docker compose up -d --force-recreate browser >/dev/null 2>&1
echo "   browser sidecar recreated with OPENROUTER_API_KEY"

echo "==> 5/5 Sending a real test message through the agent (may take up to 2 min)"
sleep 5
RESP=$(curl -s --max-time 180 -X POST http://localhost:5678/webhook/agent \
  -H "Content-Type: application/json" \
  -d '{"message":"Hello! In one short sentence, tell me which model you are and confirm you can see your tools.","sessionId":"wire-test"}')
echo "AGENT RESPONSE:"
echo "$RESP" | python -c "import json,sys; d=json.load(sys.stdin); print(d.get('output', d))" 2>/dev/null || echo "$RESP"
