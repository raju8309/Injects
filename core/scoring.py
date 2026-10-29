"""
The score, and the reasons for it.

Two layers, deliberately separate.

**Gates** disqualify outright. A drug given intravenously cannot be
delivered by a push-button auto-injector at any price, so it is not a
low-scoring candidate, it is not a candidate. Gates are listed on the
dashboard rather than filtered out silently, because "why isn't X on this
list" is the first question anyone asks.

**Components** score what is left, each returning its own points and its
own sentence. A number with no reason attached is not a screening tool, it
is an oracle, and nobody re-presents a drug on the word of an oracle.

The rule that matters most is in `_component`: **a field we do not know
scores zero, never the favourable value.** Getting that backwards is the
single way a tool like this does real damage — it would rank a drug highly
for the absence of evidence and send someone to a diligence meeting with
it.
"""

from __future__ import annotations

from datetime import date

from core.model import (DEVICE_VOLUME_COMFORTABLE_ML, DEVICE_VOLUME_MAX_ML,
                        INJECTABLE_ROUTES, Candidate)

# Weights, in points. They add to 100 so a score reads as a percentage of
# the best case, and they are here in one place to be argued with rather
# than buried in the functions.
WEIGHTS = {
    "dosing_burden": 28,      # how often the patient has to inject
    "device_whitespace": 24,  # is there already a good device for this
    "volume_fit": 16,         # does the dose fit the format
    "chronic_use": 14,        # chronic therapy is where adherence pays
    "population": 10,         # how many people are on it
    "pathway_timing": 8,      # is the reference product clear of patent
}

# Confidence below this and the ranking is not worth acting on, whatever
# the score says.
CONFIDENCE_FLOOR = 0.6

# Device formats that mean somebody has already built this category. A drug
# with a mature pen ecosystem is not a worse candidate than one with no
# device at all — it is a different business decision, and mixing the two
# into one ranked list answers neither question.
#
# Creating a category where none exists is a product problem. Taking share
# from an incumbent injector is a sales and clinical-preference problem.
# They need different evidence, different partners and different pricing,
# so they get separate lists.
CONTESTED_DEVICES = ("pen", "autoinjector", "on_body")


def _component(name: str, known: bool, fraction: float, reason: str) -> dict:
    """One scored dimension.

    `fraction` is 0..1 of this component's weight. When the input is not
    known it scores zero and says so, rather than defaulting to anything.
    An unknown is not a neutral value and it is certainly not a good one.
    """
    weight = WEIGHTS[name]
    return {
        "name": name,
        "points": round(weight * fraction, 1) if known else 0.0,
        "max_points": weight,
        "known": known,
        "reason": reason,
    }


# ---------------------------------------------------------------- gates

def gates(c: Candidate) -> list[dict]:
    """Reasons this cannot be a candidate at all.

    Each gate says what ruled it out and on what evidence, so a wrong gate
    can be corrected rather than argued with.
    """
    out = []

    route = c.route
    if route.known and route.value not in INJECTABLE_ROUTES:
        out.append({
            "gate": "route",
            "reason": f"given {route.value}, which a push-button injector cannot deliver",
            "source": route.source,
        })

    vol = c.volume_ml
    if vol.known and float(vol.value) > DEVICE_VOLUME_MAX_ML:
        out.append({
            "gate": "volume",
            "reason": f"{vol.value} mL per dose, past the {DEVICE_VOLUME_MAX_ML} mL "
                      f"an auto-injector format holds",
            "source": vol.source,
        })

    return out


# ------------------------------------------------------------ components

def _dosing_burden(c: Candidate) -> dict:
    """More injections means more chances to stop.

    This is the component that carries the most weight, because a device
    that makes injecting easier is worth most where injecting happens
    often. A once-every-six-months drug has almost no adherence problem
    for a device to solve.
    """
    f = c.dose_interval_days
    if not f.known:
        return _component("dosing_burden", False, 0, "dose interval not known")

    if c.as_needed:
        # A rescue medicine can be carried for years and used twice. Scoring
        # that as daily dosing inverts the case: the value of a better
        # device here is that a frightened bystander can work it, not that
        # it saves anyone a hundred injections.
        return _component("dosing_burden", True, 0.35,
                          "as-needed rescue, so the case is usability under "
                          "panic rather than injection frequency")

    days = float(f.value)
    if days <= 1:
        frac, note = 1.0, "daily or more often"
    elif days <= 3:
        frac, note = 0.9, "every few days"
    elif days <= 7:
        frac, note = 0.75, "weekly"
    elif days <= 14:
        frac, note = 0.55, "fortnightly"
    elif days <= 30:
        frac, note = 0.35, "monthly"
    elif days <= 92:
        frac, note = 0.15, "quarterly"
    else:
        frac, note = 0.05, "less than quarterly"

    per_year = c.doses_per_year
    return _component("dosing_burden", True, frac,
                      f"{note}, about {per_year} injections a year")



