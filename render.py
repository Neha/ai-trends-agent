"""Step 3 — Render digest.json into a static index.html page.

No LLM, no cost. Produces a self-contained HTML file you can host anywhere
(GitHub Pages, Netlify, S3) or open locally.

Also archives each day's page under archive/YYYY-MM-DD/ so readers can
navigate back and forth between dates.
"""

from __future__ import annotations

import datetime
import html
import json
import os
import re
import shutil
from urllib.parse import urlparse

import config

# Small inline SVGs so the page stays self-contained (no external assets).
_ICON_REDDIT = (
    '<svg class="src-icon" viewBox="0 0 20 20" aria-hidden="true">'
    '<circle cx="10" cy="10" r="10" fill="#FF4500"/>'
    '<circle cx="7.2" cy="10.2" r="1.35" fill="#fff"/>'
    '<circle cx="12.8" cy="10.2" r="1.35" fill="#fff"/>'
    '<path d="M7.4 12.4c.8.7 1.7 1 2.6 1s1.8-.3 2.6-1" fill="none" '
    'stroke="#fff" stroke-width="1.2" stroke-linecap="round"/>'
    "</svg>"
)
_ICON_NEWS = (
    '<svg class="src-icon" viewBox="0 0 20 20" aria-hidden="true">'
    '<rect width="20" height="20" rx="4" fill="#1a73e8"/>'
    '<path d="M4 6h12M4 10h8M4 14h10" stroke="#fff" stroke-width="1.6" '
    'stroke-linecap="round"/>'
    "</svg>"
)
_ICON_ARXIV = (
    '<svg class="src-icon" viewBox="0 0 20 20" aria-hidden="true">'
    '<rect width="20" height="20" rx="4" fill="#b31b1b"/>'
    '<text x="10" y="14" text-anchor="middle" fill="#fff" '
    'font-size="8" font-family="system-ui,sans-serif" font-weight="700">arX</text>'
    "</svg>"
)
_ICON_LINK = (
    '<svg class="src-icon" viewBox="0 0 20 20" aria-hidden="true">'
    '<rect width="20" height="20" rx="4" fill="#6b7280"/>'
    '<path d="M8 10.5a3 3 0 0 1 0-4.2l1.4-1.4a3 3 0 0 1 4.2 4.2L12.5 10" '
    'fill="none" stroke="#fff" stroke-width="1.4" stroke-linecap="round"/>'
    '<path d="M12 9.5a3 3 0 0 1 0 4.2l-1.4 1.4a3 3 0 0 1-4.2-4.2L7.5 10" '
    'fill="none" stroke="#fff" stroke-width="1.4" stroke-linecap="round"/>'
    "</svg>"
)

_DATE_DIR_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def esc(s: str) -> str:
    """Escape text so post titles/questions can't break the HTML."""
    return html.escape(str(s))


def source_label(url: str) -> tuple[str, str]:
    """Return (icon_svg, display_name) for a source URL."""
    parsed = urlparse(url)
    host = (parsed.netloc or "").lower().removeprefix("www.")
    path = parsed.path or ""

    if "reddit.com" in host:
        match = re.search(r"/r/([^/]+)", path)
        name = f"r/{match.group(1)}" if match else "Reddit"
        return _ICON_REDDIT, name
    if "news.google." in host or host == "news.google.com":
        return _ICON_NEWS, "Google News"
    if "arxiv.org" in host:
        return _ICON_ARXIV, "arXiv"
    return _ICON_LINK, host or "link"


def source_link(url: str) -> str:
    icon, name = source_label(url)
    return (
        f'<a class="src" href="{esc(url)}" title="{esc(url)}">'
        f"{icon}<span>{esc(name)}</span></a>"
    )


def today_iso() -> str:
    return datetime.datetime.now(tz=datetime.timezone.utc).strftime("%Y-%m-%d")


def format_display_date(iso: str) -> str:
    return datetime.date.fromisoformat(iso).strftime("%B %d, %Y")


