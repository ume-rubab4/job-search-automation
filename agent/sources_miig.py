"""
Germany job source via the Federal Employment Agency (Bundesagentur für Arbeit) job-search API.

This is the same database that powers make-it-in-germany.com's job listings, read through the agency's public
API (client id "jobboerse-jobsuche") instead of scraping the website, which blocks scripts.
Contact e-mails are taken from the job description text when the employer prints one there.

Run standalone to test:   python -m agent.sources_miig 5
"""
import re, sys, time, base64
import requests
from .core import CONFIG

BASE = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service"
HEADERS = {"X-API-Key": "jobboerse-jobsuche",
           "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/128",
           "Accept": "application/json"}

DEFAULT_QUERIES = ["Data Analyst", "Business Analyst", "Power BI", "AI Engineer", "Machine Learning",
                   "SAP FICO", "SAP FI/CO", "IT Support", "Datenanalyst", "Business Intelligence"]

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
SKIP = ("arbeitsagentur", "noreply", "no-reply", "example.", "datenschutz", "privacy")


def _cfg(key, default):
    return (CONFIG.get("miig") or {}).get(key, default)


def _get(url: str, params: dict | None = None):
    for attempt in range(3):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=30)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (429, 503):
                time.sleep(5 * (attempt + 1)); continue
            return None
        except (requests.RequestException, ValueError):
            time.sleep(2)
    return None


def search(query: str, pages: int, days: int) -> list[dict]:
    out = []
    for page in range(1, pages + 1):
        d = _get(BASE + "/pc/v6/jobs", {"was": query, "page": page, "size": 50, "angebotsart": 1,
                                        "veroeffentlichtseit": days})
        if not d:
            break
        items = d.get("ergebnisliste") or d.get("stellenangebote") or []
        out += items
        if len(items) < 50:
            break
        time.sleep(0.5)
    return out


def details(refnr: str) -> dict | None:
    code = base64.b64encode(refnr.encode()).decode()
    for path in ("/pc/v4/jobdetails/", "/pc/v3/jobdetails/", "/pc/v6/jobdetails/"):
        d = _get(BASE + path + code)
        if d:
            return d
    return None


def find_email(text: str) -> str | None:
    for m in EMAIL_RE.findall(text or ""):
        if not any(s in m.lower() for s in SKIP):
            return m
    return None


def to_job(item: dict, d: dict) -> dict | None:
    refnr = item.get("referenznummer") or item.get("refnr") or d.get("referenznummer")
    title = d.get("stellenangebotsTitel") or item.get("stellenangebotsTitel") or item.get("titel") or d.get("titel")
    company = d.get("firma") or item.get("firma") or item.get("arbeitgeber") or d.get("arbeitgeber") or ""
    if not (refnr and title and company):
        return None
    locs = d.get("stellenlokationen") or item.get("stellenlokationen") or []
    adr = (locs[0].get("adresse") if locs else None) or item.get("arbeitsort") or {}
    land = (adr.get("land") or "DEUTSCHLAND").upper()
    if "DEUTSCH" not in land and land not in ("DE", "GERMANY"):
        return None
    city = adr.get("ort") or ""
    desc = d.get("stellenangebotsBeschreibung") or item.get("stellenangebotsBeschreibung") or ""
    desc = re.sub(r"\n{3,}", "\n\n", desc).strip()
    email = find_email(desc)
    salary = d.get("verguetungsangabe") or item.get("verguetungsangabe") or None
    remote = bool(d.get("homeofficemoeglich") or item.get("homeofficemoeglich"))
    posted = d.get("datumErsteVeroeffentlichung") or item.get("aktuelleVeroeffentlichungsdatum") or ""
    url = f"https://www.arbeitsagentur.de/jobsuche/jobdetail/{refnr}"
    header = (f"Source: German Federal Employment Agency job board (arbeitsagentur.de / Make it in Germany)\n"
              f"Reference: {refnr} | Posted: {posted[:10]} | Home office: {'yes' if remote else 'not stated'}\n"
              f"Location: {city}, Germany" + (f" | Salary: {salary}" if isinstance(salary, str) else "") + "\n"
              + (f"Contact e-mail found in posting: {email}\n" if email else "") + "\n")
    return {
        "source": "make-it-in-germany",
        "platform": "email" if email else "other",
        "title": title.strip(),
        "company": company.strip(),
        "country": "DE",
        "city": city,
        "remote": remote,
        "url": url,
        "description": header + desc,
        "salary": salary if isinstance(salary, str) else None,
        "contact_email": email,
        "contact_name": None,
        "visa_flag": True,
    }


def fetch() -> list[dict]:
    if not _cfg("enabled", True):
        return []
    queries = _cfg("queries", None) or list(dict.fromkeys(list(CONFIG.get("target_roles", [])) + DEFAULT_QUERIES))
    pages = int(_cfg("pages_per_query", 1))
    days = int(_cfg("days", 14))
    max_jobs = int(_cfg("max_jobs_per_run", 80))

    seen, items = set(), []
    for q in queries:
        for it in search(q, pages, days):
            ref = it.get("referenznummer") or it.get("refnr")
            if ref and ref not in seen:
                seen.add(ref); items.append(it)
    print(f"germany (BA API): {len(items)} listings from {len(queries)} searches")
    jobs = []
    for it in items[:max_jobs]:
        ref = it.get("referenznummer") or it.get("refnr")
        d = details(ref) or {}
        j = to_job(it, d)
        if j:
            jobs.append(j)
        time.sleep(0.4)
    with_mail = sum(1 for j in jobs if j["contact_email"])
    print(f"germany (BA API): parsed {len(jobs)} jobs, {with_mail} with a contact e-mail in the posting")
    return jobs


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    CONFIG.setdefault("miig", {})["max_jobs_per_run"] = limit
    for j in fetch():
        print(f"\n{j['title']} — {j['company']} ({j['city']})  email={j['contact_email']}  remote={j['remote']}")
        print("  ", j["url"])
        print("  ", j["description"][:300].replace("\n", " | "))ss