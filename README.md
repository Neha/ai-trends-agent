# AI Trends Agent

I got tired of skimming Reddit, news, and arXiv every week and still missing the plot. This is a small agent that pulls the noisy bits, ranks Reddit by upvotes + comments, and publishes one static page on Fridays — something I can actually finish with coffee.

![Screenshot of the weekly AI digest page](docs/screenshot.png)

## What you get

A weekly digest page (`index.html`) with:

- **Week in brief** — short overview of the week, plus how much overlaps with the last publish (topics / questions / papers)
- **Trending topics** — clustered from the week’s discussion
- **Notable papers** — a handful of arXiv standouts
- **Top questions** — what people were actually asking

Also:

- jump links for Brief / Topics / Papers / Questions
- older/newer date controls
- a right-side **Timeline** of publish dates (`archive/YYYY-MM-DD/`)
- funky theme, favicon, source pills (subreddit / Google News / arXiv)

## Cadence

This is a **weekly** digest, not daily.

| When | What |
|---|---|
| **Friday 07:00 UK** (BST; `06:00 UTC`) | Full publish — topics, questions, papers, overview |
| Manual / local | `python run.py` anytime for testing |

Daily didn’t make sense: Reddit is pulled with a week window, so Tue–Thu pages mostly reshuffled the same threads. Friday is the pulse.

## Where the data comes from

| Source | What |
|---|---|
| Reddit | Top-ish posts from the last week, ranked by upvotes + comments |
| Google News | AI / LLM / lab headlines via RSS |
| arXiv | Recent `cs.AI`, `cs.LG`, `cs.CL` papers |

Reddit is the engagement-heavy part. News/papers don’t have useful “likes,” so those are recent + whatever the model flags.

Subs right now: `MachineLearning`, `LocalLLaMA`, `OpenAI`, `artificial`, `ChatGPT`, `ClaudeAI`, `claude`, `singularity`, `LangChain`, `womenin_AI`. Edit `config.py` to change them.

## Pipeline

Three scripts, files in between:

```
fetch.py    → raw_posts.json
analyze.py  → digest.json (+ weekly_papers.json on Friday)
render.py   → index.html + archive/YYYY-MM-DD/
```

Or:

```bash
python run.py
```

### How days are stored

```
index.html                 ← latest digest
favicon.svg
weekly_papers.json         ← Friday paper picks (for local mid-week reuse)
archive/
  YYYY-MM-DD/
    index.html
    digest.json            ← kept so older pages / comparisons can be rebuilt
```

The Timeline and “same as last publish” line both read from `archive/`.

## Setup

Python 3.10+. You need a Cursor API key ([dashboard](https://cursor.com/dashboard/api)) — fetching uses public endpoints only.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# put CURSOR_API_KEY in .env
python run.py
open index.html
```

Single steps if you’re debugging:

```bash
python fetch.py
python analyze.py
python render.py
```

## Cost

One Cursor agent call per Friday publish (~4–5 runs/month if you only use the schedule). Fetch + `render.py` + GitHub Pages are free at this scale.

Tip: when you’re only tweaking CSS/layout, run `python render.py` — don’t re-pay for analyze.

## Deploy on GitHub Pages (Fridays)

Workflow: `.github/workflows/daily.yml` (name in the UI: **AI trends digest**).

It runs **Friday at 07:00 UK** during BST (`06:00 UTC`; 06:00 UK in winter/GMT), or whenever you hit **Run workflow**. Then it:

1. builds the digest
2. commits `index.html`, `archive/`, `favicon.svg`, `weekly_papers.json`
3. deploys to Pages

Setup:

1. Push this repo to GitHub (if it isn’t already).
2. **Settings → Secrets and variables → Actions → New repository secret**
   - Name: `CURSOR_API_KEY`
   - Value: from https://cursor.com/dashboard/api  
   (use the **Secrets** tab, not Variables)
3. **Settings → Pages → Source: GitHub Actions**
4. **Actions → AI trends digest → Run workflow** once

Site URL:

**https://neha.github.io/ai-trends-agent/**

Older weeks: `/archive/YYYY-MM-DD/`.

Local cron instead of Actions:

```bash
0 6 * * 5 cd /path/to/ai-trends-agent && .venv/bin/python run.py
```

## Tweaking

`config.py` has the knobs: subreddit list, posts per sub, news/arXiv queries, model (`composer-2.5` by default), `DIGEST_WEEKDAYS` / `PAPERS_REFRESH_WEEKDAY` (Friday = `5`).

## Contributing

Open to contributions — PRs welcome.

Useful directions: better sources, ranking tweaks, UI polish, tests, docs. Fork, branch off `main`, open a PR with a short note on what changed and how you checked it. Not sure it fits? Open an issue first.

## License

[MIT](LICENSE) — use it, fork it, break it, improve it.
