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
BRAND_TAGLINE = "AI illustration"

# Slots: the publish workflow maps each cron to one of these.
SLOTS = {
    "a": "photo",  # ~12:47 UTC — Europe lunch / US morning
    "b": "reel",   # ~17:52 UTC — Europe evening / US midday
    "c": "photo",  # ~00:13 UTC — US evening
}

# Facebook Graph API
GRAPH_VERSION = os.environ.get("GRAPH_VERSION", "v24.0")
FB_PAGE_ID = os.environ.get("FB_PAGE_ID", "")
FB_PAGE_TOKEN = os.environ.get("FB_PAGE_TOKEN", "")

# Image generation (Cloudflare Workers AI, free daily allowance)
CF_ACCOUNT_ID = os.environ.get("CF_ACCOUNT_ID", "")
CF_API_TOKEN = os.environ.get("CF_API_TOKEN", "")
CF_MODEL = os.environ.get("CF_MODEL", "@cf/black-forest-labs/flux-1-schnell")

# Voiceover (Microsoft Edge neural voices via edge-tts, free)
TTS_VOICE = os.environ.get("TTS_VOICE", "en-US-AndrewMultilingualNeural")
TTS_RATE = os.environ.get("TTS_RATE", "+4%")

# Fonts available on the ubuntu runner after `apt-get install fonts-dejavu-core`
FONT_DIR = Path(os.environ.get("FONT_DIR", "/usr/share/fonts/truetype/dejavu"))
FONT_SERIF_BOLD = FONT_DIR / "DejaVuSerif-Bold.ttf"
FONT_SANS = FONT_DIR / "DejaVuSans.ttf"

IMAGE_STYLE_SUFFIX = (
    ", cinematic historical illustration, dramatic chiaroscuro lighting, rich detail, "
    "muted earthy palette with warm gold highlights, photorealistic, no text, no letters, "
    "no watermark, no logo"
)
