import sys
from datetime import date, datetime, timezone
from .core import db, CONFIG, job_hash
from . import sources, matcher, documents, emailer, applier


def discover_and_shortlist() -> dict:
    raw = sources.fetch_all()
    print(f"fetched {len(raw)} raw postings")
    scored = 0
    new, shortlisted = 0, []
    cap = CONFIG["matching"].get("max_to_score_per_run", 10**9)
    for j in raw:
        if scored >= cap:
            print(f"reached max_to_score_per_run={cap}; remaining jobs will be scored on the next run")
            break
        if not j.get("company") or j["country"] in CONFIG["excluded_countries"]:
            continue
        h = job_hash(j["title"], j["company"], j["country"])
        if db.table("jobs").select("id").eq("hash", h).execute().data:
            continue
        j["hash"] = h
        if not matcher.cheap_prefilter(j):
            j.pop("visa_flag", None)
            db.table("jobs").insert({**j, "status": "rejected"}).execute()
            continue
        a = matcher.analyse(j)
        j.pop("visa_flag", None)
        if not a:
            continue
        scored += 1
        if scored % 10 == 0:
            print(f"scored {scored} jobs, shortlisted {len(shortlisted)} so far")
        row = {**j, "fit_score": a.get("fit_score"), "matched_reqs": a.get("matched_requirements"),
               "missing_reqs": a.get("missing_requirements"), "visa_status": a.get("visa_status"),
               "visa_evidence": a.get("visa_evidence"), "company_size": a.get("company_size"),
               "needs_cover_letter": a.get("needs_cover_letter", False),
               "role_family": a.get("role_family"),
               "status": "shortlisted" if matcher.passes(a) else "rejected"}
        ins = db.table("jobs").insert(row).execute().data[0]
        new += 1
        if row["status"] == "shortlisted":
            shortlisted.append(ins)
    shortlisted.sort(key=matcher.rank_key)
    shortlisted = shortlisted[: CONFIG["matching"]["max_jobs_per_day"]]
    return {"found": new, "shortlisted": shortlisted}


def prepare_and_email(shortlisted: list) -> int:
    if not shortlisted:
        return 0
    today = date.today().isoformat()
    ready, n = [], 0
    for job in shortlisted:
        try:
            t = documents.tailor(job)
            cv = documents.build_cv_docx(job, t)
            cover = documents.build_cover_letter(job, t) if job.get("needs_cover_letter") or job["country"] in ("DE", "AT", "CH", "FR") else None
        except Exception as e:
            print(f"CV generation failed for {job['title']} at {job['company']}: {e}")
            continue
        n += 1
        db.table("jobs").update({"digest_no": n, "digest_date": today, "cv_path": cv,
                                 "cover_letter_path": cover, "status": "emailed"}).eq("id", job["id"]).execute()
        job.update(digest_no=n, cv_path=cv, cover_letter_path=cover)
        ready.append(job)
        print(f"prepared {n}/{len(shortlisted)}: {job['title']} at {job['company']}")
    if ready:
        emailer.send_digest(ready)
    return len(ready)


def email_shortlisted() -> int:
    rows = db.table("jobs").select("*").eq("status", "shortlisted").execute().data
    rows.sort(key=matcher.rank_key)
    rows = rows[: CONFIG["matching"]["max_jobs_per_day"]]
    print(f"{len(rows)} shortlisted jobs waiting for CVs")
    return prepare_and_email(rows)


def read_email_decisions() -> None:
    for digest_date, verb, nums in emailer.read_approvals():
        q = db.table("jobs").select("id").eq("status", "emailed").in_("digest_no", nums)
        if digest_date:
            q = q.eq("digest_date", digest_date)
        for job in q.execute().data:
            db.table("jobs").update({"status": "approved" if verb == "approve" else "skipped"}
                                    ).eq("id", job["id"]).execute()


def apply_jobs(jobs: list, send_report: bool = True) -> int:
    """Apply to the given job rows. Auto-apply where the platform allows; otherwise mark package_ready."""
    applied, report = 0, []
    for job in jobs:
        if not job.get("cv_path"):
            t = documents.tailor(job)
            job["cv_path"] = documents.build_cv_docx(job, t)
            db.table("jobs").update({"cv_path": job["cv_path"]}).eq("id", job["id"]).execute()
        if CONFIG["apply"]["mode"] == "auto" and job["platform"] != "other":
            ok, note = applier.auto_apply(job, job["cv_path"], job.get("cover_letter_path"))
        else:
            ok, note = False, "site needs manual submit; CV is ready"
        status = "applied" if ok else "package_ready"
        db.table("jobs").update({"status": status, "apply_notes": note,
                                 "applied_at": datetime.now(timezone.utc).isoformat() if ok else None}
                                ).eq("id", job["id"]).execute()
        applied += ok
        print(f"{job['title']} at {job['company']}: {status} ({note})")
        report.append(f"<li>{job['title']} at {job['company']}: <b>{status}</b> ({note}) <a href='{job['url']}'>link</a></li>")
    if report and send_report:
        emailer.send_note("Application results", "<ul>" + "".join(report) + "</ul>"
                          "<p>'package_ready' = open the link and submit with the attached CV from the digest.</p>")
    return applied


def apply_approved() -> int:
    rows = db.table("jobs").select("*").eq("status", "approved").execute().data
    return apply_jobs(rows)


def apply_one(job_id: int) -> int:
    rows = db.table("jobs").select("*").eq("id", job_id).execute().data
    if not rows:
        print("job not found"); return 0
    db.table("jobs").update({"status": "approved"}).eq("id", job_id).execute()
    return apply_jobs(rows, send_report=False)


def process_approvals() -> int:
    read_email_decisions()
    return apply_approved()


def run(mode: str = "all", arg: str = None):
    found = short = emailed = applied = 0
    if mode in ("all", "approvals"):
        applied = process_approvals()
    if mode in ("all", "discover"):
        r = discover_and_shortlist()
        found, short = r["found"], len(r["shortlisted"])
        emailed = prepare_and_email(r["shortlisted"])
    if mode == "email":
        emailed = email_shortlisted()
    if mode == "apply_one":
        applied = apply_one(int(arg))
    db.table("runs").insert({"found": found, "shortlisted": short, "emailed": emailed,
                             "applied": applied}).execute()
    print(f"done: found={found} shortlisted={short} emailed={emailed} applied={applied}")


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "all", sys.argv[2] if len(sys.argv) > 2 else None)