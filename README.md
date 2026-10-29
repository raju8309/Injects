# Inject Fit

A device company that runs 505(b)(2) and 351(k) programmes has to answer one
question before anything else: **which already-approved injectable is worth
re-presenting in our device?**

That is a ranking problem over public data. It is usually done by hand in a
spreadsheet.

This screens marketed injectables and ranks them, with the reasoning visible for
every row and the provenance attached to every input.

## Run it

```bash
pip install -r requirements.txt
python3 -m ingest.seed
uvicorn api.main:app --reload
```

Open http://localhost:8000

Then fill in patent status from the FDA's own files:

```bash
# download the Orange Book data files, unzip into data/orange_book/
#   https://www.fda.gov/drugs/drug-approvals-and-databases/approved-drug-products-therapeutic-equivalence-evaluations-orange-book
python3 -m ingest.orange_book
```

That import is what turns a directional list into one you could take into a
meeting. Everything else in the seed is a stable property of the marketed
product. Patent status is the part that decides whether the pathway is open at
all, it changes monthly, and it is the one thing this tool refuses to guess.

## What it found

Of 50 seeded injectables:

| | |
|---|---|
| Open ground — chronic, no device or a bare syringe | 18 |
| Contested — chronic, a pen or injector already exists | 20 |
| Rescue — as-needed, judged on its own terms | 4 |
| Ruled out — route or volume the format cannot take | 8 |

**Top of open ground:** enoxaparin, octreotide, fondaparinux, testosterone
cypionate, methylnaltrexone, enfuvirtide.

**Top of rescue: naloxone, by twenty points,** and the only one of the four with
no existing device. That matters as a check on the model rather than as a
finding: it is a programme that has already been built and won an award, and the
tool got there from public facts with no knowledge of it. A screener that agrees
with a decision somebody already made is the best evidence available that it
isn't producing noise.

## The one rule that matters

**A field we do not know scores zero, never the favourable value.**

A screening tool with missing inputs has exactly one dangerous failure mode, and
it is not crashing. It is quietly treating "we don't know" as "no objection" and
ranking a drug highly for an absence of evidence. That score looks identical to a
researched one, and it travels all the way into a diligence meeting before
anybody checks it.

So every field carries a provenance tag — `orange_book`, `seed`, `estimate` or
`unknown` — and every row shows the fraction of its score that came from known
inputs. `/api/provenance` reports the split across the whole set. In the seed
data that is 68% stated product properties, 20% estimates, 12% not known.

## Three lists, not one

This is the same correction made twice, and both times the symptom was a ranking
that looked fine and answered the wrong question.

**Open ground versus contested.** A daily injectable with a mature pen scores
well on injection burden and badly on device gap. Summing those into one figure
buried the only thing that mattered about it — insulin and liraglutide came out
top ten, which for a device company means volunteering to fight Novo and Lilly.
Creating a category and taking share from an incumbent are different decisions
needing different evidence, different partners and different pricing. One ranked
list answers neither.

**Rescue versus chronic.** Fixing the as-needed handling exposed the second
case. A rescue medicine scored against a chronic-adherence rubric can never win
it, because what a better rescue device buys is that a frightened bystander can
work it, not that somebody is spared a hundred injections. Ranked together,
every rescue candidate sinks to the bottom and that gets called an answer.

Scores are comparable inside a list and not across them. The dashboard says so.

## How the score is built

Six components, weighted to 100, set in one place in `core/scoring.py` so they
can be argued with rather than reverse-engineered:

| Component | Weight | What it asks |
|---|---|---|
| Injection burden | 28 | how often the patient injects — a device earns most where injecting happens most |
| Device gap | 24 | is there already a pen or injector for this |
| Volume | 16 | does the dose fit the format comfortably, halved if it needs reconstituting |
| Chronic use | 14 | chronic therapy compounds; rescue is judged on usability instead |
| Population | 10 | how many US patients, as a band rather than an invented count |
| Patent status | 8 | is the reference product clear of patent — Orange Book only |

**Gates** are separate from scores. A drug given intravenously cannot be
delivered by a push-button injector at any price, so it is not a low-scoring
candidate, it is not a candidate. Gated rows are **shown rather than filtered
away**, with the reason and the provenance of the value that triggered it,
because "why isn't X on this list" is the first question anyone asks and a tool
that answers it with silence does not get used twice.

**Candidates under 60% known inputs are held back** rather than mixed into the
ranking. A row built on two facts and six blanks looks exactly like a researched
one.

## Notes on the data

The seed carries only facts that are stable and checkable: route, existing device
format, chronic or acute, whether it needs reconstituting. Dose volume is tagged
`seed` where the product ships as one fixed presentation and `estimate` wherever
presentations vary by strength, which is most of them. Population is a band, not
a count, tagged `estimate` throughout.

Biologics are in the Purple Book rather than the Orange Book, so they come back
unmatched from the import and say so, rather than silently reading as
patent-free.

Delisted patents are excluded from the latest-expiry calculation. Including them
made octreotide read as blocked until 2040 when the live patents run to 2031.

## Layout

```
core/model.py         Candidate and Field — every value carries its source
core/scoring.py       gates, six weighted components, three-way ranking
ingest/seed.py        50 real marketed injectables, honestly tagged
ingest/orange_book.py parses the FDA products, patent and exclusivity files
ingest/store.py       one JSON file on disk, no database
api/main.py           /api/ranking, /api/candidate/{name}, /api/provenance
static/index.html     the dashboard, one file, no build step, no CDN
tests/                22 tests, every expected value worked out on paper first
```

```bash
python3 -m pytest tests/ -q
```

## What this is not

It is a screener, not a diligence pack. It narrows fifty drugs to a handful worth
a closer look. Formulation feasibility, stability in a prefilled format, freedom
to operate, partner appetite and reimbursement are all outside it, and each one
can kill a candidate this tool ranks first.
