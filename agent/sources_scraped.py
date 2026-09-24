"""
LinkedIn / Indeed via python-jobspy, Naukrigulf via HTML scraping.
These sites have no public candidate APIs. Scrapers are best-effort: if one fails it logs and
returns nothing, and the API sources in sources.py still run. Every job keeps its original URL.
"""
import requests, re
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from .core import CONFIG, ALL_COUNTRIES

INDEED_COUNTRY = {"AU": "australia", "DE": "germany", "GB": "uk", "US": "usa", "FR": "france",
                  "ES": "spain", "CH": "switzerland", "NL": "netherlands", "IE": "ireland",
                  "AE": "united arab emirates", "SA": "saudi arabia", "QA": "qatar", "OM": "oman",
                  "KW": "kuwait", "BH": "bahrain", "AT": "austria", "BE": "belgium", "IT": "italy",
                  "SE": "sweden", "DK": "denmark", "PL": "poland"}
LINKEDIN_LOCATION = {"AU": "Australia", "DE": "Germany", "GB": "United Kingdom", "US": "United States",
                     "FR": "France", "ES": "Spain", "CH": "Switzerland", "AE": "United Arab Emirates",
                     "SA": "Saudi Arabia", "QA": "Qatar", "OM": "Oman", "KW": "Kuwait", "BH": "Bahrain",
                     "NL": "Netherlands", "IE": "Ireland"}
NAUKRIGULF_COUNTRY = {"AE": "uae", "SA": "saudi-arabia", "QA": "qatar", "OM": "oman",
                      "KW": "kuwait", "BH": "bahrain"}
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}


def jobspy_linkedin_indeed(roles, per_query: int = 15) -> list:
    try:
        from jobspy import scrape_jobs
    except ImportError:
        print("python-jobspy not installed; skipping LinkedIn/Indeed")
        return []
    out = []
    hours_old = CONFIG["matching"]["max_job_age_days"] * 24
    for iso in ALL_COUNTRIES:
        if iso not in INDEED_COUNTRY:
            continue
        for role in roles:
            try:
                df = scrape_jobs(
                    site_name=["indeed", "linkedin"],
                    search_term=role,
                    location=LINKEDIN_LOCATION.get(iso, INDEED_COUNTRY[iso]),
                    country_indeed=INDEED_COUNTRY[iso],
                    results_wanted=per_query,
                    hours_old=hours_old,
                    linkedin_fetch_description=True,
                    verbose=0,
                )
            except Exception as e:
                print("jobspy error", iso, role, e)
                continue
            for _, r in df.iterrows():
                if not r.get("company") or not r.get("job_url"):
                    continue
                out.append({
                    "source": str(r["site"]), "title": str(r["title"]), "company": str(r["company"]),
                    "country": iso, "city": str(r.get("location") or ""),
                    "remote": bool(r.get("is_remote") or False), "url": str(r["job_url"]),
                    "description": str(r.get("description") or ""),
                    "salary": f'{r.get("min_amount") or ""}-{r.get("max_amount") or ""}'.strip("-"),
                    "posted_at": str(r.get("date_posted") or ""),
                })
    return out


def naukrigulf(roles) -> list:
    """Scrapes Naukrigulf search result pages. Selectors verified Sept 2026; if the site changes,
    update the parsing below (look for job-card <a> tags with '/jobs/' hrefs)."""
    out = []
    for iso, slug in NAUKRIGULF_COUNTRY.items():
        if iso not in ALL_COUNTRIES:
            continue
        for role in roles:
            q = re.sub(r"\s+", "-", role.strip().lower())
            url = f"https://www.naukrigulf.com/{q}-jobs-in-{slug}"
            try:
                html = requests.get(url, headers=HEADERS, timeout=20).text
            except Exception as e:
                print("naukrigulf error", url, e)
                continue
            soup = BeautifulSoup(html, "html.parser")
            for card in soup.select("div.ng-box.srp-tuple, div[class*='srp-tuple'], article"):
                a = card.find("a", href=re.compile(r"/jobs?/|-jobs-"))
                if not a:
                    continue
                title = a.get_text(strip=True)
                comp = card.find(class_=re.compile("info-org|company|org", re.I))
                loc = card.find(class_=re.compile("info-loc|location|loc", re.I))
                desc = card.find(class_=re.compile("description|desc|snippet", re.I))
                link = a["href"]
                if link.startswith("/"):
                    link = "https://www.naukrigulf.com" + link
                if not title or not comp:
                    continue
                out.append({
                    "source": "naukrigulf", "title": title, "company": comp.get_text(strip=True),
                    "country": iso, "city": loc.get_text(strip=True) if loc else "",
                    "remote": False, "url": link,
                    "description": desc.get_text(" ", strip=True) if desc else title,
                    "salary": "", "posted_at": datetime.now(timezone.utc).isoformat(),
                })
    return out


def fetch_scraped() -> list:
    roles = CONFIG["target_roles"]
    return jobspy_linkedin_indeed(roles) + naukrigulf(roles)
