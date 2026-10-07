#!/usr/bin/env bash
# Optional: start OpenViking (context database for the agent) via Docker.
# Once running, expose it to the agent the same way as agentmemory:
# add an MCP Client Tool node in n8n pointing at its MCP endpoint, or extend
# the skills service to proxy its HTTP API.
# Docs: https://docs.openviking.ai/
set -euo pipefail

OV_DIR="$(pwd)/openviking"
mkdir -p "$OV_DIR"
cd "$OV_DIR"

echo "==> Cloning OpenViking (first run only)"
[ -d .git ] || git clone --depth 1 https://github.com/volcengine/OpenViking.git .

echo "==> Starting OpenViking via Docker Compose"
docker compose up -d

echo ""
echo "==> OpenViking starting. Check its README for the API/MCP endpoint and"
echo "    wire it into the n8n workflow as another mcpClientTool node."
