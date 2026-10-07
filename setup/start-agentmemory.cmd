@echo off
rem Starts agentmemory detached (survives the terminal), logging to agentmemory.log
rem REST + MCP: http://localhost:3111   Viewer: http://localhost:3113
cd /d "%~dp0.."
set AGENTMEMORY_USE_DOCKER=1
npx -y @agentmemory/agentmemory@latest --data-dir "%~dp0..\data\agentmemory" > agentmemory.log 2>&1
