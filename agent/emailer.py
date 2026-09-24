import os, re, imaplib, email, base64
from datetime import date
from dotenv import load_dotenv
import resend

load_dotenv()

resend.api_key = os.getenv("RESEND_API_KEY")
VISA_LABEL = {"stated_yes": "Sponsorship stated in posting", "known_sponsor": "Known sponsor",
              "not_mentioned": "Not mentioned", "stated_no": "No sponsorship"}


def send_digest(rows: list) -> None:
    """rows: shortlisted jobs with digest_no, cv_path, cover_letter_path."""
    today = date.today().isoformat()
    lines = [f"<h2>Job digest - {today}</h2>",
             "<p>Reply to this email with <b>APPROVE 1,3,5</b> and/or <b>SKIP 2,4</b>. "
             "Nothing is submitted until you approve.</p>"]
    attachments = []
    for r in rows:
        lines.append(
            f"<hr><h3>#{r['digest_no']} - {r['title']} at {r['company']}</h3>"
            f"<p><b>Location:</b> {r.get('city') or ''}, {r['country']}"
            f"{' (Remote)' if r.get('remote') else ''}<br>"
            f"<b>Fit score:</b> {r['fit_score']}/100 &nbsp; <b>Company size:</b> {r.get('company_size')}<br>"
            f"<b>Visa:</b> {VISA_LABEL.get(r['visa_status'], r['visa_status'])}"
            f"{(' - ' + r['visa_evidence']) if r.get('visa_evidence') else ''}<br>"
            f"<b>Salary:</b> {r.get('salary') or 'n/a'}<br>"
            f"<b>Apply method:</b> {'auto-apply (' + r['platform'] + ')' if r['platform'] != 'other' else 'package - you submit'}<br>"
            f"<b>Original posting:</b> <a href='{r['url']}'>{r['url']}</a></p>"
            f"<p><b>You match:</b> {', '.join(r.get('matched_reqs') or [])}<br>"
            f"<b>Gaps:</b> {', '.join(r.get('missing_reqs') or []) or 'none'}</p>")
        for path in (r.get("cv_path"), r.get("cover_letter_path")):
            if path and os.path.exists(path):
                attachments.append({"filename": os.path.basename(path),
                                    "content": base64.b64encode(open(path, "rb").read()).decode()})
    resend.Emails.send({
        "from": os.environ["FROM_EMAIL"], "to": [os.environ["TO_EMAIL"]],
        "subject": f"[Job Agent] {len(rows)} jobs need your approval - {today}",
        "html": "\n".join(lines), "attachments": attachments,
    })


def read_approvals() -> list:
    """Scan unread Gmail replies. Returns [(date, 'approve'|'skip', [numbers])]."""
    user, pwd = os.getenv("IMAP_USER"), os.getenv("IMAP_PASSWORD")
    if not (user and pwd):
        return []
    decisions = []
    m = imaplib.IMAP4_SSL("imap.gmail.com")
    m.login(user, pwd)
    m.select("INBOX")
    _, ids = m.search(None, '(UNSEEN SUBJECT "[Job Agent]")')
    for i in ids[0].split():
        _, data = m.fetch(i, "(RFC822)")
        msg = email.message_from_bytes(data[0][1])
        body = ""
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                body += part.get_payload(decode=True).decode(errors="ignore")
        dt = re.search(r"(\d{4}-\d{2}-\d{2})", msg.get("Subject", ""))
        digest_date = dt.group(1) if dt else None
        for verb in ("APPROVE", "SKIP"):
            for match in re.finditer(rf"{verb}\s+([\d,\s]+)", body, re.I):
                nums = [int(n) for n in re.findall(r"\d+", match.group(1))]
                decisions.append((digest_date, verb.lower(), nums))
        m.store(i, "+FLAGS", "\\Seen")
    m.logout()
    return decisions


def send_note(subject: str, html: str) -> None:
    resend.Emails.send({"from": os.environ["FROM_EMAIL"], "to": [os.environ["TO_EMAIL"]],
                        "subject": f"[Job Agent] {subject}", "html": html})
