"""
Job agent API + web UI.   Run:  python api.py   then open http://localhost:8000
"""
import os, sys, json, subprocess, threading
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from agent.core import db, CONFIG, ROOT
from agent import profile_builder, outreach, matcher, documents

app = FastAPI(title="Job agent")
WEB = ROOT / "web" / "dist"
RUNNING: dict = {}


def profile() -> dict:
    return json.loads((ROOT / "data" / "profile.json").read_text())


def all_jobs() -> list:
    rows, start, page = [], 0, 1000
    while True:
        batch = db.table("jobs").select("*").order("found_at", desc=True).range(start, start + page - 1).execute().data
        rows += batch
        if len(batch) < page:
            break
        start += page
    return rows


# ---------------- data ----------------
@app.get("/api/overview")
def overview():
    jobs = all_jobs()
    counts = {}
    for j in jobs:
        counts[j["status"]] = counts.get(j["status"], 0) + 1
    good = [j for j in jobs if j["status"] in ("emailed", "approved", "applied", "package_ready", "shortlisted")]
    by_country, visa = {}, {}
    for j in good:
        by_country[j["country"]] = by_country.get(j["country"], 0) + 1
        v = j.get("visa_status") or "not_mentioned"
        visa[v] = visa.get(v, 0) + 1
    return {"profile": profile(), "counts": counts, "total": len(jobs),
            "by_country": sorted(by_country.items(), key=lambda x: -x[1])[:10], "visa": visa,
            "running": {k: v.poll() is None for k, v in RUNNING.items()},
            "config": {"roles": CONFIG["target_roles"], "countries": CONFIG["countries"]}}


@app.get("/api/jobs")
def jobs():
    slim = ("id", "title", "company", "country", "city", "remote", "url", "salary", "source", "platform",
            "fit_score", "matched_reqs", "missing_reqs", "visa_status", "visa_evidence", "company_size",
            "status", "found_at", "cv_path", "cover_letter_path", "apply_notes", "applied_at", "digest_no",
            "contact_email", "contact_name")
    return [{k: j.get(k) for k in slim} for j in all_jobs()]


@app.get("/api/jobs/{job_id}")
def job(job_id: int):
    rows = db.table("jobs").select("*").eq("id", job_id).execute().data
    if not rows:
        raise HTTPException(404)
    return rows[0]


class Status(BaseModel):
    status: str


@app.post("/api/jobs/{job_id}/status")
def set_status(job_id: int, body: Status):
    if body.status not in ("approved", "skipped", "emailed"):
        raise HTTPException(400, "bad status")
    db.table("jobs").update({"status": body.status}).eq("id", job_id).execute()
    return {"ok": True}


@app.post("/api/jobs/{job_id}/apply")
def apply_now(job_id: int):
    """Applies to one job synchronously (up to ~4 min). Returns the resulting status."""
    r = subprocess.run([sys.executable, "-m", "agent.main", "apply_one", str(job_id)],
                       capture_output=True, text=True, timeout=300, cwd=ROOT)
    rows = db.table("jobs").select("status,apply_notes,url").eq("id", job_id).execute().data
    return {**rows[0], "log": r.stdout[-2000:]}


@app.get("/api/files/{kind}/{job_id}")
def file(kind: str, job_id: int, fmt: str = "pdf"):
    rows = db.table("jobs").select("cv_path,cover_letter_path").eq("id", job_id).execute().data
    if not rows:
        raise HTTPException(404)
    path = rows[0]["cv_path" if kind == "cv" else "cover_letter_path"]
    if not path:
        raise HTTPException(404, "not generated yet")
    p = Path(path)
    if fmt == "docx":
        p = p.with_suffix(".docx")
    if not p.exists():
        raise HTTPException(404, "file missing")
    return FileResponse(p, filename=p.name)


# ---------------- pasted hiring posts & email applications ----------------
class Post(BaseModel):
    text: str


