"""
Job agent dashboard.  Run:  python -m streamlit run dashboard.py
"""
import os, sys, subprocess
from datetime import datetime
import pandas as pd
import altair as alt
import streamlit as st
import json
from agent.core import db, CONFIG, ROOT
from agent import profile_builder

PROFILE = json.loads((ROOT / "data" / "profile.json").read_text())

st.set_page_config(page_title="Job agent", page_icon="✦", layout="wide", initial_sidebar_state="collapsed")

st.html("""<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root { --ink:#EAF2FF; --muted:#8FA3C2; --line:rgba(120,170,255,0.14); --card:rgba(18,24,38,0.82);
          --blue:#5EB8FF; --blue-2:#3B82F6; --mint:#2DD4BF; --peach:#FB923C; --lilac:#A78BFA; --lemon:#FACC15; --rose:#FB7185; }
  .stApp { background: radial-gradient(1200px 600px at 10% -10%, #0F2A4A 0%, #0B0F19 45%, #07090F 100%); color: var(--ink); }
  html, body, [class*="css"], p, li, span, div, button { font-family: "Plus Jakarta Sans", sans-serif; }
  .block-container { max-width: 1180px; padding-top: 1.6rem; }
  header[data-testid="stHeader"] { background: transparent; }
  .stMarkdown, .stMarkdown p, .stMarkdown li, label, .stCaption { color: var(--ink) !important; }
  .hero { display:flex; align-items:center; justify-content:space-between; margin-bottom: 1.2rem; }
  .hello { font-size: 2.1rem; font-weight: 700; color: #FFFFFF; margin: 0; letter-spacing: -0.02em; }
  .sub { color: var(--muted); margin-top: 0.2rem; }
  .avatar { width: 56px; height: 56px; border-radius: 50%; background: linear-gradient(135deg,#5EB8FF,#3B82F6);
            color:#06101F; display:flex; align-items:center; justify-content:center; font-weight:700; font-size:1.3rem;
            box-shadow: 0 0 28px rgba(94,184,255,0.45); }
  .tiles { display:grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 1.4rem; }
  .tile { background: var(--card); border: 1px solid var(--line); border-radius: 18px; padding: 16px 18px;
          box-shadow: 0 12px 30px rgba(0,0,0,0.35); backdrop-filter: blur(10px); }
  .tile .ico { width: 38px; height: 38px; border-radius: 12px; display:flex; align-items:center; justify-content:center;
               font-size: 1.1rem; margin-bottom: 10px; background: rgba(94,184,255,0.12); }
  .tile .num { font-size: 1.9rem; font-weight: 700; color: #FFFFFF; line-height: 1; }
  .tile .lab { color: var(--muted); font-size: 0.85rem; margin-top: 4px; }
  .panel-title { font-weight: 600; color: #FFFFFF; font-size: 1.05rem; margin: 0.4rem 0 0.4rem; }
  .job-title { font-size: 1.2rem; font-weight: 700; color: #FFFFFF; margin: 0; }
  .job-meta  { color: var(--muted); margin-top: 0.15rem; font-size: 0.9rem; }
  .pill { display:inline-block; padding: 4px 11px; border-radius: 999px; font-size: 0.78rem; font-weight: 600;
          margin: 8px 6px 0 0; border: 1px solid transparent; }
  .p-mint { background: rgba(45,212,191,0.14); color: var(--mint); border-color: rgba(45,212,191,0.3); }
  .p-sky  { background: rgba(94,184,255,0.14); color: var(--blue); border-color: rgba(94,184,255,0.3); }
  .p-peach{ background: rgba(251,146,60,0.14); color: var(--peach); border-color: rgba(251,146,60,0.3); }
  .p-lilac{ background: rgba(167,139,250,0.14); color: var(--lilac); border-color: rgba(167,139,250,0.3); }
  .p-lemon{ background: rgba(250,204,21,0.14); color: var(--lemon); border-color: rgba(250,204,21,0.3); }
  .p-rose { background: rgba(251,113,133,0.14); color: var(--rose); border-color: rgba(251,113,133,0.3); }
  .p-grey { background: rgba(255,255,255,0.06); color: var(--muted); border-color: rgba(255,255,255,0.1); }
  .ring { width: 64px; height: 64px; border-radius: 50%; display:flex; align-items:center; justify-content:center;
          font-weight: 700; font-size: 1.15rem; color: #FFFFFF; margin-left:auto; }
  [data-testid="stVerticalBlockBorderWrapper"] { background: var(--card); border: 1px solid var(--line) !important;
        border-radius: 18px; box-shadow: 0 12px 30px rgba(0,0,0,0.35); padding: 0.5rem 0.8rem; }
  .stTabs [data-baseweb="tab-list"] { gap: 6px; background: rgba(255,255,255,0.05); padding: 6px; border-radius: 14px; width: fit-content; }
  .stTabs [data-baseweb="tab"] { border-radius: 10px; padding: 6px 14px; color: var(--muted); font-weight: 600; }
  .stTabs [aria-selected="true"] { background: rgba(94,184,255,0.16); color: #FFFFFF; }
  .stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] { display: none; }
  .stButton>button, .stDownloadButton>button, .stLinkButton a { border-radius: 12px; font-weight: 600;
        border: 1px solid var(--line); background: rgba(255,255,255,0.05); color: var(--ink); }
  .stButton>button:hover, .stDownloadButton>button:hover, .stLinkButton a:hover { border-color: var(--blue); color: var(--blue); }
  .stButton>button[kind="primary"] { background: linear-gradient(135deg,#5EB8FF,#3B82F6); color:#06101F; border: none;
        box-shadow: 0 0 22px rgba(94,184,255,0.35); }
  .stButton>button[kind="primary"]:hover { filter: brightness(1.08); }
  [data-testid="stExpander"] { border: none; background: transparent; }
  [data-testid="stExpander"] summary, [data-testid="stCaptionContainer"] { color: var(--muted) !important; }
  [data-testid="stExpander"] summary:hover { color: var(--blue) !important; }
  section[data-testid="stSidebar"] { background: rgba(11,15,25,0.9); }
  .stMultiSelect div[data-baseweb="select"] > div, .stDataFrame { background: rgba(255,255,255,0.04); }
</style>""")

