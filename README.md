# AI Trends Agent

I built this because I kept losing track of what actually mattered in AI that week — Reddit threads, random news hits, arXiv drops. So this script pulls the noisy bits, ranks the Reddit stuff by upvotes + comments, and spits out one page I can skim with coffee.

![Screenshot of the weekly AI digest page](docs/screenshot.png)

## What you get

A static `index.html` with:

- trending topics (clustered from the week’s discussion)
- a few notable papers
- questions people were actually asking

Jump links at the top, date nav so older digests stick around under `archive/`, funky theme because plain cards were boring.

## Where the data comes from

| Source | What |
|---|---|
| Reddit | Top-ish posts from the last week across a handful of AI subs |
| Google News | AI / LLM / lab headlines via RSS |
| arXiv | Recent `cs.AI`, `cs.LG`, `cs.CL` papers |

Reddit is the engagement-heavy part (score + comments). News and papers don’t really have “likes,” so those are just recent + whatever the model thinks is interesting.

Subs right now: `MachineLearning`, `LocalLLaMA`, `OpenAI`, `artificial`, `ChatGPT`, `ClaudeAI`, `claude`, `singularity`, `LangChain`, `womenin_AI`. Edit `config.py` if you want different ones.

## Pipeline

Nothing fancy — three scripts, files in between:

```
fetch.py    → raw_posts.json
analyze.py  → digest.json      (Cursor agent does the clustering)
render.py   → index.html
```

Or just:

```bash
python run.py
```

## Setup

Python 3.10+. You need a Cursor API key ([dashboard](https://cursor.com/dashboard/api)) — fetch itself is free / public endpoints.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# put CURSOR_API_KEY in .env
python run.py
open index.html
```

You can also run steps alone if you’re debugging:

```bash
python fetch.py
python analyze.py
python render.py
```

## Cost / hosting

One Cursor agent call per run. That’s the only paid bit. The HTML is self-contained — open it locally, or wire up the GitHub Action in `.github/workflows/daily.yml` for daily Pages deploys (drop `CURSOR_API_KEY` in Actions secrets, turn on Pages → GitHub Actions).

## Tweaking

Most knobs are in `config.py`: subreddit list, posts per sub, news query, arXiv query, model name. Defaults are fine if you just want to try it.
