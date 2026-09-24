"""
Every function returns a list of dicts:
{source, title, company, country, city, remote, url, description, salary, posted_at}
Only live postings from real APIs. Nothing is generated.
"""
import os, requests
from datetime import datetime, timedelta, timezone
from .core import CONFIG, ALL_COUNTRIES, detect_platform

ADZUNA_COUNTRIES = {"GB": "gb", "US": "us", "AU": "au", "DE": "de", "FR": "fr", "ES": "es",
                    "CH": "ch", "NL": "nl", "AT": "at", "BE": "be", "IT": "it", "PL": "pl"}
JOOBLE_LOCATIONS = {
    "AE": "United Arab Emirates", "SA": "Saudi Arabia", "QA": "Qatar", "OM": "Oman",
    "KW": "Kuwait", "BH": "Bahrain", "IE": "Ireland", "SE": "Sweden", "DK": "Denmark",
    "GB": "United Kingdom", "DE": "Germany", "AU": "Australia", "US": "United States",
    "FR": "France", "ES": "Spain", "CH": "Switzerland", "NL": "Netherlands",
}
MAX_AGE = timedelta(days=CONFIG["matching"]["max_job_age_days"])


def _fresh(posted) -> bool:
    if not posted:
        return True
    try:
        dt = datetime.fromisoformat(str(posted).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - dt <= MAX_AGE
    except Exception:
        return True


def adzuna(roles) -> list:
    app_id, key = os.getenv("ADZUNA_APP_ID"), os.getenv("ADZUNA_APP_KEY")
    if not app_id:
        return []
    out = []
    for iso, cc in ADZUNA_COUNTRIES.items():
        if iso not in ALL_COUNTRIES:
            continue
        for role in roles:
            try:
                r = requests.get(
                    f"https://api.adzuna.com/v1/api/jobs/{cc}/search/1",
                    params={"app_id": app_id, "app_key": key, "what": role,
                            "results_per_page": 20, "max_days_old": MAX_AGE.days,
                            "content-type": "application/json"}, timeout=20)
                for j in r.json().get("results", []):
                    out.append({
                        "source": "adzuna", "title": j["title"],
                        "company": j.get("company", {}).get("display_name", ""),
                        "country": iso,
                        "city": j.get("location", {}).get("area", [None, None])[-1],
                        "remote": False, "url": j["redirect_url"],
                        "description": j.get("description", ""),
                        "salary": f'{j.get("salary_min","")}-{j.get("salary_max","")}'.strip("-"),
                        "posted_at": j.get("created"),
                    })
            except Exception as e:
                print("adzuna error", cc, role, e)
    return out


def jooble(roles) -> list:
    key = os.getenv("JOOBLE_API_KEY")
    if not key:
        return []
    out = []
    for iso, loc in JOOBLE_LOCATIONS.items():
        if iso not in ALL_COUNTRIES:
            continue
        for role in roles:
            try:
                r = requests.post(f"https://jooble.org/api/{key}",
                                  json={"keywords": role, "location": loc, "page": 1}, timeout=20)
                for j in r.json().get("jobs", []):
                    if not _fresh(j.get("updated")):
                        continue
                    out.append({
                        "source": "jooble", "title": j["title"], "company": j.get("company", ""),
                        "country": iso, "city": j.get("location", ""), "remote": False,
                        "url": j["link"], "description": j.get("snippet", ""),
                        "salary": j.get("salary", ""), "posted_at": j.get("updated"),
                    })
            except Exception as e:
                print("jooble error", loc, role, e)
    return out


def arbeitnow(roles) -> list:
    """German/EU jobs; has an explicit visa_sponsorship flag."""
    out = []
    try:
        for page in (1, 2, 3):
            r = requests.get("https://www.arbeitnow.com/api/job-board-api",
                             params={"page": page}, timeout=20).json()
            for j in r.get("data", []):
                if not any(role.split()[0].lower() in j["title"].lower() for role in roles):
                    continue
                out.append({
                    "source": "arbeitnow", "title": j["title"], "company": j["company_name"],
                    "country": "DE", "city": j.get("location", ""), "remote": j.get("remote", False),
                    "url": j["url"], "description": j.get("description", ""), "salary": "",
                    "posted_at": datetime.fromtimestamp(j["created_at"], tz=timezone.utc).isoformat(),
                    "visa_flag": bool(j.get("visa_sponsorship")),
                })
    except Exception as e:
        print("arbeitnow error", e)
    return out


def remotive(roles) -> list:
    out = []
    try:
        for cat in ("data", "business", "customer-support", "software-dev"):
            r = requests.get("https://remotive.com/api/remote-jobs", params={"category": cat}, timeout=20).json()
            for j in r.get("jobs", []):
                if not any(role.split()[0].lower() in j["title"].lower() for role in roles):
                    continue
                out.append({
                    "source": "remotive", "title": j["title"], "company": j["company_name"],
                    "country": "REMOTE", "city": j.get("candidate_required_location", "Worldwide"),
                    "remote": True, "url": j["url"], "description": j.get("description", ""),
                    "salary": j.get("salary", ""), "posted_at": j.get("publication_date"),
                })
    except Exception as e:
        print("remotive error", e)
    return out


def fetch_all() -> list:
    roles = CONFIG["target_roles"]
    jobs = adzuna(roles) + jooble(roles) + arbeitnow(roles) + remotive(roles)
    if CONFIG.get("scraped_sources", {}).get("enabled", True):
        from .sources_scraped import fetch_scraped
        jobs += fetch_scraped()
    for j in jobs:
        j["platform"] = detect_platform(j["url"])
    return jobs
