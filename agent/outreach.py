"""
Direct email applications.
- find_email(): pulls a recruiter/HR address out of a job description or a pasted hiring post.
- parse_post(): turns a pasted LinkedIn-style hiring post into a job record.
- draft_email(): writes the application email (subject + body) ending with the candidate's name and number.
- send_email(): sends from the candidate's own Gmail via SMTP with the tailored CV (and cover letter) attached.
"""
import os, re, json, smtplib, ssl
from email.message import EmailMessage
from pathlib import Path
from dotenv import load_dotenv
from .core import PROFILE, ask_json, ask_text, job_hash

load_dotenv()

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
SKIP = ("noreply", "no-reply", "donotreply", "example.com", "privacy", "unsubscribe", "support@linkedin", "@indeed", "@adzuna", "@jooble")


def find_email(text: str) -> str | None:
    for m in EMAIL_RE.findall(text or ""):
        low = m.lower()
        if not any(s in low for s in SKIP):
            return m
    return None


PARSE_SYSTEM = """You read a hiring post (often copied from LinkedIn) and return ONLY JSON:
{"title": str, "company": str, "country": "ISO-2 or empty", "city": str, "remote": bool,
 "contact_email": "email in the post or empty", "contact_name": "person to address, or empty",
 "requirements": [str], "description": "clean plain-text version of the post"}
Use only what the post says. Do not guess the country if it isn't stated."""


def parse_post(text: str) -> dict:
    data = ask_json(PARSE_SYSTEM, text[:6000], max_tokens=1500)
    data["contact_email"] = data.get("contact_email") or find_email(text) or ""
    data["source"] = "pasted"
    data["platform"] = "email" if data["contact_email"] else "other"
    data["url"] = ""
    data["country"] = (data.get("country") or "REMOTE" if data.get("remote") else data.get("country") or "XX")
    data["description"] = data.get("description") or text
    data["hash"] = job_hash(data.get("title", ""), data.get("company", ""), data["country"])
    return data


DRAFT_SYSTEM = """Write a short, professional job application email from the candidate to the recruiter.
Rules:
- 120-180 words in the body. Plain text. No markdown, no bullet symbols.
- Open with a greeting using the contact name if given, otherwise "Dear Hiring Team".
- First line names the exact role and where you saw it.
- Two or three sentences of concrete evidence from the profile that match the posting's requirements. Never invent anything.
- Mention that the CV is attached and that the candidate is available for immediate joining and open to relocation / visa sponsorship if relevant.
- End with exactly this signature block on separate lines: candidate name, phone, email.
Return ONLY JSON: {"subject": str, "body": str}"""


def draft_email(job: dict) -> dict:
    user = (f"PROFILE:\n{json.dumps(PROFILE, ensure_ascii=False)}\n\n"
            f"CONTACT NAME: {job.get('contact_name') or ''}\n"
            f"JOB: {job['title']} at {job.get('company') or 'the company'} ({job.get('city') or ''}, {job.get('country')})\n"
            f"WHERE SEEN: {'LinkedIn post' if job.get('source') == 'pasted' else job.get('source', 'job board')}\n\n"
            f"POSTING:\n{(job.get('description') or '')[:5000]}")
    d = ask_json(DRAFT_SYSTEM, user, max_tokens=900)
    sig = f"\n\n{PROFILE['name']}\n{PROFILE['phone']}\n{PROFILE['email']}"
    body = d["body"].rstrip()
    if PROFILE["phone"] not in body:
        body += sig
    return {"subject": d.get("subject") or f"Application for {job['title']} - {PROFILE['name']}", "body": body}


def send_email(to: str, subject: str, body: str, attachments: list[str]) -> str:
    user, pwd = os.getenv("IMAP_USER"), os.getenv("IMAP_PASSWORD")
    if not (user and pwd):
        raise RuntimeError("Gmail app password not set (IMAP_USER / IMAP_PASSWORD in .env)")
    msg = EmailMessage()
    msg["From"] = f"{PROFILE['name']} <{user}>"
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    for path in attachments:
        if path and Path(path).exists():
            p = Path(path)
            mt = "application/pdf" if p.suffix == ".pdf" else "application/octet-stream"
            msg.add_attachment(p.read_bytes(), maintype=mt.split("/")[0], subtype=mt.split("/")[1], filename=p.name)
    if os.getenv("DRY_RUN"):
        return f"DRY_RUN: would email {to}"
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context()) as s:
        s.login(user, pwd)
        s.send_message(msg)
    return f"emailed {to}"
