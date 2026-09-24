import json
from .core import CONFIG, PROFILE, ask_json, MATCH_MODEL

ROLE_KEYWORDS = ["analyst", "power bi", "business intelligence", "bi ", "ai engineer", "ai agent",
                 "machine learning", "sap", "help desk", "helpdesk", "it support", "service desk",
                 "data", "reporting"]

SYSTEM = """You are a strict recruiter assistant. Compare a candidate profile to a job posting.
Return ONLY a JSON object, no prose, no markdown:
{
 "fit_score": 0-100,
 "role_family": "data_analyst|business_analyst|ai_engineer|sap|it_support|other",
 "matched_requirements": [..],
 "missing_requirements": [..],
 "seniority": "entry|junior|mid|senior|lead",
 "visa_status": "stated_yes|stated_no|not_mentioned",
 "visa_evidence": "exact sentence from posting or empty string",
 "company_size": "large|medium|small|unknown",
 "needs_cover_letter": true/false,
 "posting_language": "en|de|fr|es|ar|other",
 "is_real_job": true/false
}
Rules: fit_score reflects how many hard requirements the candidate meets. Senior/lead roles requiring
5+ years score below 40. visa_status is stated_yes only if the posting explicitly says it sponsors
visas / work permits / relocation for international candidates. is_real_job is false for staffing spam,
training-for-fee schemes, or postings with no company name."""


def cheap_prefilter(job: dict) -> bool:
    t = job["title"].lower()
    if not any(k in t for k in ROLE_KEYWORDS):
        return False
    if any(x in t for x in ("senior", "lead", "head of", "director", "principal", "manager")):
        return False
    return True


def analyse(job: dict) -> dict:
    user = (f"CANDIDATE PROFILE:\n{json.dumps(PROFILE, ensure_ascii=False)}\n\n"
            f"JOB POSTING:\nTitle: {job['title']}\nCompany: {job['company']}\n"
            f"Location: {job.get('city')}, {job['country']}\n\n{job['description'][:6000]}")
    try:
        a = ask_json(SYSTEM, user, model=MATCH_MODEL)
    except Exception as e:
        print("analyse error", e)
        return {}
    # Upgrade visa status with known-sponsor list or source flag
    sponsors = [s.lower() for s in CONFIG["visa"]["known_sponsors"]]
    if a.get("visa_status") == "not_mentioned":
        if job.get("visa_flag") or any(s in (job["company"] or "").lower() for s in sponsors):
            a["visa_status"] = "known_sponsor"
    return a


def passes(a: dict) -> bool:
    if not a or not a.get("is_real_job"):
        return False
    if a["fit_score"] < CONFIG["matching"]["min_fit_score"]:
        return False
    if a.get("seniority") not in CONFIG["seniority"] and a.get("seniority") not in ("entry", "junior", "mid"):
        return False
    if CONFIG["visa"]["require_sponsorship"] and a["visa_status"] == "stated_no":
        return False
    return True


def rank_key(row: dict):
    size = {"large": 0, "medium": 1, "unknown": 2, "small": 3}[row.get("company_size") or "unknown"]
    visa = {"stated_yes": 0, "known_sponsor": 1, "not_mentioned": 2}.get(row["visa_status"], 3)
    return (visa, size if CONFIG["prefer_large_companies"] else 0, -row["fit_score"])
