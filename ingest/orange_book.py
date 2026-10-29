"""
Fill the patent and exclusivity fields from the FDA's own files.

This is the import that turns a directional list into one you could take
into a meeting. Everything else in the seed is a property of the marketed
product that anyone in the field could confirm. Patent status is the part
that decides whether a 505(b)(2) is possible at all, it changes monthly,
and it is the one thing this tool refuses to guess.

Get the files:

    https://www.fda.gov/drugs/drug-approvals-and-databases/approved-drug-products-therapeutic-equivalence-evaluations-orange-book
    -> "Orange Book Data Files" -> unzip into data/orange_book/

You want three pipe-delimited files out of that zip:

    products.txt      ingredient, route, application number, approval date
    patent.txt        patent numbers and expiry dates per application
    exclusivity.txt   exclusivity codes and dates per application

Then:

    python3 -m ingest.orange_book

Biologics are not in the Orange Book. They are in the Purple Book, which
ships as a separate file with a different shape, so anything marked
`biologic` in the seed will come back unmatched here and say so rather
than silently reading as patent-free.
"""

from __future__ import annotations

import csv
import re
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

from core.model import Field
from ingest.store import load, save

OB_DIR = Path(__file__).resolve().parents[1] / "data" / "orange_book"

# Salt and ester forms the Orange Book spells out and the seed often does
# not, stripped so "enoxaparin sodium" matches "ENOXAPARIN SODIUM" and
# "enoxaparin" alike.
SALTS = (
    "sodium", "hydrochloride", "hcl", "acetate", "sulfate", "succinate",
    "tartrate", "maleate", "mesylate", "citrate", "phosphate", "besylate",
    "bromide", "chloride", "calcium", "potassium", "palmitate", "decanoate",
    "lauroxil", "cypionate", "enanthate", "caproate", "fumarate",
)


def _norm(name: str) -> str:
    """Normalise an ingredient name for matching.

    The Orange Book is uppercase, uses semicolons for combinations, and
    spells out salt forms. None of that is meaningful for identifying the
    active moiety, so it comes off.
    """
    n = name.lower().strip()
    n = re.sub(r"\s*;\s*", " / ", n)
    n = re.sub(r"[^a-z0-9/ ]+", " ", n)
    words = [w for w in n.split() if w and w not in SALTS]
    return " ".join(words)


def _parse_date(raw: str) -> date | None:
    """Orange Book dates come in a few shapes, and some are not dates.

    Patent expiry is sometimes blank, and approval date is sometimes the
    literal text "Approved Prior to Jan 1, 1982", which is information but
    not a date.
    """
    raw = (raw or "").strip()
    if not raw or raw.lower().startswith("approved prior"):
        return None
    for fmt in ("%b %d, %Y", "%Y-%m-%d", "%m/%d/%Y", "%d-%b-%y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _read(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(path)
    with open(path, newline="", encoding="utf-8", errors="replace") as fh:
        return list(csv.DictReader(fh, delimiter="~" if "~" in
                                   open(path, encoding="utf-8",
                                        errors="replace").readline() else "|"))


def build_index(ob_dir: Path = OB_DIR) -> dict:
    """Index the three files by normalised ingredient name.

    Returns, per ingredient: the application numbers, the latest patent
    expiry across them, and the latest exclusivity date.
    """
    products = _read(ob_dir / "products.txt")
    patents = _read(ob_dir / "patent.txt")
    excl = _read(ob_dir / "exclusivity.txt")

    # application number -> set of normalised ingredient names
    by_appl: dict[str, set[str]] = defaultdict(set)
    appl_of: dict[str, set[str]] = defaultdict(set)
    for row in products:
        ing = _norm(row.get("Ingredient", ""))
        appl = (row.get("Appl_No") or "").strip()
        if not ing or not appl:
            continue
        by_appl[appl].add(ing)
        appl_of[ing].add(appl)

    patent_by_appl: dict[str, list[date]] = defaultdict(list)
    for row in patents:
        appl = (row.get("Appl_No") or "").strip()
        # A delisted patent no longer blocks anything, so it must not count
        # toward the latest expiry. Including it would push the date out and
        # make a clear path look blocked.
        if (row.get("Delist_Flag") or "").strip():
            continue
        d = _parse_date(row.get("Patent_Expire_Date_Text", ""))
        if appl and d:
            patent_by_appl[appl].append(d)

    excl_by_appl: dict[str, list[date]] = defaultdict(list)
    for row in excl:
        appl = (row.get("Appl_No") or "").strip()
        d = _parse_date(row.get("Exclusivity_Date", ""))
        if appl and d:
            excl_by_appl[appl].append(d)

    index: dict[str, dict] = {}
    for ing, appls in appl_of.items():
        pats = [d for a in appls for d in patent_by_appl.get(a, [])]
        exs = [d for a in appls for d in excl_by_appl.get(a, [])]
        index[ing] = {
            "application_numbers": sorted(appls),
            "latest_patent_expiry": max(pats) if pats else None,
            "latest_exclusivity_expiry": max(exs) if exs else None,
            "patent_rows": len(pats),
        }
    return index


def apply_index(candidates, index: dict) -> dict:
    """Write the dates onto the candidates, and report what missed.

    A candidate the index does not contain keeps its empty fields. It does
    not get a default, and it does not get dropped. The report says which
    ones missed so the gap is visible rather than inferred from a score
    that came out lower than expected.
    """
    matched, unmatched, no_patents = [], [], []

    for c in candidates:
        key = _norm(c.generic_name)
        hit = index.get(key)
        if hit is None:
            # try the first word, which catches "octreotide acetate" against
            # an index entry of just "octreotide"
            first = key.split()[0] if key else ""
            hit = index.get(first)
        if hit is None:
            unmatched.append(c.generic_name)
            continue

        c.application_numbers = hit["application_numbers"]
        if hit["latest_patent_expiry"]:
            c.latest_patent_expiry = Field(
                hit["latest_patent_expiry"].isoformat(), "orange_book")
        else:
            # Matched the product but it carries no listed patents. That is
            # a real finding — it usually means the patents lapsed — but it
            # is recorded as its own thing, not as a blank, so the score can
            # treat "known to have none" differently from "never looked".
            c.latest_patent_expiry = Field(date(1970, 1, 1).isoformat(),
                                           "orange_book")
            no_patents.append(c.generic_name)
        if hit["latest_exclusivity_expiry"]:
            c.latest_exclusivity_expiry = Field(
                hit["latest_exclusivity_expiry"].isoformat(), "orange_book")
        matched.append(c.generic_name)

    return {"matched": matched, "unmatched": unmatched, "no_patents": no_patents}


if __name__ == "__main__":
    ob_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else OB_DIR
    try:
        index = build_index(ob_dir)
    except FileNotFoundError as e:
        print(f"missing {e}")
        print(__doc__)
        raise SystemExit(1)

    candidates = load()
    if not candidates:
        print("no candidates loaded. run `python3 -m ingest.seed` first.")
        raise SystemExit(1)

    report = apply_index(candidates, index)
    path = save(candidates)

    print(f"indexed {len(index)} ingredients from {ob_dir}")
    print(f"  matched    {len(report['matched'])} of {len(candidates)}")
    print(f"  no listed patents  {len(report['no_patents'])}"
          f"  (recorded as expired, not as unknown)")
    if report["unmatched"]:
        print(f"  unmatched  {len(report['unmatched'])}:")
        for n in report["unmatched"]:
            print(f"    {n}")
        print("  biologics are in the Purple Book, not here, so those are "
              "expected to miss")
    print(f"-> {path}")
