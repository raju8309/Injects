"""
Hand-checkable tests. Every expected number was worked out on paper before
the code ran, so a failure means the code is wrong, not the test.

Weights add to 100: dosing 28, device gap 24, volume 16, chronic 14,
population 10, patent 8.
"""

from datetime import date

from core.model import Candidate, F, Field
from core.scoring import WEIGHTS, gates, rank, score

TODAY = date(2026, 10, 29)


def cand(**kw) -> Candidate:
    """A fully-known, strong candidate. Tests override one field at a time."""
    base = dict(
        generic_name="testdrug", route="SC", volume_ml=0.5,
        dose_interval_days=1, chronic=True, existing_device="none",
        reconstitution_required=False, population_band="over_5m",
    )
    base.update(kw)
    c = Candidate(generic_name=base.pop("generic_name"))
    for name, value in base.items():
        setattr(c, name, F(value) if value is not None else Field())
    return c


def comp(s: dict, name: str) -> dict:
    return next(k for k in s["components"] if k["name"] == name)


# ----------------------------------- an unknown is never a good value

def test_an_unknown_field_scores_zero_rather_than_the_favourable_value():
    """The one rule that matters.

    A screener does real damage by ranking a drug highly for an absence of
    evidence. A missing device format must not read as "no competition".
    """
    c = cand(existing_device=None)
    s = score(c, TODAY)
    k = comp(s, "device_whitespace")
    assert k["known"] is False
    assert k["points"] == 0.0
    assert "not known" in k["reason"]


def test_missing_fields_lower_confidence_and_the_total_together():
    """Both readings move, and the dashboard shows both.

    `score` is out of the full 100 so unknowns drag it down. `score_of_known`
    is out of what was assessable, which flatters a thin row — which is why
    it is never shown without the confidence figure beside it.
    """
    full = score(cand(), TODAY)
    thin = score(cand(population_band=None, chronic=None), TODAY)
    assert thin["confidence"] < full["confidence"]
    assert thin["score"] < full["score"]
    # on what it could assess, the thin one is still strong
    assert thin["score_of_known"] > thin["score"]


def test_a_candidate_under_the_confidence_floor_is_not_actionable():
    c = cand(volume_ml=None, dose_interval_days=None, chronic=None,
             population_band=None, existing_device=None)
    s = score(c, TODAY)
    assert s["confidence"] < 0.6
    assert s["actionable"] is False


# ------------------------------------------------------------- gates

def test_intravenous_is_a_gate_not_a_low_score():
    """No auto-injector delivers an IV drug at any price."""
    s = score(cand(route="IV"), TODAY)
    assert s["blocked"] is True
    assert s["gates"][0]["gate"] == "route"


def test_volume_past_the_format_is_a_gate():
    s = score(cand(volume_ml=5.0), TODAY)
    assert s["blocked"] is True
    assert any(g["gate"] == "volume" for g in s["gates"])


def test_a_gate_carries_the_source_of_the_value_that_triggered_it():
    """A gate fired from an estimate is weaker than one from a known
    presentation, and the dashboard needs to be able to say which."""
    c = cand()
    c.volume_ml = F(5.0, "estimate")
    g = gates(c)[0]
    assert g["gate"] == "volume"
    assert g["source"] == "estimate"


def test_an_unknown_route_does_not_gate():
    """Not knowing the route is not grounds to rule a drug out.

    Gating on an unknown would silently shrink the list and look like a
    considered exclusion.
    """
    assert gates(cand(route=None)) == []


def test_a_volume_inside_the_format_does_not_gate():
    assert gates(cand(volume_ml=2.0)) == []
    assert gates(cand(volume_ml=2.01)) != []


# -------------------------------------------------------- components

def test_dosing_burden_scales_with_how_often_you_inject():
    daily = comp(score(cand(dose_interval_days=1), TODAY), "dosing_burden")
    weekly = comp(score(cand(dose_interval_days=7), TODAY), "dosing_burden")
    monthly = comp(score(cand(dose_interval_days=30), TODAY), "dosing_burden")
    assert daily["points"] == WEIGHTS["dosing_burden"]      # full marks
    assert daily["points"] > weekly["points"] > monthly["points"]


def test_doses_per_year_is_reported_as_a_whole_number():
    s = score(cand(dose_interval_days=7), TODAY)
    assert s["doses_per_year"] == 52
    assert "52 injections a year" in comp(s, "dosing_burden")["reason"]


