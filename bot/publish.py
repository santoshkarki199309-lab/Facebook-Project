"""Publish today's queued post for one slot.

Usage:
  python -m bot.publish --slot a                # publish slot a for today (UTC)
  python -m bot.publish --slot b --dry-run      # render only, no posting
  python -m bot.publish --slot b --dry-run --offline   # render with placeholders, no network
  python -m bot.publish --check                 # verify Facebook credentials
"""
import argparse
import sys
from datetime import datetime, timedelta, timezone

from . import brand, config, facebook, media, reel
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
        raw, tag, credit = media.picture(post, work / "raw.jpg", offline=offline)
        credits = [credit] if credit else []
        out_file = brand.photo_post(raw, work / "post.jpg", tagline=tag,
                                    layout=post.get("layout", "full"),
                                    headline=post.get("image_headline"),
                                    kicker=post.get("series"))
    else:
        out_file, credits = reel.render(post, work, offline=offline)

    comment = q.build_sources_comment(post, credits)
    if dry_run:
        (work / "sources_comment.txt").write_text(comment, encoding="utf-8")
        print(f"[publish] DRY RUN — rendered {out_file} (not posted)")
        return 0

    if post["type"] == "photo":
        result = facebook.post_photo(out_file, caption)
        post_id = result.get("post_id") or result.get("id")
    else:
        result = facebook.post_reel(out_file, caption)
        post_id = result.get("video_id")

    # Best effort: a sources comment never blocks or fails a publish.
    commented = False
    if post_id and post.get("sources"):
        try:
            facebook.add_comment(post_id, comment)
            commented = True
            print("[publish] sources comment added")
        except Exception as exc:  # noqa: BLE001
            print(f"::warning::Could not add sources comment: {exc}")

    state[key] = {
        "id": post_id,
        "type": post["type"],
        "topic": post.get("topic"),
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sources_comment": commented,
        "image_credits": credits,
    }
    q.save_state(state)
    print(f"[publish] published {key} -> {post_id}")
    return 0


def backfill_comments() -> int:
    """Add the sources comment to any published post that is missing it."""
    state = q.load_state()
    added = 0
    for key, entry in sorted(state.items()):
        if entry.get("sources_comment") or not entry.get("id"):
            continue
        date, slot = key.split(":")
        post = q.item_for(date, slot)
        if not post or not post.get("sources"):
            continue
        try:
            facebook.add_comment(entry["id"],
                                 q.build_sources_comment(post, entry.get("image_credits", [])))
            entry["sources_comment"] = True
            added += 1
            print(f"[comments] added sources comment to {key}")
        except Exception as exc:  # noqa: BLE001
            print(f"::warning::Sources comment for {key} failed: {exc}")
    q.save_state(state)
    print(f"[comments] backfilled {added}")
    return added


def intended_date(slot: str, now: datetime | None = None) -> str:
    """UTC date of the slot's most recent scheduled time (handles late-starting cron runs)."""
    now = now or datetime.now(timezone.utc)
    hh, mm = map(int, config.SLOT_TIMES[slot].split(":"))
    sched = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if sched > now:
        sched -= timedelta(days=1)
    return sched.strftime("%Y-%m-%d")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slot", choices=sorted(config.SLOTS))
    ap.add_argument("--date", default=None, help="UTC date YYYY-MM-DD (default: today)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--scheduled", action="store_true",
                    help="cron run: use the date of the slot's most recent scheduled time")
    ap.add_argument("--offline", action="store_true", help="placeholder images + silent audio")
    ap.add_argument("--check", action="store_true", help="verify Facebook credentials and exit")
    ap.add_argument("--backfill-comments", action="store_true",
                    help="add missing sources comments to published posts and exit")
    args = ap.parse_args()

    if args.backfill_comments:
        backfill_comments()
        sys.exit(0)

    if args.check:
        me = facebook.whoami()
        print(f"[check] token belongs to: {me}")
        if config.FB_PAGE_ID and me.get("id") != config.FB_PAGE_ID:
            print(f"::warning::FB_PAGE_ID ({config.FB_PAGE_ID}) differs from the token's page id "
                  f"({me.get('id')}). Set FB_PAGE_ID to {me.get('id')}.")
        sys.exit(0)

    if not args.slot:
        ap.error("--slot is required")
    date = args.date or (intended_date(args.slot) if args.scheduled else q.today_utc())
    try:
        code = run(args.slot, date, args.dry_run, args.offline)
    except Exception as exc:  # noqa: BLE001 — surface the reason as a run annotation
        msg = f"{type(exc).__name__}: {exc}".replace("\n", " ")[:900]
        print(f"::error::Publishing {date}:{args.slot} failed — {msg}")
        raise
    if code == 0 and not args.dry_run:
        try:
            backfill_comments()  # self-heal comments missed by earlier runs
        except Exception as exc:  # noqa: BLE001
            print(f"::warning::comment backfill skipped: {exc}")
    sys.exit(code)


if __name__ == "__main__":
    main()
