"""
A starter set of real marketed injectables.

Scope of what is in here, stated plainly because a screening tool is only
as honest as its inputs:

  * **route, existing device format, chronic or acute, reconstitution** —
    these are stable, well-known properties of the marketed product. Tagged
    `seed`.
  * **dose volume** — tagged `seed` only where the product ships as one
    fixed presentation (an EpiPen is 0.3 mL and always has been). Tagged
    `estimate` wherever presentations vary by dose or strength, which is
    most of them.
  * **patient population** — tagged `estimate` throughout. These are bands,
    not counts, because a precise figure here would be invented.
  * **patent and exclusivity expiry** — deliberately left empty. Run
    `ingest/orange_book.py` against the FDA source files to fill them. A
    guessed patent date is worse than a blank one: the whole 505(b)(2)
    question turns on it, and a plausible wrong date survives all the way
    into a meeting.

So the rankings this produces out of the box are directional. They tell you
where to look, not what to file. The dashboard says so, and every row
carries the fraction of its score that came from known inputs.

    python3 -m ingest.seed
"""

from __future__ import annotations

from core.model import Candidate, F
from ingest.store import save


def _c(name, brands, area, route, vol, vol_src, interval, chronic,
       device, *, modality="small_molecule", recon=False, cold=False,
       pop="50k_500k", self_admin=True, note="") -> Candidate:
    return Candidate(
        generic_name=name,
        brand_examples=brands,
        therapy_area=area,
        modality=F(modality),
        route=F(route),
        volume_ml=F(vol, vol_src),
        dose_interval_days=F(interval),
        chronic=F(chronic),
        self_administered=F(self_admin),
        existing_device=F(device),
        reconstitution_required=F(recon),
        cold_chain=F(cold),
        population_band=F(pop, "estimate"),
        note=note,
    )


