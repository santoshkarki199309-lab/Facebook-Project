"""Publish today's queued post for one slot.

Usage:
  python -m bot.publish --slot a                # publish slot a for today (UTC)
  python -m bot.publish --slot b --dry-run      # render only, no posting
  python -m bot.publish --slot b --dry-run --offline   # render with placeholders, no network
  python -m bot.publish --check                 # verify Facebook credentials
"""
import argparse
import sys
from datetime import datetime, timezone

from . import brand, config, facebook, images, reel
from . import queue as q
from .validate import validate_post


def run(slot: str, date: str, dry_run: bool, offline: bool) -> int:
    key = f"{date}:{slot}"
    state = q.load_state()
    if key in state and not dry_run:
        print(f"[publish] {key} already published ({state[key].get('id')}); nothing to do.")
        return 0

    post = q.item_for(date, slot)
    if post is None:
        print(f"::error::No queued content for {key}. The content task may have failed — "
              f"check content/queue/{date}.json")
        return 2

    problems = validate_post(post, slot)
    if problems:
        print("::error::Queue item is invalid: " + "; ".join(problems))
        return 3

    work = config.OUT_DIR / date / slot
    caption = q.build_caption(post)
    (work).mkdir(parents=True, exist_ok=True)
    (work / "caption.txt").write_text(caption, encoding="utf-8")
    print(f"[publish] {key} type={post['type']} topic={post.get('topic')!r}")

    if post["type"] == "photo":
        raw = images.generate(post["image_prompt"], work / "raw.jpg", offline=offline)
        media = brand.photo_post(raw, work / "post.jpg")
    else:
        media = reel.render(post, work, offline=offline)

    if dry_run:
        print(f"[publish] DRY RUN — rendered {media} (not posted)")
        return 0

    if post["type"] == "photo":
        result = facebook.post_photo(media, caption)
        post_id = result.get("post_id") or result.get("id")
    else:
        result = facebook.post_reel(media, caption)
        post_id = result.get("video_id")

    state[key] = {
        "id": post_id,
        "type": post["type"],
        "topic": post.get("topic"),
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    q.save_state(state)
    print(f"[publish] published {key} -> {post_id}")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slot", choices=sorted(config.SLOTS))
    ap.add_argument("--date", default=None, help="UTC date YYYY-MM-DD (default: today)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--offline", action="store_true", help="placeholder images + silent audio")
    ap.add_argument("--check", action="store_true", help="verify Facebook credentials and exit")
    args = ap.parse_args()

    if args.check:
        me = facebook.whoami()
        print(f"[check] token belongs to: {me}")
        if config.FB_PAGE_ID and me.get("id") != config.FB_PAGE_ID:
            print(f"::warning::FB_PAGE_ID ({config.FB_PAGE_ID}) differs from the token's page id "
                  f"({me.get('id')}). Set FB_PAGE_ID to {me.get('id')}.")
        sys.exit(0)

    if not args.slot:
        ap.error("--slot is required")
    sys.exit(run(args.slot, args.date or q.today_utc(), args.dry_run, args.offline))


if __name__ == "__main__":
    main()
