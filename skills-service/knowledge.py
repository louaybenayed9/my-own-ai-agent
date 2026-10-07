"""
Lightweight RAG (BM25 keyword retrieval) over the user's knowledge folder.

Reads documents from KNOWLEDGE_DIR (default /app/knowledge) with support for:
  .txt .md  — plain text
  .pdf      — pypdf text extraction
  .docx     — python-docx paragraph extraction

Endpoints served from app.py:
  GET  /knowledge/status     -> {docs, chunks, index_age_s, folder}
  POST /knowledge/search     -> {query, k?, full_doc?} -> {results|documents, ...}
  POST /knowledge/reindex    -> rebuilds the index now
"""

from __future__ import annotations

import hashlib
import re
import threading
import time
from pathlib import Path
from typing import Any

from pypdf import PdfReader
import docx  # python-docx
import olefile  # legacy .doc best-effort

KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"
CHUNK_SIZE = 1200          # characters per chunk
CHUNK_OVERLAP = 200        # character overlap between chunks
MIN_CHUNK_LEN = 60         # skip chunks smaller than this

_LOCK = threading.Lock()
_state: dict[str, Any] = {
    "docs": {},      # relname -> {text, mtime, sha1, n_chars}
    "chunks": [],    # [{doc, chunk_id, text, offset}]
}


# ----------------------------------------------------------------- parsing

def parse_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    parts = []
    for page in reader.pages:
        t = page.extract_text() or ""
        if t.strip():
            parts.append(t)
    return "\n".join(parts)


def parse_docx(path: Path) -> str:
    d = docx.Document(str(path))
    parts = [p.text for p in d.paragraphs if p.text.strip()]
    for tbl in d.tables:  # tables are common in CVs
        for row in tbl.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    return "\n".join(parts)


def parse_doc(path: Path) -> str:
    """Best-effort legacy .doc: printable runs from the WordDocument stream.

    Structure (bold/table layout) is lost, but the plain text survives for
    typical letters, resumes, and notes.
    """
    with olefile.OleFileIO(str(path)) as ole:
        stream_name = next(
            (s for s in ole.listdir() if s[-1].lower() == "worddocument"), None
        )
        if stream_name is None:
            raise ValueError("no WordDocument stream (not a legacy .doc?)")
        raw = ole.openstream(stream_name).read()
    runs = re.findall(rb"[\x20-\x7e\xa0-\xff]{4,}", raw)
    return "\n".join(r.decode("latin-1", "ignore").strip() for r in runs)


def parse_plaintext(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


PARSERS = {
    ".doc": parse_doc,
    ".docx": parse_docx,
    ".pdf": parse_pdf,
    ".txt": parse_plaintext,
    ".md": parse_plaintext,
}
SUPPORTED = sorted(PARSERS)


def _normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _chunk_text(doc: str, text: str) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    step = CHUNK_SIZE - CHUNK_OVERLAP
    start = 0
    cid = 0
    n = len(text)
    while start < n:
        piece = text[start:start + CHUNK_SIZE]
        if piece.strip() and len(piece.strip()) >= MIN_CHUNK_LEN:
            chunks.append({
                "doc": doc,
                "chunk_id": cid,
                "offset": start,
                "text": piece,
            })
            cid += 1
        if start + CHUNK_SIZE >= n:
            break
        start += step
    return chunks


# ----------------------------------------------------------------- indexing

def _scan_folder() -> dict[str, dict[str, Any]]:
    docs: dict[str, dict[str, Any]] = {}
    if not KNOWLEDGE_DIR.is_dir():
        return docs
    for path in sorted(KNOWLEDGE_DIR.rglob("*")):
        if not path.is_file():
            continue
        parser = PARSERS.get(path.suffix.lower())
        if parser is None:
            continue
        try:
            mtime = path.stat().st_mtime
            raw = parser(path)
        except Exception as exc:  # noqa: BLE001 — report, don't crash the service
            rel = str(path.relative_to(KNOWLEDGE_DIR))
            docs[f"{rel} [ERROR]"] = {
                "text": "", "mtime": 0.0, "sha1": "", "n_chars": 0,
                "error": f"{type(exc).__name__}: {exc}",
            }
            continue
        rel = str(path.relative_to(KNOWLEDGE_DIR))
        text = _normalize(raw)
        docs[rel] = {
            "text": text,
            "mtime": mtime,
            "sha1": hashlib.sha1(text.encode("utf-8")).hexdigest()[:12],
            "n_chars": len(text),
        }
    return docs


def _rebuild_locked() -> None:
    docs = _scan_folder()
    chunks: list[dict[str, Any]] = []
    for rel, meta in docs.items():
        if meta.get("error") or not meta["text"]:
            continue
        chunks.extend(_chunk_text(rel, meta["text"]))
    _state["docs"] = docs
    _state["chunks"] = chunks
    _state["built_at"] = time.time()


def _state_fresh() -> bool:
    """Return True if no source file changed since the last index build."""
    docs = _state.get("docs") or {}
    try:
        current = _scan_folder()
    except Exception:
        return False
    if set(current.keys()) != set(docs.keys()):
        return False
    for rel, meta in current.items():
        old = docs.get(rel)
        if old is None or old["mtime"] != meta["mtime"] or old["sha1"] != meta["sha1"]:
            return False
    return True


def ensure_index() -> None:
    with _LOCK:
        if not _state.get("chunks") or not _state_fresh():
            _rebuild_locked()


def reindex_now() -> dict[str, Any]:
    with _LOCK:
        _rebuild_locked()
        return status()


# ----------------------------------------------------------------- scoring

_TOKEN_RE = re.compile(r"[a-zA-Z0-9_+#.]+")

_stopwords = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with",
    "at", "by", "from", "as", "is", "are", "was", "were", "be", "been",
    "it", "its", "this", "that", "these", "those", "my", "me", "i",
}


