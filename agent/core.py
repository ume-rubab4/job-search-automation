import os, json, hashlib, yaml
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
ROOT = Path(__file__).resolve().parent.parent
CONFIG = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))


def _load_profile() -> dict:
    """Load the candidate profile, falling back to the example file.

    Keeping this non-fatal means the package can be imported without a
    configured profile, which is what CI and a fresh clone need.
    """
    for candidate in (ROOT / "data" / "profile.json", ROOT / "data" / "profile.example.json"):
        if candidate.exists():
            return json.loads(candidate.read_text(encoding="utf-8"))
    return {"name": "", "email": "", "phone": "", "location": "", "headline": ""}


PROFILE = _load_profile()
OUTPUT_DIR = ROOT / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


class _Unconfigured:
    """Stands in for a client that could not be created.

    Importing this module must not require credentials, so a missing
    environment variable defers the error to the moment the client is
    actually used, with a message that says what to set.
    """

    def __init__(self, service: str, variables: str):
        self._service, self._variables = service, variables

    def __getattr__(self, name):
        raise RuntimeError(
            f"{self._service} is not configured. Set {self._variables} in your .env file. "
            "See .env.example for the full list."
        )


def _make_db():
    url, key = os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY")
    if not (url and key):
        return _Unconfigured("Supabase", "SUPABASE_URL and SUPABASE_SERVICE_KEY")
    from supabase import create_client
    return create_client(url, key)


db = _make_db()

# ---- LLM provider switch: LLM_PROVIDER=anthropic | gemini ----
PROVIDER = os.getenv("LLM_PROVIDER", "gemini").lower()
gtypes = None

if PROVIDER == "gemini":
    MODEL = os.getenv("WRITER_MODEL", "gemini-2.5-pro")         # CV + cover letters
    MATCH_MODEL = os.getenv("MATCH_MODEL", "gemini-2.5-flash")  # scoring every job
    if os.getenv("GEMINI_API_KEY"):
        from google import genai
        from google.genai import types as gtypes
        _llm = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    else:
        _llm = _Unconfigured("Gemini", "GEMINI_API_KEY")
else:
    MODEL = os.getenv("WRITER_MODEL", "claude-sonnet-5")
    MATCH_MODEL = os.getenv("MATCH_MODEL", "claude-haiku-4-5")
    if os.getenv("ANTHROPIC_API_KEY"):
        from anthropic import Anthropic
        _llm = Anthropic()
    else:
        _llm = _Unconfigured("Anthropic", "ANTHROPIC_API_KEY")


def _complete(system: str, user: str, max_tokens: int, model: str) -> str:
    if PROVIDER == "gemini":
        r = _llm.models.generate_content(
            model=model, contents=user,
            config=gtypes.GenerateContentConfig(system_instruction=system, max_output_tokens=max_tokens))
        return (r.text or "").strip()
    r = _llm.messages.create(model=model, max_tokens=max_tokens, system=system,
                             messages=[{"role": "user", "content": user}])
    return r.content[0].text.strip()


ALL_COUNTRIES = [c for c in CONFIG["countries"]["primary"] + CONFIG["countries"]["gulf"]
                 if c not in CONFIG["excluded_countries"]]


def job_hash(title: str, company: str, country: str) -> str:
    key = f"{title}|{company}|{country}".lower().strip()
    return hashlib.sha1(key.encode()).hexdigest()


def ask_json(system: str, user: str, max_tokens: int = 1500, model: str = None) -> dict:
    """Call the LLM and parse a JSON-only reply."""
    text = _complete(system, user, max_tokens, model or MODEL)
    text = text.replace("```json", "").replace("```", "").strip()
    return json.loads(text)


def ask_text(system: str, user: str, max_tokens: int = 2500) -> str:
    return _complete(system, user, max_tokens, MODEL)


def detect_platform(url: str) -> str:
    u = url.lower()
    for p in ("greenhouse", "lever", "ashby", "workable"):
        if p in u:
            return p
    return "other"