@app.post("/api/paste")
def paste(body: Post):
    """Turn a pasted hiring post (e.g. from LinkedIn) into a scored job with a tailored CV and a draft email."""
    j = outreach.parse_post(body.text)
    if db.table("jobs").select("id").eq("hash", j["hash"]).execute().data:
        raise HTTPException(409, "You already added this post.")
    a = matcher.analyse(j) or {}
    row = {k: j.get(k) for k in ("hash", "source", "platform", "title", "company", "country", "city", "remote", "url",
                                  "description", "contact_email", "contact_name")}
    row.update({"fit_score": a.get("fit_score"), "matched_reqs": a.get("matched_requirements"),
                "missing_reqs": a.get("missing_requirements"), "visa_status": a.get("visa_status") or "not_mentioned",
                "visa_evidence": a.get("visa_evidence"), "company_size": a.get("company_size"),
                "role_family": a.get("role_family"), "status": "emailed"})
    ins = db.table("jobs").insert(row).execute().data[0]
    t = documents.tailor(ins)
    cv = documents.build_cv_docx(ins, t)
    upd = {"cv_path": cv}
    if ins.get("contact_email"):
        d = outreach.draft_email(ins)
        upd.update({"email_subject": d["subject"], "email_body": d["body"]})
    db.table("jobs").update(upd).eq("id", ins["id"]).execute()
    return {**ins, **upd}


class Draft(BaseModel):
    subject: str
    body: str
    to: str | None = None


@app.get("/api/jobs/{job_id}/email")
def email_draft(job_id: int):
    rows = db.table("jobs").select("*").eq("id", job_id).execute().data
    if not rows:
        raise HTTPException(404)
    j = rows[0]
    if not j.get("contact_email"):
        raise HTTPException(400, "This job has no contact email.")
    if not (j.get("email_subject") and j.get("email_body")):
        d = outreach.draft_email(j)
        db.table("jobs").update({"email_subject": d["subject"], "email_body": d["body"]}).eq("id", job_id).execute()
        j.update(email_subject=d["subject"], email_body=d["body"])
    return {"to": j["contact_email"], "subject": j["email_subject"], "body": j["email_body"], "cv_path": j.get("cv_path")}


@app.post("/api/jobs/{job_id}/email")
def email_send(job_id: int, d: Draft):
    rows = db.table("jobs").select("*").eq("id", job_id).execute().data
    if not rows:
        raise HTTPException(404)
    j = rows[0]
    to = d.to or j.get("contact_email")
    if not to:
        raise HTTPException(400, "No recipient")
    if not j.get("cv_path"):
        t = documents.tailor(j); j["cv_path"] = documents.build_cv_docx(j, t)
    try:
        note = outreach.send_email(to, d.subject, d.body, [j["cv_path"], j.get("cover_letter_path")])
    except Exception as e:
        raise HTTPException(500, str(e))
    from datetime import datetime, timezone
    db.table("jobs").update({"status": "applied", "apply_notes": note, "contact_email": to, "cv_path": j["cv_path"],
                             "email_subject": d.subject, "email_body": d.body,
                             "applied_at": datetime.now(timezone.utc).isoformat()}).eq("id", job_id).execute()
    return {"ok": True, "note": note}


# ---------------- actions ----------------
@app.post("/api/run/{mode}")
def run(mode: str):
    if mode not in ("discover", "approvals", "email"):
        raise HTTPException(400)
    if mode in RUNNING and RUNNING[mode].poll() is None:
        return {"ok": False, "message": "already running"}
    os.makedirs(ROOT / "logs", exist_ok=True)
    log = open(ROOT / "logs" / f"{mode}.log", "a")
    RUNNING[mode] = subprocess.Popen([sys.executable, "-m", "agent.main", mode], stdout=log, stderr=subprocess.STDOUT, cwd=ROOT)
    return {"ok": True}


@app.get("/api/logs/{mode}")
def logs(mode: str):
    p = ROOT / "logs" / f"{mode}.log"
    return {"log": p.read_text(errors="ignore")[-4000:] if p.exists() else ""}


# ---------------- profile ----------------
@app.get("/api/profile")
def get_profile():
    return profile()


@app.post("/api/profile/parse")
async def parse_profile(file: UploadFile = File(...)):
    try:
        return profile_builder.build_profile(file.filename, await file.read())
    except Exception as e:
        raise HTTPException(400, str(e))


@app.post("/api/profile/save")
def save_profile(prof: dict):
    profile_builder.save_profile(prof)
    return {"ok": True}


# ---------------- static UI ----------------
if WEB.exists():
    app.mount("/assets", StaticFiles(directory=WEB / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        target = WEB / path
        if path and target.exists() and target.is_file():
            return FileResponse(target)
        return FileResponse(WEB / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)