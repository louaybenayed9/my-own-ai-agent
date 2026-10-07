"""
browser-use sidecar for the n8n AI agent.

Wraps the browser-use Python agent behind a tiny HTTP API so n8n can drive a
real browser as a tool:
  GET  /health
  POST /browse   {task: str, max_steps?: int} -> {status, result, steps, errors}

The sidecar uses its own LLM (via OpenRouter) for the inner browser loop —
n8n only sends the high-level task.
"""

import asyncio
import logging
import os
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("browser-service")

HEADLESS = os.environ.get("BROWSER_HEADLESS", "true").lower() == "true"
MAX_STEPS = int(os.environ.get("BROWSER_MAX_STEPS", "20"))

app = FastAPI(title="agent-browser", version="0.2.0")

# One browser session at a time for the MVP (keeps memory predictable).
_browser_lock = asyncio.Lock()


class BrowseRequest(BaseModel):
    task: str
    max_steps: int | None = None


def _build_llm():
    """LLM for the inner browser loop.

    Prefers the LiteLLM proxy (OpenRouter primary + Gemini/Groq fallbacks on
    quota), falling back to direct OpenRouter when LiteLLM is not configured.
    """
    litellm_url = os.environ.get("LITELLM_URL")
    master_key = os.environ.get("LITELLM_MASTER_KEY")
    if litellm_url and master_key:
        from browser_use.llm.openai.chat import ChatOpenAI

        return ChatOpenAI(
            model=os.environ.get("LITELLM_MODEL", "openrouter/free"),
            api_key=master_key,
            base_url=litellm_url.rstrip("/") + "/v1",
        )
    from browser_use.llm.openrouter.chat import ChatOpenRouter

    return ChatOpenRouter(model=os.environ.get("OPENROUTER_MODEL", "anthropic/claude-sonnet-4.5"))


def _build_agent(task: str, max_steps: int):
    """Construct a browser-use Agent, adapting to 0.13.x API surface."""
    from browser_use import Agent

    llm = _build_llm()

    # browser-use 0.13: BrowserSessionConfig lives in browser_session.py and is
    # re-exported from the package root; Browser was renamed BrowserSession.
    try:
        from browser_use import BrowserSessionConfig  # new location

        session = BrowserSessionConfig(headless=HEADLESS)
    except ImportError:
        from browser_use import BrowserSession, BrowserProfile  # older 0.13 layout

        session = BrowserSession(browser_profile=BrowserProfile(headless=HEADLESS))

    return Agent(task=task, llm=llm, browser_session=session)


def _history_to_result(history: Any) -> dict[str, Any]:
    """Extract a JSON-safe summary from an AgentHistoryList."""
    final = None
    try:
        final = history.final_result()
    except Exception:
        final = None

    steps = 0
    try:
        steps = len(history.history)
    except Exception:
        steps = 0

    errors: list[str] = []
    try:
        errors = [str(e) for e in (history.errors() or []) if e]
    except Exception:
        pass

    status = "done" if final else "incomplete"
    return {"status": status, "result": final, "steps": steps, "errors": errors[:5]}


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "headless": str(HEADLESS),
        "default_max_steps": MAX_STEPS,
    }


@app.post("/browse")
async def browse(req: BrowseRequest) -> dict[str, Any]:
    try:
        agent = _build_agent(req.task, req.max_steps or MAX_STEPS)
    except Exception as exc:
        logger.exception("failed to construct agent")
        raise HTTPException(status_code=500, detail=f"agent construction failed: {exc}")

    async with _browser_lock:
        try:
            history = await agent.run(max_steps=req.max_steps or MAX_STEPS)
            return _history_to_result(history)
        except Exception as exc:
            logger.exception("browse failed")
            raise HTTPException(status_code=500, detail=str(exc))
