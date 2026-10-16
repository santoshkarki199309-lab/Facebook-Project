"""Weekly performance snapshot -> content/state/insights.json (read by the content task)."""
import json
from datetime import datetime, timezone

from . import config, facebook
from . import queue as q


def main() -> None:
    posts = facebook.recent_posts(limit=60)
    state = q.load_state()
    topic_by_id = {v.get("id"): (k, v.get("topic"), v.get("type")) for k, v in state.items()}
    rows = []
    for p in posts:
        reactions = p.get("reactions", {}).get("summary", {}).get("total_count", 0)
        comments = p.get("comments", {}).get("summary", {}).get("total_count", 0)
        shares = p.get("shares", {}).get("count", 0)
        key, topic, kind = topic_by_id.get(p["id"], (None, None, None))
        rows.append({
            "post_id": p["id"],
            "created": p.get("created_time"),
            "slot_key": key,
            "topic": topic or (p.get("message") or "")[:80],
            "type": kind,
            "reactions": reactions,
            "comments": comments,
            "shares": shares,
            "score": reactions + 3 * comments + 5 * shares,
            "url": p.get("permalink_url"),
        })
    rows.sort(key=lambda r: r["score"], reverse=True)
    out = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "note": "score = reactions + 3*comments + 5*shares",
        "top": rows[:10],
        "bottom": rows[-10:] if len(rows) > 10 else [],
        "count": len(rows),
    }
    config.INSIGHTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    config.INSIGHTS_FILE.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"[insights] {len(rows)} posts scored")


if __name__ == "__main__":
    main()
