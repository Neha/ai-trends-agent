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

    # Jump chips only when there are other days — avoid duplicating today's date.
    other_dates = [d for d in reversed(dates) if d != current]
    if other_dates:
        chips = []
        for d in other_dates:
            label = datetime.date.fromisoformat(d).strftime("%b %d")
            href = archive_href(d, from_archive=from_archive, latest_date=latest)
            chips.append(f'<a class="date-chip" href="{esc(href)}">{esc(label)}</a>')
        chips_html = (
            f'<div class="date-chips" aria-label="Other digests">{"".join(chips)}</div>'
        )
        row_class = "date-nav-row"
    else:
        chips_html = ""
        row_class = "date-nav-row alone"

    return f"""
  <nav class="date-nav" aria-label="Digest date">
    <div class="{row_class}">
      {prev}
      <div class="date-current">{esc(format_display_date(current))}</div>
      {next_}
    </div>
    {chips_html}
  </nav>
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


def render(
    digest: dict,
    *,
    date_iso: str,
    dates: list[str],
    from_archive: bool,
) -> str:
    section_nav = section_pills_html(digest)

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
  <h2 id="notable-papers">Notable papers</h2>
  <div class="card-grid">{papers_html}</div>
"""
        if papers
        else ""
    )

    nav = date_nav_html(date_iso, dates, from_archive=from_archive)
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
    max-width: 1200px;
    margin: 0 auto;
    padding: 2rem 1rem 3rem;
  }}
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
  .section-pill:hover {{
    transform: translate(-2px, -2px);
    box-shadow: 5px 5px 0 var(--ink);
    color: var(--ink);
  }}
  .section-pill .count {{
    font-size: .72rem; font-weight: 800; padding: .1rem .4rem;
    border-radius: 8px; background: var(--ink); color: var(--mango);
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
  .date-chips {{ display: flex; flex-wrap: wrap; gap: .3rem; justify-content: flex-end; }}
  .date-chip {{
    font-size: .7rem; font-weight: 700; padding: .1rem .45rem; border-radius: 8px;
    background: #fff; color: var(--ink); text-decoration: none;
    border: 2px solid var(--ink); line-height: 1.2;
  }}
  .date-chip:hover {{ background: var(--sky); }}
  .date-chip.current {{ background: var(--coral); color: #fff; }}
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
  @media (max-width: 1000px) {{
    .card-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
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
  ul {{ padding-left: 0; list-style: none; }}
  li {{
    margin: .65rem 0; padding: .75rem 1rem; background: var(--paper);
    border: 2.5px solid var(--ink); border-radius: 14px;
    box-shadow: 3px 3px 0 var(--teal); font-weight: 600;
  }}
  li:hover {{ transform: translate(-2px, -2px); box-shadow: 5px 5px 0 var(--coral); }}
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
  <h1>AI — Trending This Week</h1>
  {section_nav}
  {nav}

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