def seed() -> list[Candidate]:
    return [
        # ---------------------------------------------- open device ground
        _c("octreotide acetate", ["Sandostatin"], "endocrine / neuroendocrine",
           "SC", 1.0, "estimate", 1 / 3, True, "none", modality="peptide",
           cold=True, pop="under_50k",
           note="three injections a day from a vial, which is about as much "
                "injection burden as a chronic therapy carries"),
        _c("enfuvirtide", ["Fuzeon"], "HIV", "SC", 1.0, "estimate", 0.5, True,
           "none", modality="peptide", recon=True, pop="under_50k",
           note="twice daily, reconstituted each time; small population but "
                "the worst routine in the category"),
        _c("cyanocobalamin", ["vitamin B12"], "haematology",
           "IM", 1.0, "estimate", 30, True, "none", pop="over_5m",
           note="very large population, very cheap drug; the question is "
                "whether a device is worth it at this price point"),
        _c("haloperidol decanoate", ["Haldol Decanoate"], "psychiatry",
           "IM", 1.0, "estimate", 28, True, "none", self_admin=False,
           note="long-acting antipsychotic, clinic administered from a vial"),
        _c("testosterone cypionate", ["Depo-Testosterone"], "endocrine",
           "IM", 1.0, "estimate", 14, True, "none", pop="500k_5m",
           note="vial and syringe; a separate SC auto-injector product exists "
                "but this presentation has no device"),
        _c("bortezomib", ["Velcade"], "oncology / myeloma",
           "SC", 1.4, "estimate", 7, True, "none", recon=True,
           self_admin=False, pop="under_50k",
           note="reconstituted and clinic administered"),
        _c("leuprolide acetate", ["Lupron Depot", "Eligard"],
           "oncology / endometriosis", "IM", 1.0, "estimate", 28, True, "none",
           modality="peptide", recon=True, self_admin=False,
           note="supplied as a kit needing reconstitution before every dose"),
        _c("triptorelin", ["Trelstar"], "oncology", "IM", 2.0, "estimate", 28,
           True, "none", modality="peptide", recon=True, self_admin=False,
           pop="under_50k"),

        # ------------------------------------------- partly solved already
        _c("enoxaparin sodium", ["Lovenox"], "anticoagulation",
           "SC", 0.4, "estimate", 1, True, "prefilled_syringe", pop="500k_5m",
           note="prefilled syringe with a visible needle; extended "
                "prophylaxis and cancer-associated thrombosis run for months"),
        _c("fondaparinux sodium", ["Arixtra"], "anticoagulation",
           "SC", 0.5, "estimate", 1, True, "prefilled_syringe"),
        _c("methylnaltrexone bromide", ["Relistor"], "gastroenterology",
           "SC", 0.4, "estimate", 2, True, "prefilled_syringe", pop="under_50k"),
        _c("paliperidone palmitate", ["Invega Sustenna"], "psychiatry",
           "IM", 1.5, "estimate", 28, True, "prefilled_syringe",
           self_admin=False),
        _c("medroxyprogesterone acetate", ["Depo-Provera", "depo-subQ 104"],
           "contraception", "SC", 0.65, "seed", 91, True, "prefilled_syringe",
           pop="500k_5m"),
        _c("cabotegravir / rilpivirine", ["Cabenuva"], "HIV",
           "IM", 2.0, "seed", 28, True, "prefilled_syringe", modality="biologic",
           cold=True, self_admin=False, pop="under_50k",
           note="two separate intramuscular injections per visit, at the top "
                "of what an auto-injector format can hold"),
        _c("peginterferon alfa-2a", ["Pegasys"], "hepatology",
           "SC", 0.5, "estimate", 7, True, "prefilled_syringe",
           modality="biologic", cold=True, pop="under_50k"),
        _c("filgrastim", ["Neupogen", "Zarxio"], "oncology support",
           "SC", 0.5, "estimate", 1, False, "prefilled_syringe",
           modality="biologic", cold=True,
           note="given as a course after chemotherapy rather than chronically"),
        _c("ustekinumab", ["Stelara"], "immunology",
           "SC", 1.0, "estimate", 84, True, "prefilled_syringe",
           modality="biologic", cold=True),

        # ------------------------------------------------- crowded already
        _c("methotrexate", ["Otrexup", "Rasuvo"], "rheumatology",
           "SC", 0.4, "estimate", 7, True, "autoinjector", pop="500k_5m"),
        _c("glatiramer acetate", ["Copaxone"], "multiple sclerosis",
           "SC", 1.0, "seed", 2, True, "autoinjector", modality="peptide",
           cold=True),
        _c("interferon beta-1a", ["Avonex"], "multiple sclerosis",
           "IM", 0.5, "seed", 7, True, "pen", modality="biologic", cold=True),
        _c("interferon beta-1b", ["Betaseron", "Extavia"], "multiple sclerosis",
           "SC", 1.0, "seed", 2, True, "autoinjector", modality="biologic",
           recon=True),
        _c("adalimumab", ["Humira"], "immunology",
           "SC", 0.8, "estimate", 14, True, "autoinjector", modality="biologic",
           cold=True, pop="500k_5m"),
        _c("etanercept", ["Enbrel"], "immunology",
           "SC", 1.0, "estimate", 7, True, "autoinjector", modality="biologic",
           cold=True, pop="500k_5m"),
        _c("dupilumab", ["Dupixent"], "immunology",
           "SC", 2.0, "estimate", 14, True, "autoinjector", modality="biologic",
           cold=True, pop="500k_5m"),
        _c("secukinumab", ["Cosentyx"], "immunology",
           "SC", 1.0, "estimate", 28, True, "autoinjector", modality="biologic",
           cold=True),
        _c("tocilizumab", ["Actemra"], "rheumatology",
           "SC", 0.9, "estimate", 7, True, "autoinjector", modality="biologic",
           cold=True),
        _c("golimumab", ["Simponi"], "rheumatology",
           "SC", 0.5, "estimate", 28, True, "autoinjector", modality="biologic",
           cold=True),
        _c("semaglutide", ["Ozempic", "Wegovy"], "diabetes / obesity",
           "SC", 0.5, "estimate", 7, True, "pen", modality="peptide",
           cold=True, pop="over_5m"),
        _c("dulaglutide", ["Trulicity"], "diabetes",
           "SC", 0.5, "seed", 7, True, "autoinjector", modality="peptide",
           cold=True, pop="over_5m"),
        _c("liraglutide", ["Victoza", "Saxenda"], "diabetes / obesity",
           "SC", 0.4, "estimate", 1, True, "pen", modality="peptide",
           cold=True, pop="over_5m"),
        _c("insulin glargine", ["Lantus", "Basaglar"], "diabetes",
           "SC", 0.3, "estimate", 1, True, "pen", modality="biologic",
           cold=True, pop="over_5m"),
        _c("teriparatide", ["Forteo"], "osteoporosis",
           "SC", 0.08, "seed", 1, True, "pen", modality="peptide", cold=True),
        _c("abaloparatide", ["Tymlos"], "osteoporosis",
           "SC", 0.08, "seed", 1, True, "pen", modality="peptide", cold=True,
           pop="under_50k"),
        _c("somatropin", ["Norditropin", "Genotropin"], "endocrine",
           "SC", 0.3, "estimate", 1, True, "pen", modality="biologic",
           cold=True),
        _c("denosumab", ["Prolia"], "osteoporosis",
           "SC", 1.0, "seed", 182, True, "prefilled_syringe",
           modality="biologic", cold=True, pop="500k_5m",
           note="twice a year, so there is very little adherence burden for "
                "a device to remove"),
        _c("pegfilgrastim", ["Neulasta"], "oncology support",
           "SC", 0.6, "seed", 21, False, "on_body", modality="biologic",
           cold=True),
        _c("testosterone enanthate", ["Xyosted"], "endocrine",
           "SC", 0.5, "seed", 7, True, "autoinjector", pop="500k_5m"),

        # ------------------------------------------------ rescue and acute
        _c("naloxone hydrochloride", ["Evzio (withdrawn)"], "opioid overdose",
           "IM", 0.4, "estimate", 0, False, "none", pop="over_5m",
           note="the auto-injector that existed was withdrawn; mostly nasal "
                "spray or a vial and syringe now"),
        _c("epinephrine", ["EpiPen", "Auvi-Q"], "anaphylaxis",
           "IM", 0.3, "seed", 0, False, "autoinjector", pop="over_5m",
           note="several competing auto-injectors already"),
        _c("sumatriptan succinate", ["Imitrex STATdose"], "migraine",
           "SC", 0.5, "seed", 0, False, "autoinjector", pop="500k_5m"),
        _c("glucagon", ["Gvoke", "Baqsimi"], "severe hypoglycaemia",
           "SC", 0.2, "seed", 0, False, "autoinjector", modality="peptide",
           pop="500k_5m"),
        _c("apomorphine hydrochloride", ["Apokyn"], "Parkinson's disease",
           "SC", 0.3, "estimate", 1 / 3, True, "pen", pop="under_50k",
           note="rescue dosing several times a day, so it carries chronic "
                "burden despite being an as-needed medicine"),

        # -------------------------------------- gated: volume or route
        _c("naltrexone for extended-release injectable suspension", ["Vivitrol"],
           "substance use disorder", "IM", 4.0, "seed", 28, True, "none",
           recon=True, self_admin=False,
           note="4 mL, past the format, and needs reconstituting"),
        _c("aripiprazole lauroxil", ["Aristada"], "psychiatry",
           "IM", 2.4, "seed", 42, True, "prefilled_syringe", self_admin=False,
           pop="under_50k"),
        _c("fulvestrant", ["Faslodex"], "oncology / breast",
           "IM", 5.0, "seed", 28, True, "prefilled_syringe", self_admin=False,
           note="two 5 mL intramuscular injections per dose"),
        _c("icatibant", ["Firazyr"], "hereditary angioedema",
           "SC", 3.0, "seed", 0, False, "prefilled_syringe", modality="peptide",
           pop="under_50k"),
        _c("azacitidine", ["Vidaza"], "oncology / MDS",
           "SC", 4.0, "estimate", 1, False, "none", recon=True,
           self_admin=False, pop="under_50k"),
        _c("daratumumab and hyaluronidase", ["Darzalex Faspro"],
           "oncology / myeloma", "SC", 15.0, "seed", 7, True, "none",
           modality="biologic", cold=True, self_admin=False, pop="under_50k",
           note="15 mL by slow subcutaneous push; nowhere near an "
                "auto-injector format"),
        _c("ocrelizumab", ["Ocrevus"], "multiple sclerosis",
           "IV", 300.0, "seed", 182, True, "none", modality="biologic",
           cold=True, self_admin=False,
           note="intravenous infusion, so no injector of any kind applies"),
        _c("infliximab", ["Remicade"], "immunology",
           "IV", 250.0, "seed", 56, True, "none", modality="biologic",
           cold=True, self_admin=False,
           note="intravenous; a separate subcutaneous product exists under a "
                "different application"),
    ]


