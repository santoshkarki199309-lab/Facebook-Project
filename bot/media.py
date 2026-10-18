"""Real archival media only: photographs, paintings, documents and film from Wikimedia Commons.

No AI imagery is used. Every visual is an openly licensed (public domain / CC0 / CC BY /
CC BY-SA) file found on Wikimedia Commons and credited in the post's first comment.
"""
import io
import random
import re
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

import requests
from PIL import Image, ImageDraw

USER_AGENT = ("HistoryUnsealedBot/1.0 (https://santoshkarki199309-lab.github.io/Facebook-Project/;"
              " historyvaultmedia8@gmail.com)")
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
TAG = "Archive image"
VIDEO_TAG = "Archive film"
MAX_VIDEO_BYTES = 250 * 1024 * 1024

BAD_TITLE_WORDS = ("logo", "icon", "flag of", "coat of arms", "signature", "diagram", "chart",
                   "screenshot", "poster", "cover", "stamp", "banknote", "coin of", "ai-generated",
                   "ai generated", "midjourney", "stable diffusion", "dall-e")
GENERIC_WORDS = {
    "the", "and", "of", "in", "on", "at", "for", "with", "from", "a", "an", "to", "by",
    "painting", "engraving", "portrait", "illustration", "photo", "photograph", "image", "picture",
    "interior", "exterior", "view", "ruins", "ruin", "ancient", "old", "medieval", "century",
    "museum", "national", "archaeological", "fragment", "close", "detail", "page", "folio",
    "watercolour", "watercolor", "woodcut", "drawing", "map", "historic", "historical",
    "film", "footage", "video", "newsreel", "archive", "archival",
}


class NoRealMedia(RuntimeError):
    pass


@dataclass
class Visual:
    kind: str            # "image" or "video"
    path: Path
    credit: str          # "Author / Wikimedia Commons (licence)"
    title: str
    duration: float = 0.0

    @property
    def tag(self) -> str:
        return VIDEO_TAG if self.kind == "video" else TAG


# ---------------------------------------------------------------- licences & matching

def normalise_license(value: str) -> str | None:
    """Map a licence string to an allowed short name, or None if not allowed."""
    v = re.sub(r"\s+", " ", (value or "").strip().lower())
    if not v or any(x in v for x in ("nc", "nd", "noncommercial", "no derivatives", "fair use")):
        return None
    if v in ("pd", "public domain") or v.startswith(("public domain", "pd-", "pd ")):
        return "Public domain"
    if v.startswith("cc0") or v.startswith("cc-zero"):
        return "CC0"
    if v == "no known copyright restrictions":
        return "No known copyright restrictions"
    m = re.match(r"^cc[- ]by(-sa)?(\s|$|-\d|\s\d)", v)
    if m:
        return "CC BY-SA" if m.group(1) else "CC BY"
    return None


def _clean(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html or "")).strip()


def _keywords(text: str) -> set[str]:
    words = re.findall(r"[a-z]+", text.lower())
    return {w for w in words if len(w) > 2 and w not in GENERIC_WORDS}


def _relevant(query: str, title: str) -> bool:
    """The file title must mention the subject: ≥2 specific query words (or all, if fewer)."""
    want, have = _keywords(query), _keywords(title)
    return len(want & have) >= min(2, len(want)) and len(want) > 0


def queries(item: dict, key: str = "image_search") -> list[str]:
    v = item.get(key)
    if not v:
        return []
    return [v] if isinstance(v, str) else [q for q in v if isinstance(q, str) and q.strip()]


# ---------------------------------------------------------------- Commons search