VISA = {"stated_yes": ("Sponsorship stated", "p-mint"), "known_sponsor": ("Known sponsor", "p-mint"),
        "not_mentioned": ("Visa not mentioned", "p-lemon"), "stated_no": ("No sponsorship", "p-rose")}
STATUS_LABEL = {"emailed": "Needs your decision", "shortlisted": "Shortlisted", "approved": "Approved, applying next run",
                "applied": "Applied", "package_ready": "Ready for you to submit", "skipped": "Skipped",
                "apply_failed": "Apply failed", "rejected": "Not a match", "found": "Found"}
PASTEL = ["#5EB8FF", "#2DD4BF", "#A78BFA", "#FB923C", "#FACC15", "#FB7185", "#38BDF8", "#818CF8"]


@st.cache_data(ttl=30)
def load_jobs() -> pd.DataFrame:
    rows, start, page = [], 0, 1000
    while True:
        batch = db.table("jobs").select("*").order("found_at", desc=True).range(start, start + page - 1).execute().data
        rows += batch
        if len(batch) < page:
            break
        start += page
    df = pd.DataFrame(rows)
    if not df.empty:
        df["found_at"] = pd.to_datetime(df["found_at"])
    return df


def set_status(job_id: int, status: str):
    db.table("jobs").update({"status": status}).eq("id", job_id).execute()
    load_jobs.clear()


def run_agent(mode: str):
    os.makedirs("logs", exist_ok=True)
    log = open(f"logs/{mode}.log", "a")
    subprocess.Popen([sys.executable, "-m", "agent.main", mode], stdout=log, stderr=subprocess.STDOUT)


