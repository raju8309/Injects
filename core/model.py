"""
What a candidate drug is.

The job this models: an approved injectable medicine, and whether it is
worth re-presenting in an auto-injector under FDA's 505(b)(2) or 351(k)
pathway. Those pathways let you build on the reference product's existing
safety data instead of proving a new molecule from scratch, which is why a
device company can run them at all.

The thing this file is really built around is **provenance**. Every field
carries a tag saying where its value came from: the FDA source files, a
curated seed, an estimate, or nothing at all. That matters because a
screening tool with missing inputs has exactly one dangerous failure mode,
and it is not crashing. It is quietly treating "we don't know" as "no
objection" and ranking a drug highly for an absence of evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

# Where a value came from. Ordered weakest to strongest, because the
# dashboard needs to be able to say how much of a score it actually earned.
PROVENANCE = ["unknown", "estimate", "seed", "orange_book", "purple_book"]

# Routes an auto-injector can physically deliver. Intravenous cannot be
# self-administered by any device of this kind, so it is a hard gate rather
# than a low score.
INJECTABLE_ROUTES = ["SC", "IM"]
ALL_ROUTES = INJECTABLE_ROUTES + ["IV", "INTRAVITREAL", "INTRATHECAL", "OTHER"]

# Existing device competition. "none" means vials or ampoules only, which
# is the whitespace worth having.
DEVICE_STATES = ["none", "prefilled_syringe", "pen", "autoinjector", "on_body"]

# Rough US patient population. Bands rather than figures, because a precise
# count would be invented and a band can be defended.
POPULATION_BANDS = ["under_50k", "50k_500k", "500k_5m", "over_5m"]

MODALITIES = ["small_molecule", "biologic", "peptide"]

# What the device can actually hold. Most marketed auto-injectors deliver
# up to 1 mL; 2 mL platforms exist and are becoming normal. Past that you
# are talking about an infusor or an on-body device, not a push-button
# injector, so it is a gate.
DEVICE_VOLUME_COMFORTABLE_ML = 1.0
DEVICE_VOLUME_MAX_ML = 2.0


@dataclass
class Field:
    """A value and where it came from.

    Kept as a wrapper rather than two parallel dicts so a value cannot
    travel through the code without its provenance attached.
    """

    value: object = None
    source: str = "unknown"

    @property
    def known(self) -> bool:
        return self.value is not None and self.source != "unknown"

    @property
    def solid(self) -> bool:
        """Came from an FDA source file rather than a human's judgement."""
        return self.source in ("orange_book", "purple_book")

    def to_json(self) -> dict:
        v = self.value
        if isinstance(v, (date, datetime)):
            v = v.isoformat()
        return {"value": v, "source": self.source}

    @classmethod
    def from_json(cls, d: dict | None) -> "Field":
        if not d:
            return cls()
        return cls(d.get("value"), d.get("source", "unknown"))


def F(value=None, source: str = "seed") -> Field:
    """Shorthand. A value with no source given is unknown, not assumed."""
    if value is None:
        return Field(None, "unknown")
    return Field(value, source)


@dataclass
class Candidate:
    generic_name: str
    brand_examples: list[str] = field(default_factory=list)
    therapy_area: str = ""
    modality: Field = field(default_factory=Field)
    route: Field = field(default_factory=Field)
    volume_ml: Field = field(default_factory=Field)
    dose_interval_days: Field = field(default_factory=Field)
    chronic: Field = field(default_factory=Field)
    self_administered: Field = field(default_factory=Field)
    existing_device: Field = field(default_factory=Field)
    reconstitution_required: Field = field(default_factory=Field)
    cold_chain: Field = field(default_factory=Field)
    population_band: Field = field(default_factory=Field)
    # These two come from the Orange Book and are deliberately left empty in
    # the seed. A guessed patent expiry is worse than a blank one, because
    # the whole pathway question turns on it.
    latest_patent_expiry: Field = field(default_factory=Field)
    latest_exclusivity_expiry: Field = field(default_factory=Field)
    application_numbers: list[str] = field(default_factory=list)
    note: str = ""

    SCORED_FIELDS = (
        "route", "volume_ml", "dose_interval_days", "chronic",
        "existing_device", "reconstitution_required", "population_band",
        "latest_patent_expiry",
    )

    # ------------------------------------------------------------ helpers

    def field_map(self) -> dict[str, Field]:
        return {name: getattr(self, name) for name in self.SCORED_FIELDS}

    @property
    def known_fraction(self) -> float:
        """How much of what the score depends on is actually known.

        Reported next to every score so a confident-looking ranking built
        on three facts and five blanks cannot pass for a researched one.
        """
        fields = self.field_map()
        return sum(1 for f in fields.values() if f.known) / len(fields)

    @property
    def unknown_fields(self) -> list[str]:
        return [n for n, f in self.field_map().items() if not f.known]

    @property
    def as_needed(self) -> bool:
        """Taken when something happens, not on a schedule.

        Stored as an interval of 0. It is not "very frequent" — a rescue
        medicine may be carried for years and used twice, so treating it as
        daily dosing gets the whole case backwards.
        """
        d = self.dose_interval_days
        return d.known and float(d.value) == 0

    @property
    def doses_per_year(self) -> float | None:
        d = self.dose_interval_days
        if not d.known or self.as_needed:
            return None
        return round(365 / float(d.value))

    def years_to_patent_expiry(self, today: date) -> float | None:
        f = self.latest_patent_expiry
        if not f.known:
            return None
        expiry = f.value
        if isinstance(expiry, str):
            expiry = date.fromisoformat(expiry)
        return round((expiry - today).days / 365.25, 1)

    # ---------------------------------------------------------------- json

    def to_json(self) -> dict:
        out = {
            "generic_name": self.generic_name,
            "brand_examples": self.brand_examples,
            "therapy_area": self.therapy_area,
            "application_numbers": self.application_numbers,
            "note": self.note,
        }
        for name in ("modality", "route", "volume_ml", "dose_interval_days",
                     "chronic", "self_administered", "existing_device",
                     "reconstitution_required", "cold_chain", "population_band",
                     "latest_patent_expiry", "latest_exclusivity_expiry"):
            out[name] = getattr(self, name).to_json()
        return out

    @classmethod
    def from_json(cls, d: dict) -> "Candidate":
        c = cls(
            generic_name=d["generic_name"],
            brand_examples=d.get("brand_examples", []),
            therapy_area=d.get("therapy_area", ""),
            application_numbers=d.get("application_numbers", []),
            note=d.get("note", ""),
        )
        for name in ("modality", "route", "volume_ml", "dose_interval_days",
                     "chronic", "self_administered", "existing_device",
                     "reconstitution_required", "cold_chain", "population_band",
                     "latest_patent_expiry", "latest_exclusivity_expiry"):
            setattr(c, name, Field.from_json(d.get(name)))
        return c