def commons_search(query: str, kind: str = "image", exclude: set[str] | None = None,
                   limit: int = 25) -> dict | None:
    """Best openly licensed Commons file for `query` whose title names the subject."""
    exclude = exclude or set()
    ftype = "bitmap" if kind == "image" else "video"
    params = {
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": f"filetype:{ftype} {query}", "gsrnamespace": 6, "gsrlimit": limit,
        "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 1920,
    }
    resp = requests.get(COMMONS_API, params=params, headers={"User-Agent": USER_AGENT}, timeout=60)
    resp.raise_for_status()
    pages = sorted((resp.json().get("query", {}).get("pages", {}) or {}).values(),
                   key=lambda pg: pg.get("index", 99))
    for pg in pages:
        title = pg.get("title", "")
        if title in exclude or any(w in title.lower() for w in BAD_TITLE_WORDS):
            continue
        if not _relevant(query, title):
            continue
        info = (pg.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata", {})
        lic = normalise_license(_clean(meta.get("LicenseShortName", {}).get("value", "")))
        if not lic:
            continue
        mime = info.get("mime", "")
        if kind == "image":
            if mime not in ("image/jpeg", "image/png", "image/tiff"):
                continue
            if min(info.get("width", 0), info.get("height", 0)) < 600:
                continue
            url = info.get("thumburl") or info.get("url")
        else:
            if not (mime.startswith("video/") or mime in ("application/ogg",)):
                continue
            if info.get("size", 0) > MAX_VIDEO_BYTES or info.get("height", 0) < 240:
                continue
            url = info.get("url")
        artist = _clean(meta.get("Artist", {}).get("value", ""))
        artist = re.sub(r"(?i)^(unknown author)+$", "", artist.replace("Unknown authorUnknown author", ""))
        artist = artist[:80] or "Unknown author"
        return {
            "title": title, "url": url, "page": info.get("descriptionurl"), "license": lic,
            "credit": f"{artist} / Wikimedia Commons ({lic})",
            "duration": float(info.get("duration") or 0),
        }
    return None


def _direct_url(url: str) -> str:
    m = re.match(r"https?://commons\.wikimedia\.org/wiki/(File:.+)$", url)
    if m:
        name = urllib.parse.unquote(m.group(1)).split(":", 1)[1]
        return ("https://commons.wikimedia.org/wiki/Special:FilePath/"
                + urllib.parse.quote(name) + "?width=1920")
    return url


def fetch_image(url: str, out: Path) -> Path:
    resp = requests.get(_direct_url(url), headers={"User-Agent": USER_AGENT}, timeout=120)
    ctype = resp.headers.get("content-type", "")
    if resp.status_code != 200 or not ctype.startswith("image"):
        raise NoRealMedia(f"image fetch {resp.status_code} {ctype}: {url}")
    img = Image.open(io.BytesIO(resp.content)).convert("RGB")
    if min(img.size) < 500:
        raise NoRealMedia(f"image too small {img.size}: {url}")
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, quality=93)
    return out


def fetch_video(url: str, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=300, stream=True) as resp:
        if resp.status_code != 200:
            raise NoRealMedia(f"video fetch {resp.status_code}: {url}")
        size = 0
        with open(out, "wb") as fh:
            for chunk in resp.iter_content(1 << 20):
                size += len(chunk)
                if size > MAX_VIDEO_BYTES:
                    raise NoRealMedia(f"video too large: {url}")
                fh.write(chunk)
    return out


def _placeholder(out: Path, text: str) -> Path:
    img = Image.new("RGB", (1280, 960), (52, 44, 34))
    d = ImageDraw.Draw(img)
    for i in range(0, 2400, 60):
        d.line([(i, 0), (i - 960, 960)], fill=(70, 60, 46), width=2)
    d.text((40, 40), "OFFLINE TEST — real archive image goes here\n" + text[:120], fill=(201, 162, 90))
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, quality=90)
    return out


# ---------------------------------------------------------------- resolve visuals

def resolve(item: dict, out_stem: Path, used: set[str], offline: bool = False,
            allow_video: bool = True) -> Visual:
    """Find and download the real visual for a post or scene. Raises NoRealMedia."""
    if offline:
        path = _placeholder(out_stem.with_suffix(".jpg"),
                            " | ".join(queries(item) or queries(item, "video_search")))
        return Visual("image", path, "Offline test", "offline")

    errors = []
    url = item.get("image_url")
    lic = normalise_license(item.get("image_license", ""))
    if url and lic:
        try:
            path = fetch_image(url, out_stem.with_suffix(".jpg"))
            credit = f"{item.get('image_credit') or 'Wikimedia Commons'} ({lic})"
            used.add(url)
            return Visual("image", path, credit, url)
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))

    if allow_video:
        for q in queries(item, "video_search"):
            try:
                hit = commons_search(q, "video", used)
                if hit:
                    ext = Path(urllib.parse.urlparse(hit["url"]).path).suffix or ".webm"
                    path = fetch_video(hit["url"], out_stem.with_suffix(ext))
                    used.add(hit["title"])
                    print(f"[media] film '{q}' -> {hit['title']} ({hit['license']})")
                    return Visual("video", path, hit["credit"], hit["title"], hit["duration"])
                errors.append(f"no film for '{q}'")
            except Exception as exc:  # noqa: BLE001
                errors.append(f"film '{q}': {exc}")

    for q in queries(item):
        try:
            hit = commons_search(q, "image", used)
            if hit:
                path = fetch_image(hit["url"], out_stem.with_suffix(".jpg"))
                used.add(hit["title"])
                print(f"[media] image '{q}' -> {hit['title']} ({hit['license']})")
                return Visual("image", path, hit["credit"], hit["title"])
            errors.append(f"no image for '{q}'")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"image '{q}': {exc}")
    raise NoRealMedia("; ".join(errors) or "no image_search / video_search given")


