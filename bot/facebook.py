"""Minimal Facebook Graph API client for a single Page."""
import time
from pathlib import Path

import requests

from . import config


class GraphError(RuntimeError):
    pass


def _base() -> str:
    return f"https://graph.facebook.com/{config.GRAPH_VERSION}"


def _check(resp: requests.Response) -> dict:
    try:
        data = resp.json()
    except ValueError:
        raise GraphError(f"HTTP {resp.status_code}: {resp.text[:300]}")
    if resp.status_code >= 400 or "error" in data:
        err = data.get("error", data)
        raise GraphError(f"HTTP {resp.status_code}: {err}")
    return data


def _require_creds() -> None:
    if not (config.FB_PAGE_ID and config.FB_PAGE_TOKEN):
        raise GraphError("FB_PAGE_ID / FB_PAGE_TOKEN secrets are not set")


def whoami() -> dict:
    """Confirms the token is a Page token and returns the Page id/name it belongs to."""
    _require_creds()
    return _check(requests.get(f"{_base()}/me", params={
        "fields": "id,name", "access_token": config.FB_PAGE_TOKEN}, timeout=30))


def post_photo(image: Path, caption: str) -> dict:
    _require_creds()
    with open(image, "rb") as fh:
        resp = requests.post(
            f"{_base()}/{config.FB_PAGE_ID}/photos",
            data={"message": caption, "published": "true", "access_token": config.FB_PAGE_TOKEN},
            files={"source": (image.name, fh, "image/jpeg")},
            timeout=180,
        )
    return _check(resp)


def post_reel(video: Path, description: str) -> dict:
    """Three-phase Reels upload: start -> binary upload -> finish (publish)."""
    _require_creds()
    url = f"{_base()}/{config.FB_PAGE_ID}/video_reels"
    start = _check(requests.post(url, data={
        "upload_phase": "start", "access_token": config.FB_PAGE_TOKEN}, timeout=60))
    video_id = start["video_id"]
    upload_url = start.get("upload_url") or (
        f"https://rupload.facebook.com/video-upload/{config.GRAPH_VERSION}/{video_id}")

    size = video.stat().st_size
    with open(video, "rb") as fh:
        up = requests.post(upload_url, headers={
            "Authorization": f"OAuth {config.FB_PAGE_TOKEN}",
            "offset": "0",
            "file_size": str(size),
        }, data=fh, timeout=600)
    up_data = _check(up)
    if not up_data.get("success", False):
        raise GraphError(f"Reel upload not acknowledged: {up_data}")

    fin = _check(requests.post(url, data={
        "upload_phase": "finish",
        "video_id": video_id,
        "video_state": "PUBLISHED",
        "description": description,
        "access_token": config.FB_PAGE_TOKEN,
    }, timeout=60))

    # Poll processing status (best effort — publishing continues server-side regardless).
    status = {}
    for _ in range(20):
        time.sleep(15)
        try:
            status = _check(requests.get(f"{_base()}/{video_id}", params={
                "fields": "status", "access_token": config.FB_PAGE_TOKEN}, timeout=30))
        except GraphError as exc:
            print(f"[facebook] status check failed: {exc}")
            break
        st = status.get("status", {})
        print(f"[facebook] reel status: {st.get('video_status')}")
        if st.get("video_status") in ("ready", "error"):
            break
    if status.get("status", {}).get("video_status") == "error":
        raise GraphError(f"Reel processing failed: {status}")
    return {"video_id": video_id, "finish": fin, "status": status.get("status")}


def add_comment(object_id: str, message: str) -> dict:
    """Comment as the Page on a post or reel. Needs pages_manage_engagement."""
    _require_creds()
    return _check(requests.post(f"{_base()}/{object_id}/comments", data={
        "message": message, "access_token": config.FB_PAGE_TOKEN}, timeout=60))


def recent_posts(limit: int = 50) -> list[dict]:
    _require_creds()
    data = _check(requests.get(f"{_base()}/{config.FB_PAGE_ID}/published_posts", params={
        "fields": "id,created_time,message,permalink_url,"
                  "reactions.summary(total_count).limit(0),"
                  "comments.summary(total_count).limit(0),shares",
        "limit": limit,
        "access_token": config.FB_PAGE_TOKEN,
    }, timeout=60))
    return data.get("data", [])
