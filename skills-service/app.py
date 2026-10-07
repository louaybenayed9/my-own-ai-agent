"""
Skills service for the n8n AI agent.

Implements Claude-style "Agent Skills": each skill is a directory containing a
SKILL.md file with YAML frontmatter (name, description) plus instructions.
The agent sees only names/descriptions until it decides to load the full body
(progressive disclosure — cheaper tokens, better routing accuracy).

Endpoints used by the n8n workflow:
  GET  /health
  GET  /skills                -> [{name, description, path, instructions}]
  POST /skills/execute        -> {name, input} -> {skill, instructions, result}
"""

import os
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

SKILLS_DIR = Path(os.environ.get("SKILLS_DIR", "/app/skills"))
PROFILE_PATH = Path(os.environ.get("PROFILE_PATH", "/app/profile.yaml"))
SOUL_PATH = Path(os.environ.get("SOUL_PATH", "/app/soul.md"))
from knowledge import (
    read_all as knowledge_read_all,
    read_doc as knowledge_read_doc,
    reindex_now,
    search as knowledge_search,
    status as knowledge_status,
)
# Compiled-in fallback persona, served if soul.md is missing or corrupt.
FALLBACK_SOUL = """# Soul (fallback)
You are the user's personal AI agent, running on n8n.

## Voice
- Direct and concise. Lead with the answer, then supporting detail.
- Use markdown formatting and code blocks where appropriate.

## Values
- Never invent facts about the user; use profile data and memory only.
- Report what tools you used and any failures plainly.
- Durable facts about the user go to memory (remember_memory).
"""

app = FastAPI(title="agent-skills", version="0.1.0")


class ExecuteRequest(BaseModel):
    name: str
    input: str


def parse_skill_file(skill_md: Path) -> dict[str, Any] | None:
    """Parse a SKILL.md with YAML frontmatter into a skill record."""
    try:
        raw = skill_md.read_text(encoding="utf-8")
    except OSError:
        return None
    if not raw.startswith("---"):
        return None
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return None
    try:
        meta = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return None
    body = parts[2].strip()
    name = str(meta.get("name") or skill_md.parent.name)
    description = str(meta.get("description") or "").strip()
    return {
        "name": name,
        "description": description,
        "path": str(skill_md.parent),
        "instructions": body,
    }


def discover_skills() -> dict[str, dict[str, Any]]:
    skills: dict[str, dict[str, Any]] = {}
    if not SKILLS_DIR.is_dir():
        return skills
    for skill_md in sorted(SKILLS_DIR.rglob("SKILL.md")):
        parsed = parse_skill_file(skill_md)
        if parsed:
            skills[parsed["name"]] = parsed
    return skills


@app.get("/profile")
def get_profile() -> dict[str, Any]:
    """The user's complete profile database, parsed live from profile.yaml.

    The file is volume-mounted, so edits apply immediately without a rebuild.
    """
    if not PROFILE_PATH.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"Profile file not found at {PROFILE_PATH}. Create it (see profile/profile.yaml).",
        )
    try:
        data = yaml.safe_load(PROFILE_PATH.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise HTTPException(status_code=500, detail=f"Profile YAML is invalid: {exc}")
    if not isinstance(data, dict):
        raise HTTPException(status_code=500, detail="Profile YAML must be a mapping at the top level")
    return {"profile": data, "source": str(PROFILE_PATH)}


@app.get("/soul")
def get_soul() -> dict[str, Any]:
    """The agent's personality file (soul.md convention), parsed live.

    Falls back to a compiled-in basic persona if the file is missing or
    invalid, so the agent always has a usable identity.
    """
    if SOUL_PATH.is_file():
        try:
            raw = SOUL_PATH.read_text(encoding="utf-8")
        except OSError as exc:
            return {"soul": FALLBACK_SOUL, "source": "fallback", "detail": str(exc)}
        if raw.startswith("---"):
            parts = raw.split("---", 2)
            if len(parts) == 3:
                try:
                    meta = yaml.safe_load(parts[1]) or {}
                except yaml.YAMLError:
                    meta = {}
                return {
                    "soul": parts[2].strip(),
                    "meta": meta,
                    "source": "file",
                }
        return {"soul": raw.strip(), "source": "file"}
    return {"soul": FALLBACK_SOUL, "source": "fallback"}


@app.post("/knowledge/reindex")
def knowledge_reindex() -> dict[str, Any]:
    return reindex_now()


@app.post("/knowledge/search")
def knowledge_search_endpoint(body: dict[str, Any] | None = None) -> dict[str, Any]:
    body = body or {}
    query = str(body.get("query") or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="Field 'query' is required")
    k = body.get("k", 6)
    try:
        k = max(1, min(int(k), 25))
    except (TypeError, ValueError):
        k = 6
    fd = body.get("full_doc", False)
    full_doc = fd is True or (isinstance(fd, str) and fd.lower() in ("true", "1", "yes"))
    return knowledge_search(
        query,
        k=k,
        full_doc=full_doc,
    )


@app.get("/knowledge/status")
def knowledge_status_endpoint() -> dict[str, Any]:
    return knowledge_status()


@app.post("/knowledge/read")
def knowledge_read_endpoint(body: dict[str, Any] | None = None) -> dict[str, Any]:
    """Read documents: /knowledge/read {name?} -> one doc; {} -> the whole folder."""
    body = body or {}
    name = body.get("name")
    if name and str(name).lower() not in ("all", "*"):
        doc = knowledge_read_doc(str(name))
        if doc is None:
            raise HTTPException(status_code=404, detail=f"Document not found or unreadable: {name}")
        return doc
    return knowledge_read_all()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/skills")
def list_skills() -> list[dict[str, Any]]:
    """Names + descriptions only. The agent loads a full body via /skills/execute."""
    return [
        {"name": s["name"], "description": s["description"]}
        for s in discover_skills().values()
    ]


@app.post("/skills/execute")
def execute_skill(req: ExecuteRequest) -> dict[str, Any]:
    skill = discover_skills().get(req.name)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Unknown skill: {req.name}")
    # MVP: hand the full instructions back for the LLM to apply to `input`.
    # Extend here with per-skill scripts later (see README "Extending").
    return {
        "skill": skill["name"],
        "description": skill["description"],
        "instructions": skill["instructions"],
        "input": req.input,
        "result": (
            f"Apply the '{skill['name']}' skill instructions below to this input:\n"
            f"{req.input}\n\n--- SKILL INSTRUCTIONS ---\n{skill['instructions']}"
        ),
    }
