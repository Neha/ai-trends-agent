"""Step 1 — Fetch trending AI news, announcements, and papers (no API keys).

Pulls:
  1. Recent Reddit posts via Arctic Shift (free archive API).
  2. Reddit public Atom RSS as fallback.
  3. Google News RSS for AI / LLM headlines.
  4. arXiv Atom API for recent cs.AI / cs.LG / cs.CL papers.

Also tries Reddit JSON / PullPush if the above fail.
Writes raw_posts.json. Read-only; never posts or comments.
"""

from __future__ import annotations

import datetime
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

import config

_HEADERS = {
    "User-Agent": config.USER_AGENT,
    "Accept": "application/json, application/atom+xml, application/rss+xml, */*",
}

_TAG_RE = re.compile(r"<[^>]+>")


def _get(url: str, timeout: int = 45) -> bytes:
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _strip_html(text: str) -> str:
    return _TAG_RE.sub("", text or "").strip()


def _week_ago() -> datetime.datetime:
    return datetime.datetime.now(tz=datetime.timezone.utc) - datetime.timedelta(days=7)


def _normalize_reddit(item: dict, sub: str) -> dict:
    permalink = item.get("permalink") or ""
    if permalink.startswith("/"):
        url = f"https://reddit.com{permalink}"
    else:
        url = item.get("url") or f"https://reddit.com/r/{sub}"
    created = item.get("created_utc") or time.time()
    return {
        "id": str(item.get("id") or item.get("fullname") or url),
        "subreddit": sub,
        "source": "reddit",
        "title": item.get("title") or "(no title)",
        "body": (item.get("selftext") or "")[:2000],
        "score": int(item.get("score") or 0),
        "num_comments": int(item.get("num_comments") or 0),
        "url": url,
        "created": datetime.datetime.fromtimestamp(
            float(created), tz=datetime.timezone.utc
        ).isoformat(),
    }


def _engagement(post: dict) -> int:
    """Upvotes + comments — primary ranking signal for Reddit posts."""
    return int(post.get("score") or 0) + int(post.get("num_comments") or 0)


def fetch_arctic_shift(sub: str, limit: int) -> list[dict]:
    """Free Reddit archive API — no key. Keep the week's most-engaged posts."""
    # Pull a wider window, then rank by engagement (API only sorts by date).
    params = urllib.parse.urlencode(
        {
            "subreddit": sub,
            "limit": min(max(limit * 2, 80), 100),
            "after": _week_ago().strftime("%Y-%m-%d"),
            "sort": "desc",
        }
    )
    url = f"https://arctic-shift.photon-reddit.com/api/posts/search?{params}"
    data = json.loads(_get(url))
    items = data.get("data") or []
    posts = [_normalize_reddit(item, sub) for item in items]
    cutoff = _week_ago().isoformat()
    recent = [p for p in posts if p["created"] >= cutoff] or posts
    recent.sort(key=_engagement, reverse=True)
    return recent[:limit]


def fetch_reddit_rss(sub: str, limit: int) -> list[dict]:
    """Public Reddit Atom feed — no key."""
    url = f"https://www.reddit.com/r/{sub}/.rss"
    raw = _get(url)
    root = ET.fromstring(raw)
    ns = {"a": "http://www.w3.org/2005/Atom"}
    posts: list[dict] = []
    for entry in root.findall("a:entry", ns)[:limit]:
        title = (entry.findtext("a:title", default="", namespaces=ns) or "").strip()
        link_el = entry.find("a:link", ns)
        link = link_el.get("href") if link_el is not None else ""
        content = entry.findtext("a:content", default="", namespaces=ns) or ""
        updated = entry.findtext("a:updated", default="", namespaces=ns) or ""
        entry_id = entry.findtext("a:id", default="", namespaces=ns) or link
        if not title or not link:
            continue
        try:
            created = datetime.datetime.fromisoformat(updated.replace("Z", "+00:00"))
        except ValueError:
            created = datetime.datetime.now(tz=datetime.timezone.utc)
        posts.append(
            {
                "id": entry_id.split("/")[-1] if "/" in entry_id else entry_id,
                "subreddit": sub,
                "source": "reddit",
                "title": title,
                "body": _strip_html(content)[:2000],
                "score": 0,
                "num_comments": 0,
                "url": link,
                "created": created.isoformat(),
            }
        )
    return posts