def list_archive_dates() -> list[str]:
    """Return archived digest dates ascending (YYYY-MM-DD)."""
    root = config.ARCHIVE_DIR
    if not os.path.isdir(root):
        return []
    dates = [
        name
        for name in os.listdir(root)
        if _DATE_DIR_RE.match(name) and os.path.isfile(os.path.join(root, name, "index.html"))
    ]
    return sorted(dates)


def archive_href(target_date: str, *, from_archive: bool, latest_date: str) -> str:
    """Relative link from the current page to another day's digest."""
    if from_archive:
        if target_date == latest_date:
            return "../../index.html"
        return f"../{target_date}/"
    if target_date == latest_date:
        return "index.html"
    return f"archive/{target_date}/"


def date_nav_html(current: str, dates: list[str], *, from_archive: bool) -> str:
    latest = dates[-1] if dates else current
    idx = dates.index(current) if current in dates else -1
    prev_date = dates[idx - 1] if idx > 0 else None
    next_date = dates[idx + 1] if 0 <= idx < len(dates) - 1 else None

    if prev_date:
        prev = (
            f'<a class="nav-btn" href="{esc(archive_href(prev_date, from_archive=from_archive, latest_date=latest))}">'
            f"← {esc(format_display_date(prev_date))}</a>"
        )
    else:
        prev = '<span class="nav-btn disabled" aria-disabled="true">← Older</span>'

    if next_date:
        next_ = (
            f'<a class="nav-btn" href="{esc(archive_href(next_date, from_archive=from_archive, latest_date=latest))}">'
            f"{esc(format_display_date(next_date))} →</a>"
        )
    else:
        next_ = '<span class="nav-btn disabled" aria-disabled="true">Newer →</span>'

    return f"""
  <nav class="date-nav" aria-label="Digest date">
    <div class="date-nav-row alone">
      {prev}
      <div class="date-current">{esc(format_display_date(current))}</div>
      {next_}
    </div>
  </nav>
"""


def timeline_html(current: str, dates: list[str], *, from_archive: bool) -> str:
    """Right-rail vertical timeline of published digest dates (newest first)."""
    if not dates:
        dates = [current]
    latest = dates[-1]
    items = []
    for d in reversed(dates):
        day = datetime.date.fromisoformat(d)
        label = day.strftime("%b %d")
        year = day.strftime("%Y")
        href = archive_href(d, from_archive=from_archive, latest_date=latest)
        if d == current:
            items.append(
                f'<li class="tl-item current">'
                f'<span class="tl-dot" aria-hidden="true"></span>'
                f'<span class="tl-link">'
                f'<span class="tl-date">{esc(label)}</span>'
                f'<span class="tl-year">{esc(year)}</span>'
                f"</span></li>"
            )
        else:
            items.append(
                f'<li class="tl-item">'
                f'<span class="tl-dot" aria-hidden="true"></span>'
                f'<a class="tl-link" href="{esc(href)}">'
                f'<span class="tl-date">{esc(label)}</span>'
                f'<span class="tl-year">{esc(year)}</span>'
                f"</a></li>"
            )

    return f"""
  <aside class="timeline-rail" aria-label="Published digests">
    <div class="timeline-card">
      <div class="timeline-title">Timeline</div>
      <ol class="timeline">{"".join(items)}</ol>
    </div>
  </aside>
"""


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "section"


def section_pills_html(digest: dict) -> str:
    """Jump-link pills for main sections only."""
    topics = digest.get("trending_topics") or []
    questions = digest.get("top_questions") or []
    papers = digest.get("notable_papers") or []

    pills = [
        f'<a class="section-pill" href="#week-brief">Brief</a>',
        f'<a class="section-pill" href="#trending-topics">Topics'
        f'<span class="count">{len(topics)}</span></a>',
    ]
    if papers:
        pills.append(
            f'<a class="section-pill" href="#notable-papers">Papers'
            f'<span class="count">{len(papers)}</span></a>'
        )
    pills.append(
        f'<a class="section-pill" href="#top-questions">Questions'
        f'<span class="count">{len(questions)}</span></a>'
    )

    return f"""
  <nav class="section-nav" aria-label="On this page">
    <div class="section-pills">{"".join(pills)}</div>
  </nav>
"""


