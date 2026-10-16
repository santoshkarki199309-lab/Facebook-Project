# History Unsealed — automated Facebook Page

Fully automated, $0 publishing pipeline for the **History Unsealed** Facebook Page
(historical mysteries & untold stories, global English audience).

```
Claude scheduled task (Mon & Thu)          GitHub Actions (4× daily)
  research + fact-check  ──►  content/queue/YYYY-MM-DD.json  ──►  generate image(s)
  write captions/scripts           (validated on push)              brand + AI label
                                                                    voiceover + captions (reels)
                                                                    publish via Graph API
        ▲                                                                   │
        └──────────── content/state/insights.json ◄── weekly insights ◄─────┘
```

| Slot | UTC | Dubai | Type |
|---|---|---|---|
| b | 12:47 | 16:47 | Reel — myth-buster / did-you-know (35–55 s) |
| a | 16:52 | 20:52 | Photo story |
| d | 23:13 | 03:13 | Reel — strongest story of the day (US prime time) |
| c | 02:07 | 06:07 | Photo — debate / On This Day |

## Layout

- `bot/` — Python publisher (images, branding, TTS, reels, Graph API, validator, insights)
- `content/queue/` — one JSON file per UTC date, three posts each
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