if __name__ == "__main__":
    from datetime import date

    from core.scoring import rank

    rows = seed()
    path = save(rows)
    r = rank(rows, date.today())

    print(f"{len(rows)} candidates -> {path}")
    print(f"  open ground   {len(r['open_ground'])}  chronic, no device or a syringe only")
    print(f"  contested     {len(r['contested'])}  chronic, a pen or injector exists")
    print(f"  rescue        {len(r['rescue'])}  as-needed, judged on its own terms")
    print(f"  too thin      {len(r['thin'])}")
    print(f"  gated out     {len(r['blocked'])}")
    print(f"  mean confidence {r['mean_confidence']}")
    print()
    print("  OPEN GROUND, best first:")
    for s in r["open_ground"][:8]:
        print(f"    {s['score']:5.1f}  conf {s['confidence']:.2f}  "
              f"{s['generic_name']}")
    print()
    print("  RESCUE, best first:")
    for s in r["rescue"]:
        print(f"    {s['score']:5.1f}  conf {s['confidence']:.2f}  "
              f"{s['generic_name']} ({s['existing_device']})")
    print()
    print("  CONTESTED, best first:")
    for s in r["contested"][:4]:
        print(f"    {s['score']:5.1f}  conf {s['confidence']:.2f}  "
              f"{s['generic_name']} ({s['existing_device']})")
    print()
    print("  biggest data gaps:")
    for name, n in r["biggest_gaps"]:
        print(f"    {n:3d} missing  {name}")