def download_button(label, path, key):
    if path and os.path.exists(path):
        with open(path, "rb") as f:
            st.download_button(label, f.read(), file_name=os.path.basename(path), key=key)


def ring(score):
    s = int(score or 0)
    color = "#2DD4BF" if s >= 80 else "#5EB8FF" if s >= 65 else "#FACC15"
    return (f"<div class='ring' style='background: conic-gradient({color} {s*3.6}deg, rgba(255,255,255,0.08) 0deg);'>"
            f"<div style='width:50px;height:50px;border-radius:50%;background:#121826;display:flex;align-items:center;"
            f"justify-content:center'>{s}</div></div>")


def job_card(j: dict, actions: bool):
    visa_txt, visa_cls = VISA.get(j.get("visa_status"), ("Visa unknown", "p-grey"))
    size = (j.get("company_size") or "unknown") + " company"
    auto = j.get("platform") not in (None, "other")
    method = ("Auto-apply", "p-sky") if auto else ("You submit", "p-peach")
    with st.container(border=True):
        left, right = st.columns([6, 1])
        with left:
            st.html(f"<p class='job-title'>{j['title']}</p>"
                    f"<p class='job-meta'>{j.get('company') or ''} · {j.get('city') or ''}, {j.get('country')}"
                    f"{' · Remote' if j.get('remote') else ''}</p>"
                    f"<span class='pill {visa_cls}'>{visa_txt}</span><span class='pill p-lilac'>{size}</span>"
                    f"<span class='pill {method[1]}'>{method[0]}</span><span class='pill p-grey'>{j.get('source')}</span>")
        with right:
            st.html(ring(j.get("fit_score")))
        if j.get("visa_evidence"):
            st.caption(f"Posting says: “{j['visa_evidence']}”")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**You match**")
            for m in (j.get("matched_reqs") or [])[:5]:
                st.markdown(f"- {m}")
        with c2:
            st.markdown("**Gaps**")
            gaps = j.get("missing_reqs") or []
            for m in gaps[:5]:
                st.markdown(f"- {m}")
            if not gaps:
                st.markdown("- none found")
        with st.expander("Job description"):
            st.write((j.get("description") or "")[:4000])
        b1, b2, b3, b4, b5 = st.columns([1.3, 1.3, 1.4, 1.4, 3])
        b1.link_button("Open posting", j["url"])
        with b2:
            download_button("Tailored CV", j.get("cv_path"), f"cv{j['id']}")
        with b3:
            download_button("Cover letter", j.get("cover_letter_path"), f"cl{j['id']}")
        if actions:
            if b4.button("🚀 Apply now", key=f"an{j['id']}", type="primary"):
                with st.spinner("Applying… (up to a minute)"):
                    subprocess.run([sys.executable, "-m", "agent.main", "apply_one", str(j["id"])],
                                   capture_output=True, text=True, timeout=240)
                load_jobs.clear()
                res = db.table("jobs").select("status,apply_notes").eq("id", j["id"]).execute().data[0]
                st.toast("Applied ✅" if res["status"] == "applied" else f"Ready to submit: {res['apply_notes']}")
                st.rerun()
            c5a, c5b = b5.columns(2)
            if c5a.button("Approve", key=f"ap{j['id']}"):
                set_status(j["id"], "approved"); st.rerun()
            if c5b.button("Skip", key=f"sk{j['id']}"):
                set_status(j["id"], "skipped"); st.rerun()
        elif j.get("apply_notes"):
            b4.caption(j["apply_notes"])

            # ---------------- Header ----------------
df = load_jobs()
hour = datetime.now().hour
greet = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"
first = PROFILE["name"].split()[0]
initials = "".join(w[0] for w in PROFILE["name"].split()[:2]).upper()
pending = int((df["status"] == "emailed").sum()) if not df.empty else 0
sub = (f"{pending} job{'s' if pending != 1 else ''} waiting for your decision" if pending
       else "No decisions waiting. The agent checks for new jobs every morning.")
