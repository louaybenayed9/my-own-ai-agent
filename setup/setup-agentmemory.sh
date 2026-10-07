#!/usr/bin/env bash
# Start agentmemory (the memory server for the agent) in Docker mode.
# Works on Windows (Docker Desktop) / macOS / Linux.
# REST + MCP: http://localhost:3111  |  Viewer: http://localhost:3113
set -euo pipefail

echo "==> Starting agentmemory on :3111 (MCP + REST) and :3113 (viewer)"
# AGENTMEMORY_USE_DOCKER=1 forces the Docker path (recommended on native Windows).
# pwd -W gives a Windows-friendly path in Git Bash; plain pwd elsewhere.
AGENTMEMORY_USE_DOCKER=1 npx -y @agentmemory/agentmemory@latest \
  --data-dir "$(pwd -W 2>/dev/null || pwd)/data/agentmemory"