def _tokens(text: str) -> list[str]:
    return [
        t.lower()
        for t in _TOKEN_RE.findall(text)
        if t.lower() not in _stopwords and len(t) > 1
    ]


def _score_chunk(query: str, chunk_text: str) -> tuple[float, list[str]]:
    """Hybrid score: phrase hits (weighted) + keyword frequency."""
    ql = query.lower()
    cl = chunk_text.lower()

    score = 0.0
    matched: list[str] = []

    for phrase in re.findall(r'"([^"]+)"', ql):
        phrase = phrase.strip()
        if phrase and phrase in cl:
            score += 6.0
            matched.append(f'"{phrase}"')
    ql_clean = re.sub(r'"', " ", ql)

    q_tokens = _tokens(ql_clean)
    if not q_tokens:
        return score, matched

    c_tokens = _tokens(cl)
    bag: dict[str, int] = {}
    for t in c_tokens:
        bag[t] = bag.get(t, 0) + 1

    for t in q_tokens:
        tf = bag.get(t, 0)
        if tf:
            score += 1.0 * min(tf, 4) / (1 + t.count(" "))
            matched.append(t)

    return score, sorted(set(matched))


def _best_window(chunk_text: str, query: str, width: int = 220) -> str:
    """Center a snippet window on the densest match area."""
    positions: list[int] = []
    for t in _tokens(query):
        idx = chunk_text.lower().find(t)
        if idx >= 0:
            positions.append(idx)
    if not positions:
        return chunk_text[:width]
    center = sum(positions) // len(positions)
    start = max(0, center - width // 2)
    end = min(len(chunk_text), start + width)
    return chunk_text[start:end]


# ----------------------------------------------------------------- search API

def search(
    query: str,
    k: int = 6,
    full_doc: bool = False,
) -> dict[str, Any]:
    ensure_index()
    chunks = _state["chunks"]
    if not chunks:
        return {
            "total_docs": len(_state["docs"]),
            "query": query,
            "results": [],
            "documents": [],
            "note": "Knowledge folder is empty or unreadable.",
        }

    scored = []
    for ch in chunks:
        s, matched = _score_chunk(query, ch["text"])
        if s > 0:
            scored.append((s, matched, ch))
    scored.sort(key=lambda x: (-x[0], x[2]["doc"], x[2]["chunk_id"]))

    results = []
    for s, matched, ch in scored[:max(1, k)]:
        results.append({
            "doc": ch["doc"],
            "chunk_id": ch["chunk_id"],
            "score": round(s, 2),
            "snippets": [_best_window(ch["text"], query)],
            "matched": matched[:12],
        })

    documents = []
    if full_doc:
        # Rank docs by total chunk score (matched first), then name; return up to 4
        # whole documents. Guarantees timeline/current-role questions always get a
        # readable document even when no chunk keyword-matches the query.
        doc_scores: dict[str, float] = {
            rel: 0.0 for rel, meta in _state["docs"].items() if meta.get("text")
        }
        for s, _m, ch in scored:
            doc_scores[ch["doc"]] = doc_scores.get(ch["doc"], 0.0) + s
        order = sorted(doc_scores, key=lambda d: (-doc_scores[d], d))[:4]
        for rel in order:
            meta = _state["docs"][rel]
            documents.append({
                "name": rel,
                "n_chars": meta["n_chars"],
                "sha1": meta["sha1"],
                "text": meta["text"],
            })

    return {
        "total_docs": len(_state["docs"]),
        "total_chunks": len(chunks),
        "query": query,
        "results": results,
        "documents": documents,
    }


# ----------------------------------------------------------------- read API

READ_ALL_MAX_TOTAL_CHARS = 80_000   # safety cap for "read everything" replies


def read_doc(name: str) -> dict[str, Any] | None:
    """Full text of one indexed document by relative name, or None."""
    ensure_index()
    meta = _state["docs"].get(name)
    if not meta or meta.get("error") or not meta.get("text"):
        return None
    return {"name": name, "n_chars": meta["n_chars"], "sha1": meta["sha1"], "text": meta["text"]}


def read_all(max_total_chars: int = READ_ALL_MAX_TOTAL_CHARS) -> dict[str, Any]:
    """Whole documents in stable name order, capped by total characters."""
    ensure_index()
    docs_out: list[dict[str, Any]] = []
    total = 0
    skipped: list[str] = []
    for rel in sorted(_state["docs"]):
        meta = _state["docs"][rel]
        if meta.get("error") or not meta.get("text"):
            continue
        if total + meta["n_chars"] > max_total_chars:
            skipped.append(rel)
            continue
        docs_out.append({
            "name": rel,
            "n_chars": meta["n_chars"],
            "sha1": meta["sha1"],
            "text": meta["text"],
        })
        total += meta["n_chars"]
    return {
        "documents": docs_out,
        "count": len(docs_out),
        "total_chars": total,
        "skipped_for_size": skipped,
    }


def status() -> dict[str, Any]:
    ensure_index()
    docs: dict[str, Any] = _state.get("docs", {})
    built_at = _state.get("built_at")
    fresh = _state_fresh() if docs else False
    return {
        "folder": str(KNOWLEDGE_DIR),
        "docs": [
            {
                "name": rel,
                "chars": meta["n_chars"],
                "sha1": meta["sha1"],
                "error": meta.get("error"),
            }
            for rel, meta in docs.items()
        ],
        "chunks": len(_state.get("chunks", [])),
        "index_age_s": (time.time() - built_at) if built_at else None,
        "fresh": fresh,
        "supported": SUPPORTED,
    }
