# AGENTS.md — instructions for AI coding agents (Codex, Claude, etc.)

This repo runs the **History Unsealed** Facebook Page: real history stories, 6 posts a day,
real archive visuals only. Publishing is fully automatic in GitHub Actions. The only job an
AI agent does every day is **writing the content queue**.

## How the system works

```
Agent (daily)                         GitHub Actions (automatic)
 research + write posts  ──►  content/queue/YYYY-MM-DD.json  ──►  publish.yml (6× daily)
                                                                    - finds real archive media on
                                                                      Wikimedia Commons
                                                                    - renders photo / reel / long video
                                                                    - posts to Facebook + sources comment
                                                                    - records content/state/posted.json
```

- `bot/` — Python publisher (`publish.py` entry point, `media.py` Commons search, `video.py`
  renderer, `facebook.py` Graph API, `validate.py` queue checks).
- `content/queue/` — one JSON file per UTC date with 6 posts (slots c, b, e, a, f, d).
- `content/state/posted.json` — what has been published (written by Actions; don't edit).
- `content/state/image_preview.json` — which archive image each upcoming item will use
  (written by Actions; items with `"hit": null` need better search queries).
- `content/state/insights.json` — weekly performance (written by Actions).
- `prompts/content_brief.md` — **the editorial rules. Read it fully before writing content.**

## The daily task

1. Read `prompts/content_brief.md` completely and follow it exactly.
2. Read `content/state/posted.json`, `insights.json`, `image_preview.json` and the queue files.
3. Fix first: for today or later, replace `image_search` / `video_search` queries of items whose
   preview `hit` is null (only those fields).
4. For each UTC date from today through today + 4: create the file if missing, or add missing
   slots. **Never change the text of a post that already exists.** Do today first.
5. Research every post on the web: true stories only, at least 2 reputable sources per post
   (3+ for the long video). Never invent facts, quotes or numbers.
6. Validate: `pip install -r requirements.txt` then
   `python -m bot.validate --from-today` must report 0 problems.
7. Commit after each day: `git pull --rebase` then commit `content: queue YYYY-MM-DD` and push to `main`.
8. Finish with a short summary: dates filled, topic per slot, anything skipped and why.

## Hard rules

- **No AI images.** Visuals come only from Wikimedia Commons via `image_search` /
  `video_search` (or a verified `image_url` + licence + credit). Never add `image_prompt`.
- Engagement bait is banned ("like if", "share if", "tag a friend", "comment YES", …).
- Do **not** edit `.github/workflows/`, `bot/`, secrets, or state files unless the owner asks.
  The daily task only touches `content/queue/`.
- Never print, commit or request access tokens. Facebook/GitHub secrets live only in
  GitHub → Settings → Secrets.

## Useful commands

```bash
python -m bot.validate --from-today                  # check the queue
python -m bot.publish --slot b --date YYYY-MM-DD --dry-run --offline   # local test render
python -m bot.media YYYY-MM-DD                        # preview which archive images will be used
```

## Troubleshooting (for the owner)

- Publish runs fail with OAuthException / code 190 → the Facebook token was invalidated
  (password change or a Facebook security checkpoint). Clear any checkpoint, then redo
  SETUP.md step 1 (Explorer → Debugger → **Extend** → `me/accounts`, check "Expires: Never")
  and update the `FB_PAGE_TOKEN` secret.
- "No queued content" → the daily content task didn't run; run it manually.
