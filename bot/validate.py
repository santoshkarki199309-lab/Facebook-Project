"""Validate queue files. Run: python -m bot.validate [files...] (default: all queue files)."""
import json
import re
import sys
from pathlib import Path

from . import config
from .media import iter_visual_items, normalise_license, queries

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
BANNED = ["corporate sponsor", "they don't want you to know", "100% proven", "scientists are baffled",
          "like if", "share if", "tag a friend", "tag someone", "comment yes", "type 1", "type yes",
          "in this video"]


def _visual_checks(item: dict, where: str) -> list[str]:
    """Every visual must point at REAL archive media (no AI): image_url, image_search or video_search."""
    out = []
    url = item.get("image_url")
    if url:
        if not str(url).startswith("https://"):
            out.append(f"{where}: image_url must be https")
        if not normalise_license(item.get("image_license", "")):
            out.append(f"{where}: image_license must be Public domain, CC0, CC BY or CC BY-SA "
                       f"(got {item.get('image_license')!r})")
        if not item.get("image_credit"):
            out.append(f"{where}: image_credit required with image_url")
    if not (url or queries(item) or queries(item, "video_search")):
        out.append(f"{where}: needs image_search (or video_search / image_url) for a real archive visual")
    qs = queries(item) + queries(item, "video_search")
    if qs and all(len(q.split()) < 2 for q in qs):
        out.append(f"{where}: searches {qs} are too vague — name the subject in 2+ words")
    if item.get("label") and len(item["label"]) > 16:
        out.append(f"{where}: label longer than 16 characters")
    return out


def _words(scenes: list[dict]) -> int:
    return sum(len(sc.get("narration", "").split()) for sc in scenes)


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

    for where, item in iter_visual_items(post):
        p += _visual_checks(item, where)

    if t == "photo":
        layout = post.get("layout", "full")
        if layout not in ("full", "card"):
            p.append(f"layout must be 'full' or 'card', got {layout!r}")
        if layout == "card" and not 2 <= len(post.get("image_headline", "").split()) <= 10:
            p.append("card layout needs image_headline of 2–10 words")
    elif t == "reel":
        scenes = post.get("scenes", [])
        if not 4 <= len(scenes) <= 9:
            p.append("reel needs 4–9 scenes")
        if not 80 <= _words(scenes) <= 190:
            p.append(f"reel narration {_words(scenes)} words; aim 90–140 (≈35–55s)")
        hook = post.get("hook_text", "")
        if hook and len(hook.split()) > 8:
            p.append("hook_text must be 8 words or fewer")
        for i, sc in enumerate(scenes):
            if not sc.get("narration"):
                p.append(f"scene {i + 1} has no narration")
    elif t == "video":
        if not 10 <= len(post.get("title", "")) <= 100:
            p.append("video title must be 10–100 characters")
        chapters = post.get("chapters", [])
        scenes = [sc for ch in chapters for sc in ch.get("scenes", [])]
        if not 3 <= len(chapters) <= 8:
            p.append("long video needs 3–8 chapters")
        if not 12 <= len(scenes) <= 45:
            p.append(f"long video needs 12–45 scenes, got {len(scenes)}")
        if not 450 <= _words(scenes) <= 1100:
            p.append(f"long video narration {_words(scenes)} words; aim 550–900 (≈4–6 min)")
        for i, ch in enumerate(chapters):
            if not ch.get("title"):
                p.append(f"chapter {i + 1} needs a title")
        for i, sc in enumerate(scenes):
            if not sc.get("narration"):
                p.append(f"scene {i + 1} has no narration")
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
    if len(slots) != len(set(slots)):
        out.append(f"{path.name}: duplicate slots {slots}")
    missing = sorted(set(config.SLOTS) - set(slots))
    if missing:
        out.append(f"{path.name}: missing slot(s) {missing}")
    for post in day.get("posts", []):
        out += [f"{path.name} [{post.get('slot')}]: {x}" for x in validate_post(post)]
    return out


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    from_today = "--from-today" in sys.argv
    files = [Path(a) for a in args] or sorted(config.QUEUE_DIR.glob("*.json"))
    if from_today:
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        files = [f for f in files if f.stem >= today]
    problems = []
    for f in files:
        problems += validate_file(f)
    seen = {}
    for f in sorted(config.QUEUE_DIR.glob("*.json")):
        try:
            for post in json.loads(f.read_text(encoding="utf-8")).get("posts", []):
                key = post.get("topic", "").strip().lower()
                if key and key in seen and f in files:
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
