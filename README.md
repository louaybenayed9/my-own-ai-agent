# Personal AI Agent — n8n + OpenRouter

A self-hosted AI agent that combines seven open-source projects into one stack:

| Capability | Built on | Where |
|---|---|---|
| Orchestration & visual editing | **n8n** | [docker-compose.yml](docker-compose.yml), [n8n/workflows/agent.json](n8n/workflows/agent.json) |
| Multi-provider LLM | **OpenRouter** | `Chat Model` node (any model: Anthropic, OpenAI, Google, local) |
| Persistent memory | [rohitg00/agentmemory](https://github.com/rohitg00/agentmemory) | REST tools wired into the agent |
| Web browsing | [browser-use/browser-use](https://github.com/browser-use/browser-use) | [browser-service/](browser-service/) sidecar |
| Skills system | Claude-style SKILL.md packs | [skills-service/](skills-service/) |
| Diagrams | [cathrynlavery/diagram-design](https://github.com/cathrynlavery/diagram-design) | ported skill → `diagram-design` |
| Scientific workflows | [K-Dense-AI/claude-scientific-skills](https://github.com/K-Dense-AI/claude-scientific-skills) | ported skill → `scientific-analysis` |
| Security review | [mukul975/Anthropic-Cybersecurity-Skills](https://github.com/mukul975/Anthropic-Cybersecurity-Skills) | ported skill → `security-review` |
| Harness patterns | [ai-boost/awesome-harness-engineering](https://github.com/ai-boost/awesome-harness-engineering) | system prompt protocol + progressive disclosure |
| Context database (optional) | [volcengine/OpenViking](https://github.com/volcengine/OpenViking) | [setup/setup-openviking.sh](setup/setup-openviking.sh) |

## Architecture

```
 you (CLI / n8n chat UI)
        │
        ▼
┌─────────────── n8n :5678 ───────────────┐
│  Webhook :5678/webhook/agent            │
│  Chat Trigger (built-in chat UI)        │
│            │                            │
│       AI Agent node                     │
│   ├── OpenRouter Chat Model (LLM)       │
│   ├── Session Memory (window)           │
│   ├── search_memory  → REST → :3111      │──▶ agentmemory (host, Docker mode)
│   ├── remember_memory→ REST → :3111      │
│   ├── list_skills    → HTTP → :8001      │──▶ skills-service (3 SKILL.md packs)
│   ├── run_skill     → HTTP → :8001      │
│   └── browse_web    → HTTP → :8002      │──▶ browser-use + Chromium
└─────────────────────────────────────────┘
```

**Harness patterns applied** (from awesome-harness-engineering):
- *Progressive disclosure*: the agent sees only skill names/descriptions; full
  instructions load only when a skill is invoked (`list_skills` → `run_skill`).
- *Memory-first protocol*: the system prompt instructs the agent to recall
  before answering and to persist durable facts after.
- *Self-describing tools*: each tool's description tells the model when to use
  it, which matters more than the model itself.

## Quick start

```bash
# 1. Configure
cp .env.example .env
#    then edit .env: set OPENROUTER_API_KEY (https://openrouter.ai/keys)
#    pick any model via OPENROUTER_MODEL (default: anthropic/claude-sonnet-4.5)

# 2. Start agentmemory (host, Docker mode; keeps REST on :3111)
#    Windows: setup\start-agentmemory.cmd    macOS/Linux: bash setup/setup-agentmemory.sh

# 3. Start the core stack (n8n + skills + browser)
docker compose up -d --build

# 4. Import the workflow
#    Open http://localhost:5678 → Workflows → Import from File
#    → n8n/workflows/agent.json
#    Then: open the "OpenRouter Chat Model" node → select/create your
#    OpenRouter credential → Save & Activate the workflow.

# 5a. Chat in the browser: n8n → workflow → "Open chat"
# 5b. Or use the terminal:
python agent_cli.py
```

agentmemory's live memory viewer: <http://localhost:3113>

## Adding your own skills

Drop a folder into `skills-service/skills/`:

```
skills-service/skills/my-skill/
└── SKILL.md        # YAML frontmatter (name, description) + instructions
```

Restart the skills service (`docker compose restart skills`). The agent
discovers it automatically on the next `list_skills` call — no code changes.

## Extending

- **Per-skill scripts**: `run_skill` currently returns instructions for the
  LLM to apply. Extend `skills-service/app.py` to execute deterministic code
  per skill instead.
- **OpenViking**: run `bash setup/setup-openviking.sh`, then add more HTTP tool nodes
  in n8n pointing at its API — copy the pattern from the `list_skills` node.
- **Triggers**: the workflow is webhook + chat today; n8n's 400+ nodes mean
  you can add email/Telegram/schedule triggers to the same agent.

## Services & ports

| Service | Port | Purpose |
|---|---|---|
| n8n | 5678 | editor, chat UI, webhook `/webhook/agent` |
| skills-service | 8001 | SKILL.md packs (list/execute) |
| browser-service | 8002 | browser-use sidecar (POST /browse) |
| agentmemory | 3111 / 3113 | REST API / memory viewer |

## Troubleshooting

- **Webhook 404**: the workflow isn't Active, or you imported but didn't save.
- **Model errors**: the OpenRouter credential isn't selected on the Chat Model node.
- **Memory tool errors**: agentmemory isn't running (`curl localhost:3111/agentmemory/health`).
- **Browser timeouts**: first browser task downloads a Chromium build; `docker compose logs browser` to watch progress. `BROWSER_HEADLESS=false` in `.env` shows the browser (needs a display).
