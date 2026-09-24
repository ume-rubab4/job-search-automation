"""
Auto-apply for Greenhouse / Lever / Ashby / Workable application forms using Playwright.
Candidate-side APIs don't exist for these platforms, so we fill the public form.
If the form has captcha, login, or unexpected required fields, we stop and mark it
'package_ready' so you can finish it manually with the prepared CV and cover letter.

Playwright is an optional dependency. Without it the module still imports and
auto_apply degrades to package_ready, which is the same outcome as an unsupported
platform. This keeps the container image small and lets the package be imported
without a browser runtime installed.
"""
import os

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
except ImportError:
    sync_playwright = None
    PWTimeout = Exception

from .core import PROFILE, CONFIG

_name_parts = (PROFILE.get("name") or "").split()
FIELD_MAP = {
    "first": _name_parts[0] if _name_parts else "",
    "last": _name_parts[-1] if _name_parts else "",
    "name": PROFILE.get("name", ""),
    "email": PROFILE.get("email", ""),
    "phone": PROFILE.get("phone", ""),
    "location": PROFILE.get("location", ""),
    "linkedin": PROFILE.get("linkedin", ""),
}
UNSUPPORTED_MARKERS = ["captcha", "recaptcha", "hcaptcha", "sign in to apply", "create an account"]


def _fill_by_label(page, keyword: str, value: str) -> bool:
    if not value:
        return False
    for sel in (f"input[name*='{keyword}' i]", f"input[id*='{keyword}' i]",
                f"input[placeholder*='{keyword}' i]", f"input[aria-label*='{keyword}' i]"):
        el = page.query_selector(sel)
        if el and el.is_visible():
            el.fill(value)
            return True
    return False


def auto_apply(job: dict, cv_path: str, cover_path: str | None) -> tuple[bool, str]:
    if sync_playwright is None:
        return False, "playwright not installed; prepare for manual submit"
    if job["platform"] not in CONFIG["apply"]["auto_apply_platforms"]:
        return False, "platform not supported for auto-apply"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(job["url"], timeout=45000)
            page.wait_for_load_state("networkidle", timeout=30000)
            html = page.content().lower()
            if any(m in html for m in UNSUPPORTED_MARKERS):
                return False, "captcha or login required"

            # Some boards need an 'Apply' click to reveal the form
            for txt in ("Apply for this job", "Apply now", "Apply"):
                btn = page.get_by_role("button", name=txt, exact=False)
                if btn.count():
                    btn.first.click()
                    page.wait_for_timeout(1500)
                    break

            _fill_by_label(page, "first", FIELD_MAP["first"])
            _fill_by_label(page, "last", FIELD_MAP["last"])
            if not page.query_selector("input[name*='first' i]"):
                _fill_by_label(page, "name", FIELD_MAP["name"])
            _fill_by_label(page, "email", FIELD_MAP["email"])
            _fill_by_label(page, "phone", FIELD_MAP["phone"])
            _fill_by_label(page, "location", FIELD_MAP["location"])
            _fill_by_label(page, "linkedin", FIELD_MAP["linkedin"])

            files = page.query_selector_all("input[type='file']")
            if not files:
                return False, "no resume upload field found"
            files[0].set_input_files(cv_path)
            if cover_path and len(files) > 1:
                files[1].set_input_files(cover_path)

            # Bail out if there are required fields we didn't fill (custom questions)
            page.wait_for_timeout(1000)
            empty_required = [e for e in page.query_selector_all("[required]")
                              if e.is_visible() and e.get_attribute("type") not in ("file", "checkbox")
                              and not (e.input_value() if e.evaluate("e=>e.tagName") in ("INPUT", "TEXTAREA") else "x")]
            if empty_required:
                return False, f"{len(empty_required)} custom required field(s) need manual answers"

            submit = page.query_selector("button[type='submit'], input[type='submit']")
            if not submit:
                return False, "submit button not found"
            if os.getenv("DRY_RUN"):
                return True, "DRY_RUN: form filled, not submitted"
            submit.click()
            page.wait_for_timeout(4000)
            ok = any(w in page.content().lower() for w in ("thank you", "application submitted", "received"))
            return ok, "submitted" if ok else "submitted but no confirmation text detected"
        except PWTimeout:
            return False, "page timeout"
        except Exception as e:
            return False, f"error: {e}"
        finally:
            browser.close()
