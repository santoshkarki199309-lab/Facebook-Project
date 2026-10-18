"""Central configuration. Secrets come from environment variables (GitHub Actions secrets)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUEUE_DIR = ROOT / "content" / "queue"
STATE_FILE = ROOT / "content" / "state" / "posted.json"
INSIGHTS_FILE = ROOT / "content" / "state" / "insights.json"
OUT_DIR = ROOT / "out"
MUSIC_DIR = ROOT / "assets" / "music"

BRAND_NAME = "History Unsealed"
BRAND_TAGLINE = "Archive image"

# Slots: the publish workflow maps each cron to one of these.
SLOTS = {
    "c": "photo",  # 02:07 UTC — US late evening / West coast prime time
    "b": "reel",   # 12:47 UTC — US morning commute / UK afternoon
    "e": "photo",  # 14:41 UTC — US mid-morning / UK late afternoon
    "a": "photo",  # 16:52 UTC — US lunch / UK evening
    "f": "video",  # 21:37 UTC — long documentary, US afternoon / UK late evening
    "d": "reel",   # 23:13 UTC — US prime time (East coast 7pm, West 4pm)
}

# Scheduled UTC time of each slot. GitHub's scheduler can start runs hours late, so a
# scheduled run publishes the post for the date of the slot's most recent scheduled time.
SLOT_TIMES = {"c": "02:07", "b": "12:47", "e": "14:41", "a": "16:52", "f": "21:37", "d": "23:13"}

# Facebook Graph API
GRAPH_VERSION = os.environ.get("GRAPH_VERSION", "v24.0")
FB_PAGE_ID = os.environ.get("FB_PAGE_ID", "")
FB_PAGE_TOKEN = os.environ.get("FB_PAGE_TOKEN", "")

# Voiceover (Microsoft Edge neural voices via edge-tts, free)
TTS_VOICE = os.environ.get("TTS_VOICE", "en-US-AndrewMultilingualNeural")
TTS_RATE = os.environ.get("TTS_RATE", "+4%")

# Fonts available on the ubuntu runner after `apt-get install fonts-dejavu-core`
FONT_DIR = Path(os.environ.get("FONT_DIR", "/usr/share/fonts/truetype/dejavu"))
FONT_SERIF_BOLD = FONT_DIR / "DejaVuSerif-Bold.ttf"
FONT_SANS = FONT_DIR / "DejaVuSans.ttf"

