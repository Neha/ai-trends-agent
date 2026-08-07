"""Step 2 — The AI layer: cluster posts into trending topics + extract questions.

Sends the fetched posts to a Cursor agent and asks it to group them into themes
and pull out the real questions people are asking. Expects a JSON object back
matching DIGEST_SCHEMA.

Writes digest.json.
"""

from __future__ import annotations

import json
import os
import re

from cursor_sdk import Agent, AgentOptions, CursorAgentError, LocalAgentOptions

import config

DIGEST_SCHEMA = {
    "type": "object",
    "properties": {
        "trending_topics": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "summary": {"type": "string"},
                    "post_count": {"type": "integer"},
                    "example_urls": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["topic", "summary", "post_count", "example_urls"],
                "additionalProperties": False,
            },
        },
        "top_questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "source_url": {"type": "string"},
                },
                "required": ["question", "source_url"],
                "additionalProperties": False,
            },
        },
        "notable_papers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "summary": {"type": "string"},
                    "url": {"type": "string"},
                },
                "required": ["title", "summary", "url"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["trending_topics", "top_questions", "notable_papers"],
    "additionalProperties": False,
}

PROMPT = """You are analyzing this week's top AI discussion from public Reddit
communities, AI news headlines/announcements, and recent arXiv papers.

Here are the items as JSON (each has a "source" of reddit, news, or paper):

{posts}

Produce a digest as a single JSON object matching this schema:

{schema}

Guidance:
- Engagement is the primary signal for Reddit items. Each Reddit post includes
  "score" (upvotes) and "num_comments". Prefer high score + high comment count
  when choosing themes, example URLs, and questions. Low-engagement posts should
  rarely drive a topic unless they are uniquely important.
- "trending_topics": 5-7 themes covering model releases, product announcements,
  research directions, tools, safety/policy, and community debates. Group
  semantically similar items, weighted toward the most upvoted/commented posts.
  Each has a "topic" (short label), "summary" (2 clear, plain-language sentences),
  "post_count" (how many items fed this theme), and "example_urls" (up to 3 —
  pick the highest-engagement examples for that theme).
- "top_questions": 8-10 real questions people are actually asking, each with the
  "source_url" of the post it came from. Prefer highly upvoted/commented Reddit
  posts over news headlines.
- "notable_papers": 4-6 standout papers from the arXiv items (source=paper).
  Papers have no vote counts — judge by clarity/novelty of the abstract. Each
  has "title", a 1-2 sentence plain-language "summary", and "url".
  If fewer papers are available, return what you have.

Use clear, concrete language for engineers and practitioners. Summarize; do not
repeat post or abstract text verbatim. Prefer signal over hype.

CRITICAL:
- Reply with ONLY valid JSON matching the schema above.
- No markdown fences, no commentary, no file edits.
- Do not read or write any files.
"""


def _extract_json(text: str) -> dict:
    """Parse JSON from the model reply, tolerating optional markdown fences."""
    text = (text or "").strip()
    if not text:
        raise SystemExit("Cursor returned an empty response.")

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except json.JSONDecodeError:
            pass

    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass

    raise SystemExit("Cursor reply was not valid JSON. Check the prompt/model output.")


def _validate_digest(digest: dict) -> None:
    if not isinstance(digest, dict):
        raise SystemExit("Digest must be a JSON object.")
    for key in ("trending_topics", "top_questions", "notable_papers"):
        if key not in digest:
            raise SystemExit(f'Digest missing "{key}".')
        if not isinstance(digest[key], list):
            raise SystemExit(f"{key} must be an array.")


def analyze(posts: list[dict]) -> dict:
    compact = [
        {
            "title": p["title"],
            "body": p["body"][:500],
            "score": p["score"],
            "num_comments": p.get("num_comments", 0),
            "engagement": int(p.get("score") or 0) + int(p.get("num_comments") or 0),
            "url": p["url"],
            "source": p.get("source", "reddit"),
        }
        for p in posts
    ]
    prompt = PROMPT.format(
        posts=json.dumps(compact, indent=2),
        schema=json.dumps(DIGEST_SCHEMA, indent=2),
    )

    try:
        result = Agent.prompt(
            prompt,
            AgentOptions(
                api_key=config.cursor_api_key(),
                model=config.CURSOR_MODEL,
                # Text-only: no file/shell tools — just return the digest JSON.
                tools=[],
                local=LocalAgentOptions(cwd=os.getcwd()),
            ),
        )
    except CursorAgentError as err:
        raise SystemExit(
            f"Cursor agent failed to start: {err.message} "
            f"(retryable={err.is_retryable})"
        ) from err

    if result.status == "error":
        raise SystemExit(f"Cursor run failed: {result.id}")

    digest = _extract_json(result.result or "")
    _validate_digest(digest)

    if result.usage:
        print(
            f"  tokens — input: {getattr(result.usage, 'input_tokens', '?')}, "
            f"output: {getattr(result.usage, 'output_tokens', '?')}"
        )
    return digest


def main() -> None:
    with open(config.RAW_POSTS_FILE) as f:
        posts = json.load(f)

    if not posts:
        raise SystemExit(f"No posts in {config.RAW_POSTS_FILE}. Run fetch.py first.")

    print(f"Analyzing {len(posts)} posts with Cursor ({config.CURSOR_MODEL})...")
    digest = analyze(posts)

    with open(config.DIGEST_FILE, "w") as f:
        json.dump(digest, f, indent=2)
    print(
        f"Wrote {len(digest['trending_topics'])} topics, "
        f"{len(digest['top_questions'])} questions, and "
        f"{len(digest['notable_papers'])} papers to {config.DIGEST_FILE}"
    )


if __name__ == "__main__":
    main()