def fallback_overview(digest: dict) -> str:
    """Build a short week brief when the digest has no overview field yet."""
    topics = digest.get("trending_topics") or []
    papers = digest.get("notable_papers") or []
    questions = digest.get("top_questions") or []
    topic_bits = "; ".join(t["topic"] for t in topics[:4]) or "a mix of community threads"
    paper_bits = "; ".join(p["title"] for p in papers[:3])
    q_n = len(questions)
    parts = [
        f"This week’s conversation clustered around {topic_bits}.",
    ]
    if paper_bits:
        parts.append(f"On the research side, standouts included {paper_bits}.")
    parts.append(
        f"People asked {q_n} sharp questions spanning tools, models, and how to ship."
    )
    return " ".join(parts)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _topic_keys(topic: dict) -> set[str]:
    keys = {_norm(topic.get("topic", ""))}
    for url in topic.get("example_urls") or []:
        if url:
            keys.add(_norm(url))
    return {k for k in keys if k}


def _question_keys(question: dict) -> set[str]:
    keys = set()
    if question.get("source_url"):
        keys.add(_norm(question["source_url"]))
    if question.get("question"):
        keys.add(_norm(question["question"]))
    return keys


def _paper_keys(paper: dict) -> set[str]:
    keys = set()
    if paper.get("url"):
        keys.add(_norm(paper["url"]))
    if paper.get("title"):
        keys.add(_norm(paper["title"]))
    return keys


def _overlap_count(current: list[dict], previous: list[dict], key_fn) -> int:
    """Count current items that share any identity key with a previous item."""
    prev_keys: set[str] = set()
    for item in previous:
        prev_keys |= key_fn(item)
    if not prev_keys:
        return 0
    matched = 0
    for item in current:
        if key_fn(item) & prev_keys:
            matched += 1
    return matched


def load_previous_digest(current_date: str, dates: list[str]) -> tuple[str | None, dict | None]:
    """Return (previous_date, digest) for the publish before current_date."""
    if current_date not in dates:
        older = [d for d in dates if d < current_date]
    else:
        idx = dates.index(current_date)
        older = dates[:idx]
    if not older:
        return None, None
    prev_date = older[-1]
    path = os.path.join(config.ARCHIVE_DIR, prev_date, "digest.json")
    if not os.path.isfile(path):
        return prev_date, None
    with open(path) as f:
        return prev_date, json.load(f)


def compare_to_previous(digest: dict, previous: dict | None) -> dict[str, int] | None:
    if not previous:
        return None
    return {
        "topics": _overlap_count(
            digest.get("trending_topics") or [],
            previous.get("trending_topics") or [],
            _topic_keys,
        ),
        "questions": _overlap_count(
            digest.get("top_questions") or [],
            previous.get("top_questions") or [],
            _question_keys,
        ),
        "papers": _overlap_count(
            digest.get("notable_papers") or [],
            previous.get("notable_papers") or [],
            _paper_keys,
        ),
    }


def week_brief_html(
    digest: dict,
    *,
    prev_date: str | None = None,
    overlap: dict[str, int] | None = None,
) -> str:
    overview = (digest.get("overview") or "").strip() or fallback_overview(digest)
    topics_n = len(digest.get("trending_topics") or [])
    questions_n = len(digest.get("top_questions") or [])
    papers_n = len(digest.get("notable_papers") or [])

    if overlap and prev_date:
        label = format_display_date(prev_date)
        delta = f"""
    <p class="vs-last">
      Same as last publish ({esc(label)}):
      <span>{overlap['topics']} of {topics_n} topics</span>
      <span>{overlap['questions']} of {questions_n} questions</span>
      <span>{overlap['papers']} of {papers_n} papers</span>
    </p>"""
    else:
        delta = '<p class="vs-last">First publish in the archive — no prior digest to compare.</p>'

    return f"""
  <section class="week-brief" id="week-brief" aria-label="Week in brief">
    <h2>Week in brief</h2>
    <p class="overview">{esc(overview)}</p>
    {delta}
  </section>
"""