def _device_whitespace(c: Candidate) -> dict:
    """Is there already a good device for this.

    A drug that already ships in three competing auto-injectors is a fight,
    not an opening. A drug that still ships as a vial and a syringe is the
    opening.
    """
    f = c.existing_device
    if not f.known:
        return _component("device_whitespace", False, 0,
                          "existing device format not known")

    state = f.value
    table = {
        "none": (1.0, "still vials or ampoules, no device at all"),
        "prefilled_syringe": (0.8, "prefilled syringe only, needle still visible"),
        "pen": (0.4, "a pen exists, so the format is partly solved"),
        "autoinjector": (0.15, "an auto-injector already exists"),
        "on_body": (0.1, "an on-body injector already exists"),
    }
    frac, note = table.get(state, (0.0, f"unrecognised device state '{state}'"))
    return _component("device_whitespace", True, frac, note)


def _volume_fit(c: Candidate) -> dict:
    """Does the dose fit the format comfortably, not just barely."""
    f = c.volume_ml
    if not f.known:
        return _component("volume_fit", False, 0, "dose volume not known")

    ml = float(f.value)
    if ml <= DEVICE_VOLUME_COMFORTABLE_ML:
        frac, note = 1.0, f"{ml} mL, comfortably inside the format"
    elif ml <= DEVICE_VOLUME_MAX_ML:
        frac, note = 0.5, f"{ml} mL, needs a large-volume variant"
    else:
        # the gate has already caught this; scoring it zero keeps the
        # component list honest if someone calls scoring without gates
        frac, note = 0.0, f"{ml} mL, past what the format holds"

    penalty = ""
    if c.reconstitution_required.known and c.reconstitution_required.value:
        frac *= 0.5
        penalty = ", and needs reconstituting first"
    return _component("volume_fit", True, frac, note + penalty)


def _chronic_use(c: Candidate) -> dict:
    """Chronic therapy is where a better device compounds.

    A rescue medicine is a different proposition: the value there is speed
    and usability under panic, not adherence. Both are real; they are not
    the same case and should not score the same way.
    """
    f = c.chronic
    if not f.known:
        return _component("chronic_use", False, 0, "chronic or acute not known")
    if f.value:
        return _component("chronic_use", True, 1.0, "chronic therapy, taken for years")
    return _component("chronic_use", True, 0.45,
                      "acute or rescue use, judged on usability rather than adherence")


def _population(c: Candidate) -> dict:
    f = c.population_band
    if not f.known:
        return _component("population", False, 0, "patient population not known")
    table = {
        "over_5m": (1.0, "over 5 million US patients"),
        "500k_5m": (0.75, "roughly 0.5 to 5 million US patients"),
        "50k_500k": (0.45, "roughly 50 to 500 thousand US patients"),
        "under_50k": (0.2, "under 50 thousand US patients"),
    }
    frac, note = table.get(f.value, (0.0, f"unrecognised band '{f.value}'"))
    if f.source == "estimate":
        note += " (estimated, not from a source file)"
    return _component("population", True, frac, note)


def _pathway_timing(c: Candidate, today: date) -> dict:
    """Is the reference product clear of patent.

    Deliberately left unknown in the seed data. A guessed patent expiry is
    worse than a blank one, because the entire 505(b)(2) question turns on
    it, and a plausible wrong date is the kind of thing that survives all
    the way into a meeting.
    """
    f = c.latest_patent_expiry
    if not f.known:
        return _component("pathway_timing", False, 0,
                          "patent status not loaded — run the Orange Book import")

    years = c.years_to_patent_expiry(today)
    if years is None:
        return _component("pathway_timing", False, 0, "patent date unreadable")
    if years <= 0:
        frac, note = 1.0, "patents expired"
    elif years <= 2:
        frac, note = 0.8, f"patents expire in about {years} years"
    elif years <= 5:
        frac, note = 0.45, f"patents expire in about {years} years"
    else:
        frac, note = 0.1, f"patents run another {years} years"
    return _component("pathway_timing", True, frac, note)


