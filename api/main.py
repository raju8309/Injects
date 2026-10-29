"""
Serves the ranking and the dashboard.

    uvicorn api.main:app --reload
    open http://localhost:8000
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from core.scoring import rank, score
from ingest.store import load

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"

app = FastAPI(title="Inject Fit", version="0.1.0")


@app.get("/api/ranking")
def ranking():
    rows = load()
    if not rows:
        raise HTTPException(
            404,
            "No candidates. Run `python3 -m ingest.seed`, then "
            "`python3 -m ingest.orange_book` to fill in patent status.",
        )
    return rank(rows, date.today())


@app.get("/api/candidate/{name}")
def candidate(name: str):
    """One candidate, with every field and where each value came from.

    The point of this endpoint is that a score can be taken apart. If a
    drug ranks high, you can see exactly which inputs earned it and which
    of them were a human's judgement rather than a source file.
    """
    rows = load()
    for c in rows:
        if c.generic_name.lower() == name.lower():
            return {
                "score": score(c, date.today()),
                "fields": c.to_json(),
                "known_fraction": round(c.known_fraction, 3),
                "unknown_fields": c.unknown_fields,
            }
    raise HTTPException(404, f"no candidate named '{name}'")


@app.get("/api/provenance")
def provenance():
    """How much of the whole dataset came from where.

    A screening tool built mostly on estimates is a hypothesis, and this is
    the endpoint that says so out loud.
    """
    rows = load()
    counts: dict[str, int] = {}
    for c in rows:
        for f in c.field_map().values():
            counts[f.source] = counts.get(f.source, 0) + 1
    total = sum(counts.values()) or 1
    return {
        "candidates": len(rows),
        "field_values": total,
        "by_source": {k: {"count": v, "share": round(v / total, 3)}
                      for k, v in sorted(counts.items(), key=lambda kv: -kv[1])},
    }


@app.get("/health")
def health():
    return {"ok": True, "candidates_loaded": len(load())}


@app.get("/")
def index():
    # no-store, or the browser cheerfully serves yesterday's ranking
    # against today's data, which is its own kind of wrong answer.
    return FileResponse(
        STATIC / "index.html",
        headers={"Cache-Control": "no-store, max-age=0"},
    )


app.mount("/static", StaticFiles(directory=STATIC), name="static")