def render(
    digest: dict,
    *,
    date_iso: str,
    dates: list[str],
    from_archive: bool,
) -> str:
    prev_date, prev_digest = load_previous_digest(date_iso, dates)
    overlap = compare_to_previous(digest, prev_digest)
    section_nav = section_pills_html(digest)
    week_brief = week_brief_html(digest, prev_date=prev_date, overlap=overlap)

    topics_html = "".join(
        f"""<div class="card" id="{esc(slugify(t['topic']))}">
          <div class="meta">
            <span>{esc(t['post_count'])} posts</span>
            {" ".join(source_link(u) for u in t['example_urls']) if t['example_urls'] else ""}
          </div>
          <h3>{esc(t['topic'])}</h3>
          <p>{esc(t['summary'])}</p>
        </div>"""
        for t in digest["trending_topics"]
    )

    questions_html = "".join(
        f'<li><a href="{esc(q["source_url"])}">{esc(q["question"])}</a></li>'
        for q in digest["top_questions"]
    )

    papers = digest.get("notable_papers") or []
    papers_html = "".join(
        f"""<div class="card">
          <h3><a href="{esc(p['url'])}">{esc(p['title'])}</a></h3>
          <p>{esc(p['summary'])}</p>
        </div>"""
        for p in papers
    )
    papers_section = (
        f"""
  <h2 id="notable-papers">Notable papers <span style="font-size:.7em;font-weight:600">(this week)</span></h2>
  <div class="card-grid">{papers_html}</div>
"""
        if papers
        else ""
    )

    nav = date_nav_html(date_iso, dates, from_archive=from_archive)
    timeline = timeline_html(date_iso, dates, from_archive=from_archive)
    display = format_display_date(date_iso)
    favicon_href = "../../favicon.svg" if from_archive else "favicon.svg"

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI — Trending This Week · {esc(display)}</title>
<link rel="icon" href="{favicon_href}" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fredoka:wght@500;600;700&family=Nunito:wght@400;600;700&display=swap" rel="stylesheet">
<style>
  :root {{
    --ink: #1a1523;
    --paper: #fff8ef;
    --card: #ffffff;
    --coral: #ff5a5f;
    --mango: #ffb703;
    --lime: #8fd94f;
    --teal: #00c2a8;
    --sky: #4cc9f0;
    --link: #0b6e4f;
  }}
  html {{ scroll-behavior: smooth; }}
  body {{
    margin: 0;
    color: var(--ink);
    font-family: "Nunito", "Trebuchet MS", sans-serif;
    line-height: 1.55;
    background-color: #ffe8a3;
    background-image:
      radial-gradient(circle at 12% 18%, #ff8fab55 0 18%, transparent 19%),
      radial-gradient(circle at 88% 12%, #4cc9f055 0 16%, transparent 17%),
      radial-gradient(circle at 80% 78%, #8fd94f55 0 20%, transparent 21%),
      radial-gradient(circle at 18% 82%, #ffb70366 0 14%, transparent 15%),
      repeating-linear-gradient(
        -18deg,
        #ffe8a3 0 14px,
        #ffd56b 14px 28px
      );
    min-height: 100vh;
  }}
  .page {{
    max-width: 1280px;
    margin: 0 auto;
    padding: 2rem 1rem 3rem;
  }}
  .page-header {{ margin-bottom: .25rem; }}
  .body-row {{
    display: grid;
    grid-template-columns: minmax(0, 1fr) 160px;
    gap: 1.5rem;
    align-items: start;
  }}
  .main {{ min-width: 0; }}
  .timeline-rail {{
    position: sticky;
    top: 1rem;
    align-self: start;
    margin-top: 2.5rem; /* match first h2 so rail lines up with content body */
  }}
  .timeline-card {{
    border: 3px solid var(--ink);
    border-radius: 16px;
    background: var(--paper);
    box-shadow: 4px 4px 0 var(--coral);
    padding: .85rem .75rem 1rem;
  }}
  .timeline-title {{
    font-family: "Fredoka", "Nunito", sans-serif;
    font-weight: 700;
    font-size: .95rem;
    margin: 0 0 .85rem;
    text-align: center;
    padding: .2rem .4rem;
    background: var(--mango);
    border: 2px solid var(--ink);
    border-radius: 10px;
  }}
  .timeline {{
    list-style: none;
    margin: 0;
    padding: 0 0 0 0.85rem;
    position: relative;
  }}
  .timeline::before {{
    content: "";
    position: absolute;
    left: 0.35rem;
    top: .35rem;
    bottom: .35rem;
    width: 3px;
    background: var(--ink);
    border-radius: 2px;
  }}
  .tl-item {{
    position: relative;
    margin: 0 0 1rem;
    padding: 0;
    border: none;
    background: none;
    box-shadow: none;
    font-weight: 700;
  }}
  .tl-item:last-child {{ margin-bottom: 0; }}
  .tl-item:hover {{ transform: none; box-shadow: none; }}
  .tl-dot {{
    position: absolute;
    left: -0.72rem;
    top: .45rem;
    width: .7rem;
    height: .7rem;
    border-radius: 50%;
    background: #fff;
    border: 2.5px solid var(--ink);
    z-index: 1;
  }}
  .tl-item.current .tl-dot {{
    background: var(--coral);
    box-shadow: 0 0 0 3px #ff5a5f44;
  }}
  .tl-link {{
    display: flex;
    flex-direction: column;
    gap: .05rem;
    padding: .35rem .5rem;
    border: 2px solid transparent;
    border-radius: 10px;
    text-decoration: none;
    color: var(--ink);
    line-height: 1.2;
  }}
  a.tl-link:hover {{
    background: var(--sky);
    border-color: var(--ink);
    color: var(--ink);
  }}
  .tl-item.current .tl-link {{
    background: var(--ink);
    color: var(--mango);
    border-color: var(--ink);
  }}
  .tl-date {{ font-size: .88rem; }}
  .tl-year {{ font-size: .7rem; opacity: .75; font-weight: 600; }}
  .tl-item.current .tl-year {{ color: #ffe8a3; opacity: 1; }}
  h1 {{
    font-family: "Fredoka", "Nunito", sans-serif;
    font-weight: 700;
    font-size: clamp(2rem, 4vw, 3rem);
    letter-spacing: -0.02em;
    margin: 0 0 .85rem;
    display: inline-block;
    padding: .2rem .55rem .35rem;
    background: var(--ink);
    color: var(--mango);
    transform: rotate(-1.2deg);
    box-shadow: 6px 6px 0 var(--coral);
  }}
  .section-nav {{ margin-bottom: 1.25rem; }}
  .section-pills {{ display: flex; flex-wrap: wrap; gap: .5rem; }}
  .section-pill {{
    display: inline-flex; align-items: center; gap: .35rem;
    padding: .4rem .8rem; border-radius: 12px; text-decoration: none;
    font-size: .85rem; font-weight: 700; border: 2.5px solid var(--ink);
    color: var(--ink); background: var(--teal);
    box-shadow: 3px 3px 0 var(--ink);
    transition: transform .12s ease, box-shadow .12s ease;
  }}
  .section-pill:nth-child(2) {{ background: var(--mango); }}
  .section-pill:nth-child(3) {{ background: var(--sky); }}
  .section-pill:nth-child(4) {{ background: var(--lime); }}
  .section-pill:hover {{
    transform: translate(-2px, -2px);
    box-shadow: 5px 5px 0 var(--ink);
    color: var(--ink);
  }}
  .section-pill .count {{
    font-size: .72rem; font-weight: 800; padding: .1rem .4rem;
    border-radius: 8px; background: var(--ink); color: var(--mango);
  }}
  .week-brief {{
    margin: 0 0 1.5rem;
    padding: 1.1rem 1.2rem 1.25rem;
    border: 3px solid var(--ink);
    border-radius: 16px;
    background: var(--paper);
    box-shadow: 5px 5px 0 var(--teal);
  }}
  .week-brief h2 {{
    margin-top: 0;
    background: var(--coral);
    color: #fff;
  }}
  .week-brief .overview {{
    margin: .85rem 0 .75rem;
    font-size: 1.02rem;
    font-weight: 600;
  }}
  .week-brief .vs-last {{
    margin: 0;
    display: flex;
    flex-wrap: wrap;
    gap: .45rem .55rem;
    align-items: center;
    font-size: .88rem;
    font-weight: 700;
  }}
  .week-brief .vs-last span {{
    display: inline-block;
    padding: .2rem .55rem;
    border: 2px solid var(--ink);
    border-radius: 10px;
    background: #fff;
  }}
  .date-nav {{
    margin-bottom: 1.25rem; padding: .4rem .7rem; border: 2.5px solid var(--ink);
    border-radius: 12px; background: var(--paper);
    box-shadow: 3px 3px 0 var(--coral);
  }}
  .date-nav-row {{ display: flex; align-items: center; justify-content: space-between;
                  gap: .5rem; margin-bottom: .3rem; }}
  .date-nav-row.alone {{ margin-bottom: 0; }}
  .date-current {{
    font-family: "Fredoka", "Nunito", sans-serif;
    font-weight: 700; text-align: center; flex: 1; font-size: .95rem;
    line-height: 1.2;
  }}
  .nav-btn {{
    font-size: .78rem; font-weight: 700; text-decoration: none; color: var(--ink);
    white-space: nowrap; min-width: 5rem; padding: .15rem .35rem;
    border-radius: 8px; border: 2px solid transparent; line-height: 1.2;
  }}
  .nav-btn:hover:not(.disabled) {{
    background: var(--lime); border-color: var(--ink);
  }}
  .date-nav-row .nav-btn:last-child {{ text-align: right; }}
  .nav-btn.disabled {{ color: #1a152366; pointer-events: none; }}
  h2 {{
    font-family: "Fredoka", "Nunito", sans-serif;
    font-weight: 700; font-size: 1.65rem; margin-top: 2.5rem;
    scroll-margin-top: 1rem; display: inline-block;
    padding: .15rem .55rem; background: var(--mango);
    border: 2.5px solid var(--ink); box-shadow: 4px 4px 0 var(--ink);
    transform: rotate(-0.6deg);
  }}
  #top-questions {{ background: var(--lime); }}
  #notable-papers {{ background: var(--sky); }}
  .card-grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr));
               column-gap: .85rem; row-gap: 4rem; margin: .85rem 0 1.25rem; }}
  @media (max-width: 1100px) {{
    .card-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
  }}
  @media (max-width: 860px) {{
    .body-row {{ grid-template-columns: 1fr; }}
    .timeline-rail {{
      position: static;
      order: -1;
      margin-top: 0;
      margin-bottom: .5rem;
    }}
    .timeline {{
      display: flex; flex-wrap: wrap; gap: .5rem; padding: 0;
    }}
    .timeline::before {{ display: none; }}
    .tl-item {{ margin: 0; }}
    .tl-dot {{ display: none; }}
    .tl-link {{ flex-direction: row; align-items: baseline; gap: .35rem; }}
  }}
  @media (max-width: 640px) {{
    .card-grid {{ grid-template-columns: 1fr; }}
    h1 {{ transform: none; }}
  }}
  .card {{
    border: 3px solid var(--ink); border-radius: 16px; padding: 1rem 1.15rem;
    margin: 0; scroll-margin-top: 1rem; height: 100%;
    display: flex; flex-direction: column; background: var(--card);
    box-shadow: 5px 5px 0 var(--ink);
    transition: transform .15s ease, box-shadow .15s ease, background .15s ease;
  }}
  .card:nth-child(4n+1) {{ background: #fff7fb; }}
  .card:nth-child(4n+2) {{ background: #f3fffa; }}
  .card:nth-child(4n+3) {{ background: #fffbeb; }}
  .card:nth-child(4n+4) {{ background: #f2fbff; }}
  .card:hover {{
    transform: translate(-3px, -3px) rotate(-0.5deg);
    box-shadow: 8px 8px 0 var(--coral);
  }}
  .card:nth-child(even):hover {{
    transform: translate(-3px, -3px) rotate(0.5deg);
    box-shadow: 8px 8px 0 var(--teal);
  }}
  .card:target {{ outline: 3px solid var(--mango); outline-offset: 3px; }}
  .card h3 {{
    margin: 0 0 .45rem;
    font-family: "Fredoka", "Nunito", sans-serif;
    font-weight: 600; font-size: 1.05rem; line-height: 1.25;
  }}
  .card h3 a {{ color: inherit; text-decoration: none; }}
  .card h3 a:hover {{ color: var(--link); text-decoration: underline; }}
  .card p {{ margin: 0; flex: 1; font-size: .92rem; }}
  .card .meta {{ margin: 0 0 .65rem; }}
  .meta {{ display: flex; flex-wrap: wrap; align-items: center; gap: .45rem .55rem;
          font-size: .85rem; color: #5a5160; font-weight: 600; }}
  .src {{
    display: inline-flex; align-items: center; gap: .3rem;
    padding: .15rem .55rem .15rem .3rem; border-radius: 10px;
    background: #fff; color: inherit; text-decoration: none;
    font-size: .78rem; border: 2px solid var(--ink); font-weight: 700;
  }}
  .src:hover {{ background: var(--mango); color: var(--ink); }}
  .src-icon {{ width: 1rem; height: 1rem; flex-shrink: 0; }}
  .main > ul {{ padding-left: 0; list-style: none; }}
  .main > ul > li {{
    margin: .65rem 0; padding: .75rem 1rem; background: var(--paper);
    border: 2.5px solid var(--ink); border-radius: 14px;
    box-shadow: 3px 3px 0 var(--teal); font-weight: 600;
  }}
  .main > ul > li:hover {{ transform: translate(-2px, -2px); box-shadow: 5px 5px 0 var(--coral); }}
  a {{ color: var(--link); }}
  footer {{
    margin-top: 3rem; padding: 1rem 1.1rem; border: 3px solid var(--ink);
    border-radius: 16px; background: var(--ink); color: #ffe8a3;
    font-size: .9rem; font-weight: 600; box-shadow: 5px 5px 0 var(--mango);
  }}
</style>
</head>
<body>
  <div class="page">
  <header class="page-header">
  <h1>AI — Trending This Week</h1>
  {section_nav}
  {nav}
  </header>
  <div class="body-row">
  <div class="main">
  {week_brief}
  <h2 id="trending-topics">Trending topics</h2>
  <div class="card-grid">{topics_html}</div>
{papers_section}
  <h2 id="top-questions">Top questions</h2>
  <ul>{questions_html}</ul>
  <footer>
    Sourced from public Reddit AI communities, Google News, and arXiv
    (cs.AI / cs.LG / cs.CL), summarized by AI. Links go to the original posts,
    articles, and papers.
  </footer>
  </div>
  {timeline}
  </div>
  </div>
</body>
</html>"""


def _write(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        f.write(content)


def main() -> None:
    with open(config.DIGEST_FILE) as f:
        digest = json.load(f)

    date_iso = today_iso()
    day_dir = os.path.join(config.ARCHIVE_DIR, date_iso)
    os.makedirs(day_dir, exist_ok=True)

    # Persist this run's digest into the archive (overwrites same-day re-runs).
    shutil.copy2(config.DIGEST_FILE, os.path.join(day_dir, "digest.json"))

    # Ensure today's folder exists before listing so nav includes it.
    dates = list_archive_dates()
    if date_iso not in dates:
        dates = sorted(dates + [date_iso])

    root_html = render(digest, date_iso=date_iso, dates=dates, from_archive=False)
    archive_html = render(digest, date_iso=date_iso, dates=dates, from_archive=True)

    _write(config.OUTPUT_HTML, root_html)
    _write(os.path.join(day_dir, "index.html"), archive_html)

    # Re-render older archive pages so their next/prev chips stay current.
    for older in dates:
        if older == date_iso:
            continue
        older_digest_path = os.path.join(config.ARCHIVE_DIR, older, "digest.json")
        if not os.path.isfile(older_digest_path):
            continue
        with open(older_digest_path) as f:
            older_digest = json.load(f)
        _write(
            os.path.join(config.ARCHIVE_DIR, older, "index.html"),
            render(older_digest, date_iso=older, dates=dates, from_archive=True),
        )

    print(f"Wrote {config.OUTPUT_HTML} and {day_dir}/index.html ({len(dates)} day(s) archived)")


if __name__ == "__main__":
    main()
