# Job Search Agent (Ume Rubab)

Daily agent that finds real, visa-sponsoring jobs matching your profile across Australia, Europe,
UK, USA and the Gulf, tailors your CV to each country's conventions, writes a cover letter when
needed, emails you a digest, and applies only after you reply APPROVE.

## How it runs

1. **10:00 PKT daily** – fetches live postings from Adzuna, Jooble, Arbeitnow, Remotive, plus LinkedIn, Indeed and Naukrigulf (scraped)
   (real APIs only; every job keeps its original URL, country and city).
2. Cheap keyword pre-filter, then Gemini scores each job against `data/profile.json`:
   fit score, matched/missing requirements, visa sponsorship (`stated_yes` / `known_sponsor` /
   `not_mentioned` / `stated_no`), company size, cover letter needed.
3. Top jobs (default 12) get a tailored ATS-safe CV in the target country's format
   (`agent/country_rules.py`) plus a cover letter where customary (DE/AT/CH/FR or if the posting asks).
4. You receive one email with everything attached. Reply `APPROVE 1,3` / `SKIP 2`.
5. **Every 3 hours** the agent reads your reply. Approved jobs on Greenhouse/Lever/Ashby/Workable
   are auto-applied with Playwright. Anything with a captcha, login or custom questions is marked
   `package_ready` and you get the link + files to finish in one minute.
6. Everything is tracked in Supabase (`jobs` table).

## Setup (about 30 minutes)

1. **Supabase** – create a project, run `db/schema.sql` in the SQL editor, copy the URL and
   service-role key.
2. **API keys** (all free tiers):
   - Google Gemini: https://aistudio.google.com/apikey (default LLM; free tier works for testing,
     enable billing for daily use so your CV data isn't used for training). To use Claude instead,
     set `LLM_PROVIDER=anthropic` and an `ANTHROPIC_API_KEY`.
   - Adzuna: https://developer.adzuna.com (app id + key)
   - Jooble: https://jooble.org/api/about
   - Resend: https://resend.com (verify a sending domain, or use their onboarding address for tests)
   - Gmail App Password for IMAP: Google Account > Security > 2-Step Verification > App passwords
3. Copy `.env.example` to `.env` and fill it in.
4. Before sending anything, fill the placeholders in `data/profile.json` (LinkedIn URL) and add
   your date of birth and a professional photo later for Germany/Switzerland/Gulf CVs
   (the generated files contain `[ADD]` markers where those go).

## Run locally

```bash
pip install -r requirements.txt
playwright install chromium
python -m agent.main discover      # find + match + email digest
python -m agent.main approvals     # read replies and apply
DRY_RUN=1 python -m agent.main approvals   # fills forms but never submits
```

## Run daily on GitHub Actions (free)

Push this folder to a private GitHub repo, add every variable from `.env.example` as a repository
secret (Settings > Secrets and variables > Actions), and the workflow in `.github/workflows/daily.yml`
handles the schedule. Trigger a first run manually from the Actions tab.

## Tuning

- `config.yaml` – roles, countries, `min_fit_score`, `max_jobs_per_day`, known sponsors,
  `apply.mode: auto|package`.
- `agent/country_rules.py` – CV conventions per country.
- `agent/matcher.py` – scoring rules in the system prompt.

## Honest limits

- LinkedIn, Indeed and Naukrigulf have no public job APIs. They are scraped via `python-jobspy`
  (LinkedIn/Indeed) and a small HTML scraper (Naukrigulf) in `agent/sources_scraped.py`. Scrapers
  can break when a site changes layout or rate-limits; the API sources keep working regardless.
  Disable with `scraped_sources.enabled: false` in `config.yaml`. LinkedIn scraping without
  login is capped (roughly a few hundred results per run), so it's run per role and country.
- Auto-apply works on standard ATS forms. Company career portals that require accounts will
  always fall back to `package_ready`.
- The agent never invents anything in your CV; if a job needs a skill you don't have, it appears
  under "Gaps" in the digest so you can decide.
