"""Read-only local ingestion tracking; document contents never leave SQLite/artifacts."""
from __future__ import annotations

import html
import sqlite3
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/api", tags=["Ingestion"])
REGISTRY = Path("/Users/hoangnc/AI/pdf-knowledge-pipeline/state/document_registry.sqlite")


def _summary() -> list[tuple[str, int]]:
    if not REGISTRY.exists():
        return []
    try:
        with sqlite3.connect(f"file:{REGISTRY}?mode=ro", uri=True, timeout=2) as db:
            return [(str(state), int(count)) for state, count in db.execute("SELECT current_state, COUNT(*) FROM documents GROUP BY current_state ORDER BY current_state")]
    except sqlite3.Error:
        return []


@router.get("/ingestion-status")
async def ingestion_status() -> dict[str, object]:
    """Metadata-only progress summary for a local, authenticated-by-host UI."""
    rows = _summary()
    return {"registry_available": REGISTRY.exists(), "states": dict(rows), "document_contents_exposed": False}


@router.get("/ingestion", response_class=HTMLResponse)
async def ingestion_page() -> str:
    rows = _summary()
    table = "".join(f"<tr><td>{html.escape(state)}</td><td>{count}</td></tr>" for state, count in rows) or "<tr><td colspan='2'>Registry unavailable</td></tr>"
    return "<!doctype html><title>Local ingestion status</title><h1>Local ingestion status</h1><p>Metadata-only: document content is not exposed.</p><table><thead><tr><th>State</th><th>Documents</th></tr></thead><tbody>" + table + "</tbody></table>"
