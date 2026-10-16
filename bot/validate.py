"""Validate queue files. Run: python -m bot.validate [files...] (default: all queue files)."""
import json
import re
import sys
from pathlib import Path

from . import config

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
BANNED = ["corporate sponsor", "they don't want you to know", "100% proven", "scientists are baffled"]


def validate_post(post: dict, slot: str | None = None) -> list[str]:
    p = []
    s = post.get("slot")
    if s not in config.SLOTS:
        p.append(f"bad slot {s!r}")
    elif slot and s != slot:
        p.append(f"slot mismatch {s} != {slot}")
    t = post.get("type")
    if s in config.SLOTS and t != config.SLOTS[s]:
        p.append(f"slot {s} must be type {config.SLOTS[s]}, got {t}")
    if not post.get("topic"):
        p.append("missing topic")
    cap = post.get("caption", "")
    if not 150 <= len(cap) <= 2000:
        p.append(f"caption length {len(cap)} not in 150–2000")
    tags = post.get("hashtags", [])
    if not 3 <= len(tags) <= 5:
        p.append("need 3–5 hashtags")
    src = post.get("sources", [])
    if len(src) < 2 or not all(str(x).startswith("http") for x in src):
        p.append("need at least 2 source URLs")
    low = cap.lower()
    for b in BANNED:
        if b in low:
            p.append(f"caption contains banned phrase {b!r}")
    if t == "photo":
        if len(post.get("image_prompt", "")) < 40:
            p.append("image_prompt too short")
    elif t == "reel":
        scenes = post.get("scenes", [])
        if not 4 <= len(scenes) <= 9:
            p.append("reel needs 4–9 scenes")
        words = sum(len(sc.get("narration", "").split()) for sc in scenes)
        if not 90 <= words <= 190:
            p.append(f"reel narration {words} words; aim 110–170 (≈45–75s)")
        for i, sc in enumerate(scenes):
            if len(sc.get("image_prompt", "")) < 30 or not sc.get("narration"):
                p.append(f"scene {i + 1} incomplete")
    return p


def validate_file(path: Path) -> list[str]:
    try:
        day = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return [f"{path.name}: invalid JSON ({exc})"]
    out = []
    if not DATE_RE.match(path.stem) or day.get("date") != path.stem:
        out.append(f"{path.name}: 'date' must equal file name")
    slots = [x.get("slot") for x in day.get("posts", [])]
    if sorted(slots) != sorted(config.SLOTS):
        out.append(f"{path.name}: needs exactly one post per slot {sorted(config.SLOTS)}, got {slots}")
    for post in day.get("posts", []):
        out += [f"{path.name} [{post.get('slot')}]: {x}" for x in validate_post(post)]
    return out


def main() -> None:
    files = [Path(a) for a in sys.argv[1:]] or sorted(config.QUEUE_DIR.glob("*.json"))
    problems = []
    for f in files:
        problems += validate_file(f)
    # Duplicate topics across the whole queue
    seen = {}
    for f in sorted(config.QUEUE_DIR.glob("*.json")):
        try:
            for post in json.loads(f.read_text(encoding="utf-8")).get("posts", []):
                key = post.get("topic", "").strip().lower()
                if key and key in seen:
                    problems.append(f"{f.name}: duplicate topic {post.get('topic')!r} (also {seen[key]})")
                seen.setdefault(key, f.name)
        except Exception:  # noqa: BLE001 - reported above
            pass
    for x in problems:
        print("::error::" + x)
    print(f"[validate] {len(files)} file(s), {len(problems)} problem(s)")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
