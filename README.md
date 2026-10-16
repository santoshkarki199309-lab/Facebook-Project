# History Unsealed — automated Facebook Page

Fully automated, $0 publishing pipeline for the **History Unsealed** Facebook Page
(historical mysteries & untold stories, global English audience).

```
Claude scheduled task (Mon & Thu)          GitHub Actions (3× daily)
  research + fact-check  ──►  content/queue/YYYY-MM-DD.json  ──►  generate image(s)
  write captions/scripts           (validated on push)              brand + AI label
                                                                    voiceover + captions (reels)
                                                                    publish via Graph API
        ▲                                                                   │
        └──────────── content/state/insights.json ◄── weekly insights ◄─────┘
```

| Slot | UTC | Dubai | Type |
|---|---|---|---|
| a | 12:47 | 16:47 | Photo story |
| b | 17:52 | 21:52 | Reel (45–75 s, AI voiceover, burned-in captions) |
| c | 00:13 | 04:13 | Photo debate / did-you-know |

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