st.html(f"<div class='hero'><div><p class='hello'>{greet}, {first}</p><p class='sub'>{sub}</p></div>"
        f"<div class='avatar'>{initials}</div></div>")

counts = df["status"].value_counts() if not df.empty else {}
tiles = [("✉️", "var(--sky)", int(counts.get("emailed", 0)), "Waiting for you"),
         ("✅", "var(--mint)", int(counts.get("applied", 0)), "Applied"),
         ("📎", "var(--peach)", int(counts.get("package_ready", 0)), "Ready to submit"),
         ("🔍", "var(--lilac)", len(df), "Jobs seen")]
st.html("<div class='tiles'>" + "".join(
    f"<div class='tile'><div class='ico' style='background:{bg}'>{ico}</div><div class='num'>{n}</div><div class='lab'>{lab}</div></div>"
    for ico, bg, n, lab in tiles) + "</div>")

# ---------------- Actions ----------------
a1, a2, a3, a4 = st.columns([1.4, 1.6, 1.4, 3.6])
if a1.button("Find new jobs now", type="primary"):
    run_agent("discover"); st.toast("Started. Takes 10–20 minutes; refresh later.")
if a2.button("Apply to approved jobs"):
    run_agent("approvals"); st.toast("Started. Results will be emailed.")
if a3.button("✚ Update my CV"):
    st.session_state["show_cv"] = not st.session_state.get("show_cv", False)

if st.session_state.get("show_cv"):
    with st.container(border=True):
        st.html("<p class='panel-title'>Update your CV</p>")
        st.caption("Upload your latest CV (PDF or Word). The agent reads it, rebuilds your profile, and uses it for "
                   "every future match and tailored CV. Your current profile is backed up automatically.")
        up = st.file_uploader("Choose a file", type=["pdf", "docx"], label_visibility="collapsed")
        if up is not None and st.button("Read this CV", type="primary"):
            with st.spinner("Reading your CV…"):
                try:
                    st.session_state["new_profile"] = profile_builder.build_profile(up.name, up.getvalue())
                except Exception as e:
                    st.error(f"Couldn't read the CV: {e}")
        newp = st.session_state.get("new_profile")
        if newp:
            st.markdown(f"**{newp.get('name')}** — {newp.get('headline')}")
            st.markdown(f"{len(newp.get('skills', []))} skills · {len(newp.get('experience', []))} roles · "
                        f"{len(newp.get('certifications', []))} certifications")
            with st.expander("See everything extracted"):
                st.json(newp)
            k1, k2, _ = st.columns([1.4, 1.2, 4])
            if k1.button("Save as my profile", type="primary"):
                profile_builder.save_profile(newp)
                st.session_state.pop("new_profile", None); st.session_state["show_cv"] = False
                st.toast("Profile updated. New matches will use it from the next run.")
                st.rerun()
            if k2.button("Discard"):
                st.session_state.pop("new_profile", None); st.rerun()

if df.empty:
    st.info("No jobs yet. Click **Find new jobs now**, or run `python -m agent.main discover` in the terminal.")
    st.stop()

# ---------------- Charts ----------------
ch1, ch2 = st.columns([1.3, 1])
with ch1:
    with st.container(border=True):
        st.html("<p class='panel-title'>Matches by country</p>")
        good = df[df["status"].isin(["emailed", "approved", "applied", "package_ready", "shortlisted"])]
        src = (good if not good.empty else df).groupby("country").size().reset_index(name="jobs").sort_values("jobs", ascending=False).head(10)
        chart = alt.Chart(src).mark_bar(cornerRadiusEnd=6).encode(
            x=alt.X("jobs:Q", title=None, axis=alt.Axis(grid=False)),
            y=alt.Y("country:N", sort="-x", title=None),
            color=alt.Color("country:N", legend=None, scale=alt.Scale(range=PASTEL)),
            tooltip=["country", "jobs"]).properties(height=240).configure_view(strokeWidth=0).configure_axis(labelColor="#8FA3C2", domainColor="#26324A", tickColor="#26324A").configure(background="transparent")
        st.altair_chart(chart, use_container_width=True)
