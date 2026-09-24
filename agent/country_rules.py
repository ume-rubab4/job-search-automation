"""
CV conventions by country. Used both by the LLM (as instructions) and by the DOCX builder
(which fields to include). Always ATS-safe: single column, no tables/text boxes/graphics,
standard fonts, plain section headings.
"""

BASE_ATS = ("Single column, no tables, no text boxes, no icons or graphics, no headers/footers, "
            "standard font (Calibri/Arial 10.5-11pt), clear section headings, bullet points, "
            "keywords copied verbatim from the job posting where truthful.")

RULES = {
    "US": dict(label="Resume", pages=1, photo=False, dob=False, nationality=False, marital=False,
               spelling="US English", summary_heading="Professional Summary", references=False,
               notes="One page. No personal data beyond name, city/state, phone, email, LinkedIn. "
                     "Strong action verbs and quantified results. Cover letter only if requested.",
               cover_letter="Short 3-paragraph letter, US business format, no address block needed for email."),
    "GB": dict(label="CV", pages=2, photo=False, dob=False, nationality=False, marital=False,
               spelling="British English", summary_heading="Personal Statement", references="on request",
               notes="Max two pages. No photo, no date of birth. Mention right-to-work/visa sponsorship "
                     "need honestly in a one-line 'Work authorisation' section.",
               cover_letter="Formal UK cover letter, British spelling, 'Yours sincerely' if named recipient."),
    "IE": "GB",
    "AU": dict(label="Resume", pages=3, photo=False, dob=False, nationality=False, marital=False,
               spelling="Australian English", summary_heading="Career Profile", references="on request",
               notes="2-3 pages accepted. No photo. Include 'Visa status' line stating sponsorship required. "
                     "Address key selection criteria if listed.",
               cover_letter="One page, addresses selection criteria explicitly, Australian spelling."),
    "DE": dict(label="Lebenslauf", pages=2, photo=True, dob=True, nationality=True, marital=False,
               spelling="British English (or German if posting is in German)", summary_heading="Profil",
               references=False,
               notes="Tabular chronological CV. Professional photo top-right is customary. Include date "
                     "and place of birth and nationality. End with place, date and name (signature line). "
                     "An 'Anschreiben' (cover letter) is expected for nearly every application.",
               cover_letter="Formal German-style Anschreiben structure: subject line, 3-4 paragraphs, "
                            "why this company, why you, availability and salary expectation only if asked."),
    "AT": "DE",
    "CH": dict(label="Lebenslauf / CV", pages=2, photo=True, dob=True, nationality=True, marital=True,
               spelling="British English", summary_heading="Profile", references="on request",
               notes="Like Germany: photo, date of birth, nationality, and work-permit status line. "
                     "Very precise, no exaggeration. Cover letter expected.",
               cover_letter="Formal, concise, Swiss business tone; mention permit/relocation openness."),
    "FR": dict(label="CV", pages=1, photo=True, dob=True, nationality=True, marital=False,
               spelling="British English (French if posting is in French)", summary_heading="Profil",
               references=False,
               notes="One page. Photo common. Title line under name stating the target role. "
                     "'Lettre de motivation' is expected.",
               cover_letter="Lettre de motivation: 'vous-moi-nous' structure (the company, you, together)."),
    "ES": dict(label="Currículum", pages=2, photo=True, dob=True, nationality=True, marital=False,
               spelling="British English (Spanish if posting is in Spanish)", summary_heading="Perfil",
               references=False,
               notes="Photo and date of birth are common. One to two pages.",
               cover_letter="Carta de presentación, formal, one page."),
    "EU": dict(label="CV", pages=2, photo=False, dob=False, nationality=True, marital=False,
               spelling="British English", summary_heading="Profile", references=False,
               notes="Europass-compatible order: personal info, profile, experience, education, skills. "
                     "State EU work-permit need.", cover_letter="Formal one-page letter."),
    "GULF": dict(label="CV", pages=2, photo=True, dob=True, nationality=True, marital=True,
                 spelling="British English", summary_heading="Professional Summary", references="on request",
                 notes="UAE/KSA/Qatar/Oman/Kuwait/Bahrain: photo, nationality, date of birth, marital status, "
                       "current location and 'Visa status: requires employment visa sponsorship' are standard. "
                       "Notice period / availability line is expected.",
                 cover_letter="Brief, formal; highlight immediate availability and relocation readiness."),
    "REMOTE": "GB",
}
GULF = {"AE", "SA", "QA", "OM", "KW", "BH"}


def for_country(iso: str) -> dict:
    if iso in GULF:
        key = "GULF"
    elif iso in RULES:
        key = iso
    else:
        key = "EU"
    r = RULES[key]
    while isinstance(r, str):        # alias
        r = RULES[r]
    r = dict(r)
    r["ats"] = BASE_ATS
    r["country"] = iso
    return r