def fetch_reddit_json(sub: str, limit: int) -> list[dict]:
    url = (
        f"https://www.reddit.com/r/{sub}/top.json"
        f"?t={config.TIME_FILTER}&limit={limit}&raw_json=1"
    )
    data = json.loads(_get(url))
    children = data.get("data", {}).get("children", [])
    return [_normalize_reddit(c.get("data", {}), sub) for c in children if c.get("data")]


def fetch_pullpush(sub: str, limit: int) -> list[dict]:
    params = urllib.parse.urlencode(
        {
            "subreddit": sub,
            "size": min(limit, 100),
            "sort": "desc",
            "sort_type": "score",
            "after": int(_week_ago().timestamp()),
        }
    )
    url = f"https://api.pullpush.io/reddit/search/submission/?{params}"
    data = json.loads(_get(url))
    return [_normalize_reddit(item, sub) for item in (data.get("data") or [])]


def fetch_subreddit(sub: str, limit: int) -> list[dict]:
    # Prefer Reddit "top this week" (vote-ranked). Fallbacks also re-rank by engagement.
    strategies = (
        ("Reddit JSON", fetch_reddit_json),
        ("Arctic Shift", fetch_arctic_shift),
        ("PullPush", fetch_pullpush),
        ("Reddit RSS", fetch_reddit_rss),
    )
    for name, fn in strategies:
        try:
            posts = fn(sub, limit)
            if posts:
                print(f"  r/{sub}: {len(posts)} via {name}")
                return posts
            print(f"  r/{sub}: {name} empty")
        except Exception as e:
            print(f"  r/{sub}: {name} failed ({e})")
    return []


def fetch_google_news(limit: int) -> list[dict]:
    query = urllib.parse.quote_plus(config.NEWS_QUERY)
    url = (
        f"https://news.google.com/rss/search?q={query}"
        f"&hl=en-US&gl=US&ceid=US:en"
    )
    try:
        raw = _get(url)
    except Exception as e:
        print(f"  news: skipped ({e})")
        return []

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        print(f"  news: bad RSS ({e})")
        return []

    items: list[dict] = []
    for item in root.findall("./channel/item")[:limit]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        description = _strip_html(item.findtext("description") or "")
        pub = item.findtext("pubDate") or ""
        try:
            created = datetime.datetime.strptime(
                pub, "%a, %d %b %Y %H:%M:%S %Z"
            ).replace(tzinfo=datetime.timezone.utc)
        except ValueError:
            created = datetime.datetime.now(tz=datetime.timezone.utc)

        if not title or not link:
            continue
        items.append(
            {
                "id": f"news-{abs(hash(link))}",
                "subreddit": "google_news",
                "source": "news",
                "title": title,
                "body": description[:2000],
                "score": 0,
                "num_comments": 0,
                "url": link,
                "created": created.isoformat(),
            }
        )
    return items