# ---------------------------------------------------------------- score

def score(c: Candidate, today: date | None = None) -> dict:
    """Score one candidate, with its gates, components and confidence."""
    today = today or date.today()

    blocked = gates(c)
    components = [
        _dosing_burden(c),
        _device_whitespace(c),
        _volume_fit(c),
        _chronic_use(c),
        _population(c),
        _pathway_timing(c, today),
    ]

    points = sum(k["points"] for k in components)
    available = sum(k["max_points"] for k in components if k["known"])

    # Two readings of the same answer, and the dashboard shows both.
    #
    #   score      - out of the full 100, so unknowns drag it down
    #   score_of_known - out of only what we could assess
    #
    # The second flatters a thinly-documented drug, which is exactly why it
    # is never shown without the confidence figure beside it.
    dev = c.existing_device
    contested = dev.known and dev.value in CONTESTED_DEVICES
    rescue = c.as_needed

    return {
        "generic_name": c.generic_name,
        "brand_examples": c.brand_examples,
        "therapy_area": c.therapy_area,
        "existing_device": dev.value if dev.known else None,
        "contested": contested,
        "rescue": rescue,
        "blocked": bool(blocked),
        "gates": blocked,
        "components": components,
        "score": round(points, 1),
        "score_of_known": round(points / available * 100, 1) if available else None,
        "confidence": round(c.known_fraction, 3),
        "actionable": (not blocked) and c.known_fraction >= CONFIDENCE_FLOOR,
        "unknown_fields": c.unknown_fields,
        "doses_per_year": c.doses_per_year,
        "note": c.note,
    }


def rank(candidates: list[Candidate], today: date | None = None) -> dict:
    """Score everything, then split it four ways.

    Open ground and contested are both ranked, separately, because they are
    different decisions rather than better and worse answers. A daily
    injectable with a mature pen scores well on burden and badly on
    whitespace, and summing those into one figure buries the only thing
    that matters about it.

    Gated candidates are shown rather than dropped, because a tool that
    silently omits things teaches people not to trust it. So does one that
    ranks a drug on two known facts, which is why thin rows are held back
    instead of mixed in.
    """
    today = today or date.today()
    scored = [score(c, today) for c in candidates]

    live = [s for s in scored if s["actionable"]]

    # Three lists, not one, and for the same reason twice over.
    #
    # Fixing the as-needed handling exposed the second case: a rescue
    # medicine scored against a chronic-adherence rubric can never win it,
    # because the thing a better rescue device buys is that a frightened
    # bystander can work it, not that someone is spared a hundred
    # injections. Ranking rescue drugs against chronic ones buries every
    # rescue candidate at the bottom and calls that an answer.
    #
    # So: rescue is judged against rescue, open ground against open ground,
    # and contested against contested. Scores are comparable inside a list
    # and not across them.
    rescue = sorted([s for s in live if s["rescue"]], key=lambda s: -s["score"])
    chronic = [s for s in live if not s["rescue"]]
    open_ground = sorted([s for s in chronic if not s["contested"]],
                         key=lambda s: -s["score"])
    contested = sorted([s for s in chronic if s["contested"]],
                       key=lambda s: -s["score"])

    thin = sorted([s for s in scored if not s["blocked"] and not s["actionable"]],
                  key=lambda s: -s["confidence"])
    blocked = sorted([s for s in scored if s["blocked"]],
                     key=lambda s: s["generic_name"])

    gap_counts: dict[str, int] = {}
    for s in scored:
        for u in s["unknown_fields"]:
            gap_counts[u] = gap_counts.get(u, 0) + 1

    return {
        "generated_at": today.isoformat(),
        "total": len(scored),
        "open_ground": open_ground,
        "contested": contested,
        "rescue": rescue,
        "thin": thin,
        "blocked": blocked,
        "confidence_floor": CONFIDENCE_FLOOR,
        "weights": WEIGHTS,
        # which fields are missing most often, so the next hour of data
        # work goes where it buys the most
        "biggest_gaps": sorted(gap_counts.items(), key=lambda kv: -kv[1]),
        "mean_confidence": round(
            sum(s["confidence"] for s in scored) / len(scored), 3) if scored else None,
    }
