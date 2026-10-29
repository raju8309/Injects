"""
Where the candidates live on disk. One JSON file, no database, so any row
behind any score can be opened in a text editor and checked.
"""

from __future__ import annotations

import json
from pathlib import Path

from core.model import Candidate

DATA = Path(__file__).resolve().parents[1] / "data"
DATA.mkdir(exist_ok=True)
PATH = DATA / "candidates.json"


def save(candidates: list[Candidate], path: Path = PATH) -> Path:
    path.write_text(json.dumps([c.to_json() for c in candidates], indent=2))
    return path


def load(path: Path = PATH) -> list[Candidate]:
    if not path.exists():
        return []
    return [Candidate.from_json(d) for d in json.loads(path.read_text())]
