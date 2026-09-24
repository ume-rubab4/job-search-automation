# Job Search Automation Platform

A full-stack system that discovers job postings across multiple countries, scores them against a
candidate profile, generates tailored application documents, and tracks each posting through an
explicit approval-and-application pipeline.

Python · FastAPI · React · PostgreSQL · Docker

---

## What it does

Six external job sources are polled, normalised into a single internal schema, deduplicated, and
filtered. Surviving postings are scored against a structured profile, and matches move through a
state machine from discovery to application — with a human approval step in the middle. A React
dashboard exposes the whole pipeline over a REST API.

Roughly 1,600 postings processed to date across Australia, the EU, the UK, the US and the Gulf.

## Architecture

```
sources ──┐
          ├─► normalise ─► dedupe ─► prefilter ─► score ─► shortlist
Adzuna    │      (hash)              (rules)     (LLM)        │
Arbeitnow │                                                   ▼
Remotive  │                                           generate CV + letter
Jooble    │                                                   │
scrapers  │                                                   ▼
BA API  ──┘                                          approval (email or UI)
                                                              │
                                                              ▼
                                                    auto-apply  or  package_ready
```

| Layer | Technology |
|---|---|
| API | FastAPI, 15+ REST endpoints |
| Frontend | React 19, Vite |
| Database | PostgreSQL (Supabase) |
| Scoring | Gemini via `agent/matcher.py` |
| Documents | python-docx, ReportLab (DOCX + PDF) |
| Delivery | Resend for digests, SMTP/IMAP for applications and replies |
| Packaging | Docker, multi-stage build |

Module layout:

- `agent/sources.py`, `sources_scraped.py`, `sources_miig.py` — source integrations
- `agent/matcher.py` — prefilter, LLM scoring, ranking
- `agent/documents.py` — CV and cover letter generation
- `agent/country_rules.py` — per-country CV conventions
- `agent/applier.py` — ATS form automation
- `agent/outreach.py` — direct email applications
- `agent/main.py` — pipeline orchestration
- `api.py` — REST API and static hosting for the built frontend

## Design decisions

**Three filters before the expensive one.** LLM scoring is the costly step and the free-tier quota
allows 14 requests per minute. Every posting is therefore checked against a content hash, then a
rule-based keyword prefilter, before reaching the model. A `max_to_score_per_run` cap bounds each
run, and postings beyond the cap are deferred to the next run rather than discarded.

**Deduplication by content hash.** Postings are hashed on title, company and country, so the same
role appearing on Adzuna and LinkedIn is stored once. The hash is checked before any processing.

**An explicit state machine rather than boolean flags.** Statuses are `found`, `rejected`,
`shortlisted`, `emailed`, `approved`, `skipped`, `applied`, `package_ready` and `apply_failed`.
Separating them makes the pipeline queryable — every stage can be counted, retried or inspected
independently.

`package_ready` is the important one: the documents exist and the link is known, but automation
could not submit. This happens when the platform is unrecognised, or when the ATS automation ran
and failed. A human finishes those in about a minute.

**Rebuilt the German source against the underlying government API.** The intended source,
make-it-in-germany.com, blocks scripted access behind a web firewall. Rather than work around the
firewall, the integration targets the Bundesagentur für Arbeit REST API, which supplies the same
listings. The detail endpoint requires base64-encoded reference numbers, and postings carry no
contact field, so addresses are extracted from the description text. First run returned 493
listings across 17 search terms.

**Human approval by default.** Nothing is submitted without an explicit approval, given either by
replying to the digest email or through the dashboard. `DRY_RUN=1` fills forms without submitting.

## Running it

With Docker:

```bash
docker build -t job-agent .
docker run -d -p 8000:8000 --env-file .env --name jobagent job-agent
```

Then open http://localhost:8000.

The image is built in two stages — the React frontend compiles in a Node stage that is discarded,
and only the built assets are copied into the Python runtime. Final image: 354 MB.

Without Docker:

```bash
pip install -r requirements.txt
python api.py                       # dashboard on :8000
python -m agent.main discover       # find, score, email digest
python -m agent.main approvals      # read replies and apply
python -m agent.main miig           # German sources
DRY_RUN=1 python -m agent.main approvals   # fills forms, never submits
```

## Setup

1. **Supabase** — create a project, run `db/schema.sql`, copy the project URL and service key.
2. **API keys** (all have free tiers): [Google Gemini](https://aistudio.google.com/apikey),
   [Adzuna](https://developer.adzuna.com), [Jooble](https://jooble.org/api/about),
   [Resend](https://resend.com), and a Gmail app password for IMAP.
3. Copy `.env.example` to `.env` and fill it in.
4. Copy `data/profile.example.json` to `data/profile.json` and populate it, or upload a CV through
   the dashboard to have it parsed.

Configuration lives in `config.yaml`: target roles, countries, `min_fit_score`,
`max_jobs_per_day`, known sponsors, and `apply.mode` (`auto` or `package`).

## Known limitations

- **Scraped sources are fragile.** LinkedIn, Indeed and Naukrigulf have no public APIs and are
  scraped. They break when layouts change and are rate-limited. The API-based sources are
  unaffected, and scrapers can be disabled entirely in `config.yaml`.
- **`apply_failed` is defined but never written.** Every failure path currently resolves to
  `package_ready`, which conflates "automation declined to try" with "automation tried and
  failed". Separating them would make the ATS automation's real success rate measurable.
- **Discovery makes one database round trip per posting** for the duplicate check. Batching these
  into a single query per run would materially reduce latency on large runs.
- **Generated documents and logs are written to the container filesystem** and do not survive a
  restart. Object storage is the correct fix.
- **Auto-apply only works on standard ATS platforms.** Company portals requiring accounts always
  fall back to `package_ready`.
- Nothing is invented in a generated CV. Requirements the profile does not meet are surfaced as
  gaps in the digest rather than papered over.