def test_an_as_needed_medicine_is_not_scored_as_daily_dosing():
    """A rescue drug can be carried for years and used twice.

    Interval zero means as-needed. Treating that as "very frequent" inverts
    the case: the value of a better rescue device is that a frightened
    bystander can work it, not that anyone is spared injections.
    """
    s = score(cand(dose_interval_days=0), TODAY)
    k = comp(s, "dosing_burden")
    assert s["rescue"] is True
    assert s["doses_per_year"] is None
    assert k["points"] < WEIGHTS["dosing_burden"]
    assert "usability under panic" in k["reason"]


def test_device_whitespace_rewards_an_empty_category():
    none = comp(score(cand(existing_device="none"), TODAY), "device_whitespace")
    syringe = comp(score(cand(existing_device="prefilled_syringe"), TODAY),
                   "device_whitespace")
    auto = comp(score(cand(existing_device="autoinjector"), TODAY),
                "device_whitespace")
    assert none["points"] == WEIGHTS["device_whitespace"]
    assert none["points"] > syringe["points"] > auto["points"]


def test_reconstitution_halves_the_volume_score():
    plain = comp(score(cand(), TODAY), "volume_fit")
    recon = comp(score(cand(reconstitution_required=True), TODAY), "volume_fit")
    assert recon["points"] == plain["points"] / 2
    assert "reconstitut" in recon["reason"]


def test_patent_status_is_unknown_until_the_orange_book_is_loaded():
    """Left blank on purpose. A guessed patent date survives into a meeting."""
    k = comp(score(cand(), TODAY), "pathway_timing")
    assert k["known"] is False
    assert "Orange Book" in k["reason"]


def test_an_expired_patent_scores_full_marks():
    c = cand()
    c.latest_patent_expiry = Field("2019-01-01", "orange_book")
    k = comp(score(c, TODAY), "pathway_timing")
    assert k["points"] == WEIGHTS["pathway_timing"]
    assert "expired" in k["reason"]


def test_a_patent_with_years_left_scores_badly():
    c = cand()
    c.latest_patent_expiry = Field("2036-01-01", "orange_book")
    k = comp(score(c, TODAY), "pathway_timing")
    assert 0 < k["points"] < WEIGHTS["pathway_timing"] / 2


# ------------------------------------------------------------ ranking

def test_the_three_lists_do_not_mix():
    """Rescue, open ground and contested are different decisions.

    Ranking them together buries every rescue candidate under chronic ones
    and calls that an answer.
    """
    rows = [
        cand(generic_name="open-chronic", existing_device="none"),
        cand(generic_name="contested-chronic", existing_device="autoinjector"),
        cand(generic_name="rescue-drug", dose_interval_days=0,
             existing_device="none", chronic=False),
    ]
    r = rank(rows, TODAY)
    assert [s["generic_name"] for s in r["open_ground"]] == ["open-chronic"]
    assert [s["generic_name"] for s in r["contested"]] == ["contested-chronic"]
    assert [s["generic_name"] for s in r["rescue"]] == ["rescue-drug"]


def test_gated_candidates_are_listed_not_dropped():
    """A tool that silently omits things does not get used twice."""
    rows = [cand(generic_name="good"), cand(generic_name="iv-drug", route="IV")]
    r = rank(rows, TODAY)
    names = [s["generic_name"] for s in r["blocked"]]
    assert names == ["iv-drug"]
    assert r["total"] == 2
    assert all(s["generic_name"] != "iv-drug"
               for s in r["open_ground"] + r["contested"] + r["rescue"])


def test_the_biggest_gap_is_reported_so_data_work_can_be_aimed():
    rows = [cand(), cand(), cand()]
    gaps = dict(rank(rows, TODAY)["biggest_gaps"])
    assert gaps["latest_patent_expiry"] == 3


def test_rank_runs_on_nothing_without_falling_over():
    r = rank([], TODAY)
    assert r["total"] == 0
    assert r["open_ground"] == []
    assert r["mean_confidence"] is None


# ------------------------------------------------- round trip and seed

def test_a_candidate_survives_a_round_trip_with_its_provenance():
    c = cand()
    c.population_band = F("over_5m", "estimate")
    back = Candidate.from_json(c.to_json())
    assert back.population_band.source == "estimate"
    assert back.route.source == "seed"
    assert back.known_fraction == c.known_fraction


def test_the_seed_set_scores_without_error_and_splits_sensibly():
    from ingest.seed import seed
    r = rank(seed(), TODAY)
    assert r["total"] >= 40
    assert r["open_ground"] and r["contested"] and r["rescue"] and r["blocked"]
    # every seeded candidate is missing patent status, by design
    assert dict(r["biggest_gaps"])["latest_patent_expiry"] == r["total"]