with ch2:
    with st.container(border=True):
        st.html("<p class='panel-title'>Visa sponsorship among matches</p>")
        v = (good if not good.empty else df)["visa_status"].fillna("not_mentioned").map(lambda x: VISA.get(x, ("Unknown",))[0])
        src = v.value_counts().reset_index(); src.columns = ["visa", "jobs"]
        donut = alt.Chart(src).mark_arc(innerRadius=62, cornerRadius=4).encode(
            theta="jobs:Q", color=alt.Color("visa:N", legend=alt.Legend(title=None, orient="bottom"),
                                             scale=alt.Scale(range=["#2DD4BF", "#FACC15", "#FB7185", "#64748B"])),
            tooltip=["visa", "jobs"]).properties(height=240).configure_view(strokeWidth=0).configure_legend(labelColor="#8FA3C2").configure(background="transparent")
        st.altair_chart(donut, use_container_width=True)

# ---------------- Tabs ----------------
tab_decide, tab_progress, tab_all = st.tabs(["Needs your decision", "In progress", "All jobs"])

with tab_decide:
    pend = df[df["status"] == "emailed"].sort_values("fit_score", ascending=False)
    if pend.empty:
        st.markdown("Nothing waiting. New matches appear here after each daily run.")
    for _, j in pend.iterrows():
        job_card(j.to_dict(), actions=True)

with tab_progress:
    prog = df[df["status"].isin(["approved", "applied", "package_ready", "apply_failed"])]
    if prog.empty:
        st.markdown("Nothing in progress yet.")
    for status in ["package_ready", "approved", "applied", "apply_failed"]:
        block = prog[prog["status"] == status].sort_values("found_at", ascending=False)
        if block.empty:
            continue
        st.html(f"<p class='panel-title'>{STATUS_LABEL[status]}</p>")
        if status == "package_ready":
            st.caption("The site needed a login, captcha, or custom questions. Download the CV, open the posting, and submit yourself.")
        for _, j in block.iterrows():
            job_card(j.to_dict(), actions=False)

with tab_all:
    f1, f2, f3, f4 = st.columns(4)
    country = f1.multiselect("Country", sorted(df["country"].dropna().unique()))
    visa = f2.multiselect("Visa", list(VISA.keys()), format_func=lambda v: VISA[v][0])
    status = f3.multiselect("Status", list(STATUS_LABEL.keys()), format_func=lambda s: STATUS_LABEL[s])
    min_fit = f4.slider("Minimum fit score", 0, 100, 0)
    view = df.copy()
    if country: view = view[view["country"].isin(country)]
    if visa: view = view[view["visa_status"].isin(visa)]
    if status: view = view[view["status"].isin(status)]
    view = view[view["fit_score"].fillna(0) >= min_fit]
    table = view[["found_at", "title", "company", "city", "country", "fit_score", "visa_status", "company_size",
                  "status", "source", "url"]].rename(columns={
        "found_at": "Found", "title": "Title", "company": "Company", "city": "City", "country": "Country",
        "fit_score": "Fit", "visa_status": "Visa", "company_size": "Size", "status": "Status", "source": "Source", "url": "Link"})
    table["Found"] = table["Found"].dt.strftime("%d %b")
    table["Visa"] = table["Visa"].map(lambda v: VISA.get(v, ("–",))[0])
    table["Status"] = table["Status"].map(lambda s: STATUS_LABEL.get(s, s))
    st.dataframe(table, use_container_width=True, hide_index=True,
                 column_config={"Link": st.column_config.LinkColumn(display_text="open"),
                                "Fit": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d")})
    st.caption(f"{len(view)} of {len(df)} jobs")