def fetch_arxiv(limit: int) -> list[dict]:
    """Recent AI / ML / NLP papers via the public arXiv Atom API — no key."""
    params = urllib.parse.urlencode(
        {
            "search_query": config.ARXIV_QUERY,
            "start": 0,
            "max_results": min(limit, 50),
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
    )
    url = f"https://export.arxiv.org/api/query?{params}"
    try:
        raw = _get(url)
    except Exception as e:
        print(f"  arxiv: skipped ({e})")
        return []

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        print(f"  arxiv: bad Atom ({e})")
        return []

    ns = {
        "a": "http://www.w3.org/2005/Atom",
        "arxiv": "http://arxiv.org/schemas/atom",
    }
    items: list[dict] = []
    for entry in root.findall("a:entry", ns)[:limit]:
        title = _strip_html(entry.findtext("a:title", default="", namespaces=ns) or "")
        title = re.sub(r"\s+", " ", title).strip()
        summary = _strip_html(
            entry.findtext("a:summary", default="", namespaces=ns) or ""
        )
        summary = re.sub(r"\s+", " ", summary).strip()
        published = entry.findtext("a:published", default="", namespaces=ns) or ""
        entry_id = entry.findtext("a:id", default="", namespaces=ns) or ""

        link = ""
        for link_el in entry.findall("a:link", ns):
            if link_el.get("type") == "text/html" or link_el.get("rel") == "alternate":
                link = link_el.get("href") or ""
                break
        if not link:
            link = entry_id

        if not title or not link:
            continue

        try:
            created = datetime.datetime.fromisoformat(published.replace("Z", "+00:00"))
        except ValueError:
            created = datetime.datetime.now(tz=datetime.timezone.utc)

        authors = [
            (a.findtext("a:name", default="", namespaces=ns) or "").strip()
            for a in entry.findall("a:author", ns)
        ]
        author_line = ", ".join(a for a in authors if a)[:300]
        body = summary[:1800]
        if author_line:
            body = f"Authors: {author_line}\n\n{body}"

        items.append(
            {
                "id": entry_id.split("/abs/")[-1] if "/abs/" in entry_id else entry_id,
                "subreddit": "arxiv",
                "source": "paper",
                "title": title,
                "body": body[:2000],
                "score": 0,
                "num_comments": 0,
                "url": link,
                "created": created.isoformat(),
            }
        )
    return items


def fetch_posts() -> list[dict]:
    posts: list[dict] = []

    for sub in config.SUBREDDITS:
        batch = fetch_subreddit(sub, config.POSTS_PER_SUB)
        posts.extend(batch)
        print(f"  running total: {len(posts)}")
        time.sleep(0.5)

    news = fetch_google_news(config.NEWS_LIMIT)
    posts.extend(news)
    print(f"  news: {len(news)} articles (running total {len(posts)})")

    # Papers are a weekly section — only hit arXiv on refresh day (or first run).
    refresh_papers = (
        datetime.datetime.now(tz=datetime.timezone.utc).weekday()
        == config.PAPERS_REFRESH_WEEKDAY
        or not os.path.isfile(config.WEEKLY_PAPERS_FILE)
    )
    if refresh_papers:
        papers = fetch_arxiv(config.ARXIV_LIMIT)
        posts.extend(papers)
        print(f"  arxiv: {len(papers)} papers (weekly refresh; running total {len(posts)})")
    else:
        print("  arxiv: skipped (notable papers refresh weekly; using cache at analyze)")

    # Dedupe, then rank: Reddit by upvotes+comments; news/papers keep source order
    # but sit after engaged Reddit posts of similar recency.
    seen: set[str] = set()
    unique: list[dict] = []
    for p in posts:
        if p["url"] in seen:
            continue
        seen.add(p["url"])
        unique.append(p)

    def _rank_key(p: dict) -> tuple:
        source = p.get("source", "reddit")
        # Reddit first by engagement; news/papers after (no vote signal).
        bucket = 0 if source == "reddit" else 1 if source == "news" else 2
        return (bucket, -_engagement(p), p.get("created") or "")

    unique.sort(key=_rank_key)
    return unique


def main() -> None:
    print("Fetching posts (Reddit + Google News + arXiv)...")
    posts = fetch_posts()
    with open(config.RAW_POSTS_FILE, "w") as f:
        json.dump(posts, f, indent=2)
    print(f"Wrote {len(posts)} posts to {config.RAW_POSTS_FILE}")


if __name__ == "__main__":
    main()
