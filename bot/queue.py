"""Content queue: one JSON file per UTC date in content/queue/YYYY-MM-DD.json."""
import json
from datetime import datetime, timezone
from pathlib import Path

from . import config


def today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def load_day(date: str) -> dict | None:
    path = config.QUEUE_DIR / f"{date}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def item_for(date: str, slot: str) -> dict | None:
    day = load_day(date)
    if not day:
        return None
    for post in day.get("posts", []):
        if post.get("slot") == slot:
            return post
    return None


def load_state() -> dict:
    if config.STATE_FILE.exists():
        return json.loads(config.STATE_FILE.read_text(encoding="utf-8"))
    return {}


def save_state(state: dict) -> None:
    config.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    config.STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n",
                                 encoding="utf-8")


def build_caption(post: dict) -> str:
    tags = " ".join("#" + t.lstrip("#") for t in post.get("hashtags", []))
    footer = "🎨 Images are AI illustrations; facts are researched and sourced."
    parts = [post["caption"].strip(), footer, tags]
    return "\n\n".join(p for p in parts if p)


def build_sources_comment(post: dict) -> str:
    from urllib.parse import urlparse

    lines = ["📚 Sources for this post:"]
    for i, url in enumerate(post.get("sources", []), 1):
        host = urlparse(url).netloc.replace("www.", "")
        lines.append(f"{i}. {host} — {url}")
    lines.append("")
    lines.append("Spotted something we got wrong? Tell us below and we'll check it.")
    return "\n".join(lines)


def queued_dates() -> list[str]:
    return sorted(p.stem for p in Path(config.QUEUE_DIR).glob("*.json"))
