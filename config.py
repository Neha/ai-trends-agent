"""Central configuration. Loads secrets from .env and defines tunable settings.

Secrets live in .env (see .env.example). Everything else is a plain constant
here so you can tweak behavior without touching the scripts.
"""

import os

from dotenv import load_dotenv

# Load .env from the project root into environment variables.
load_dotenv()


def require(name: str) -> str:
    """Return an env var or raise a clear error if it's missing."""
    value = os.environ.get(name)
    if not value or value.startswith("your_"):
        raise SystemExit(
            f"Missing config: {name}. Copy .env.example to .env and fill it in."
        )
    return value


def cursor_api_key() -> str:
    """Cursor API key — only needed for analyze.py, not for fetching."""
    return require("CURSOR_API_KEY")


# ── Tunable settings (edit freely) ──

# Descriptive User-Agent for public HTTP requests (Reddit rejects empty/default UAs).
USER_AGENT = "ai-trends-agent/0.1 (weekly digest; educational)"

# Subreddits to scan via public JSON / PullPush fallback.
SUBREDDITS = [
    "MachineLearning",
    "LocalLLaMA",
    "OpenAI",
    "artificial",
    "ChatGPT",
    "ClaudeAI",
    "claude",
    "singularity",
    "LangChain",
    "womenin_AI",
]

# How many top posts to pull per subreddit.
POSTS_PER_SUB = 40

# Reddit sort window for "trending": "day", "week", or "month".
TIME_FILTER = "week"

# Google News RSS query + how many articles to keep.
NEWS_QUERY = (
    'AI OR "artificial intelligence" OR LLM OR "large language model" '
    'OR "OpenAI" OR "Anthropic" OR "Google DeepMind"'
)
NEWS_LIMIT = 25

# arXiv categories / search for recent papers + how many to keep.
ARXIV_QUERY = "cat:cs.AI OR cat:cs.LG OR cat:cs.CL"
ARXIV_LIMIT = 25

# Cursor model for analyze.py. "composer-2.5" is the usual default; "auto" lets
# the server pick. List available IDs with: python -c "from cursor_sdk import Cursor; print([m.id for m in Cursor.models.list()])"
CURSOR_MODEL = "composer-2.5"

# File paths (kept in the project root).
RAW_POSTS_FILE = "raw_posts.json"
DIGEST_FILE = "digest.json"
OUTPUT_HTML = "index.html"

# Per-day archives so the site can navigate back and forth between digests.
# Each run writes archive/YYYY-MM-DD/{digest.json,index.html}.
ARCHIVE_DIR = "archive"
