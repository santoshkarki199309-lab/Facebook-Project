# History Unsealed — automated Facebook Page

Fully automated, $0 publishing pipeline for the **History Unsealed** Facebook Page
(historical mysteries & untold stories, global English audience).

```
Claude scheduled task (daily)          GitHub Actions (6× daily)
  research + fact-check  ──►  content/queue/YYYY-MM-DD.json  ──►  real archive media
  write captions/scripts           (validated on push)              (Wikimedia Commons) + brand
                                                                    voiceover + captions (reels)
                                                                    publish via Graph API
        ▲                                                                   │
        └──────────── content/state/insights.json ◄── weekly insights ◄─────┘
```

| Slot | UTC | Dubai | Type |
|---|---|---|---|
| c | 02:07 | 06:07 | Photo — debate / On This Day |
| b | 12:47 | 16:47 | Reel — myth-buster / did-you-know (35–55 s) |
| e | 14:41 | 18:41 | Photo — famous photo story / strange true fact |
| a | 16:52 | 20:52 | Photo story |
| f | 21:37 | 01:37 | Long documentary video (4–6 min, 16:9) |
| d | 23:13 | 03:13 | Reel — strongest story of the day (US prime time) |

All visuals are real archive photographs, paintings, documents and film from Wikimedia Commons
(public domain / CC0 / CC BY / CC BY-SA), credited in each post's first comment. No AI images.

## Layout

- `bot/` — Python publisher (images, branding, TTS, reels, Graph API, validator, insights)
- `content/queue/` — one JSON file per UTC date, six posts each
- `content/state/` — what was published (`posted.json`) and weekly performance (`insights.json`)
- `prompts/content_brief.md` — editorial rules the content task follows
- `.github/workflows/` — `publish`, `insights`, `validate`, `check`

## Run locally

```bash
pip install -r requirements.txt          # plus ffmpeg and fonts-dejavu-core
python -m bot.validate
python -m bot.publish --slot b --date 2026-10-17 --dry-run --offline   # no network, placeholders
```

First-time setup: see [SETUP.md](SETUP.md).