def resolve_many(items: list[dict], workdir: Path, prefix: str, offline: bool = False) -> list[Visual]:
    """Resolve visuals for a list of scenes. A scene without a match reuses another real
    visual from the same post (different framing), so no scene ever falls back to AI."""
    used: set[str] = set()
    found: list[Visual | None] = []
    for i, item in enumerate(items):
        try:
            found.append(resolve(item, workdir / f"{prefix}{i}_raw", used, offline))
        except NoRealMedia as exc:
            print(f"::notice::scene {i + 1}: {exc}")
            found.append(None)
    pool = [v for v in found if v]
    if not pool:
        raise NoRealMedia("no real archive image found for any scene of this post")
    missing = sum(1 for v in found if v is None)
    if missing:
        print(f"::notice::{missing} scene(s) reuse another archive image from this post")
    out, k = [], 0
    for v in found:
        if v is None:
            v = pool[k % len(pool)]
            k += 1
        out.append(v)
    return out


def credits_of(visuals: list[Visual]) -> list[str]:
    seen = []
    for v in visuals:
        if v.credit not in seen and v.credit != "Offline test":
            seen.append(v.credit)
    return seen


def random_start(v: Visual, need: float) -> float:
    if v.kind != "video" or v.duration <= need + 2:
        return 0.0
    return round(random.uniform(0, min(v.duration - need - 1, 90)), 2)


# ---------------------------------------------------------------- preview (CI)

def preview(dates: list[str]) -> dict:
    """Resolve every search in the given queue dates without downloading (for review)."""
    import json
    from . import config
    report = {}
    for date in dates:
        path = config.QUEUE_DIR / f"{date}.json"
        if not path.exists():
            continue
        for post in json.loads(path.read_text(encoding="utf-8"))["posts"]:
            for where, item in iter_visual_items(post):
                hit, tried = None, []
                for kind, key in (("video", "video_search"), ("image", "image_search")):
                    for q in queries(item, key):
                        tried.append(f"{kind}:{q}")
                        try:
                            hit = commons_search(q, kind)
                        except Exception as exc:  # noqa: BLE001
                            hit = {"error": str(exc)}
                        if hit:
                            break
                    if hit:
                        break
                report[f"{date}:{post['slot']}:{where}"] = {"topic": post["topic"], "tried": tried,
                                                            "hit": hit}
    return report


def iter_visual_items(post: dict):
    if post["type"] == "photo":
        yield "post", post
    elif post["type"] == "reel":
        for i, sc in enumerate(post.get("scenes", [])):
            yield f"scene {i + 1}", sc
    elif post["type"] == "video":
        n = 0
        for ch in post.get("chapters", []):
            for sc in ch.get("scenes", []):
                n += 1
                yield f"scene {n}", sc


if __name__ == "__main__":
    import json
    import sys
    from . import config
    out = config.ROOT / "content" / "state" / "image_preview.json"
    rep = preview(sys.argv[1:])
    out.write_text(json.dumps(rep, indent=2) + "\n", encoding="utf-8")
    missing = [k for k, v in rep.items() if not v["hit"] or "error" in (v["hit"] or {})]
    for k in missing:
        print(f"::warning::no real archive media for {k} ({rep[k]['topic']}) — tried {rep[k]['tried']}")
    print(f"[media] preview: {len(rep) - len(missing)}/{len(rep)} items have real media -> {out}")
