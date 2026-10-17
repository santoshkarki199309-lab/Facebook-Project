"""Pick the picture for a post or scene: a real archival image when one is given, AI otherwise.

Real public-domain photographs, paintings, maps and artefacts make the Page clearly original
and editorial — not "AI slop" — which matters for Facebook monetization review.
"""
import io
import re
import urllib.parse
from pathlib import Path

import requests
from PIL import Image

from . import images

USER_AGENT = "HistoryUnsealedBot/1.0 (https://santoshkarki199309-lab.github.io/Facebook-Project/; historyvaultmedia8@gmail.com)"

# Licences we may publish. Anything else must not be used.
ALLOWED_LICENSES = {
    "public domain": "Public domain",
    "pd": "Public domain",
    "cc0": "CC0",
    "cc by": "CC BY",
    "cc by-sa": "CC BY-SA",
    "cc-by": "CC BY",
    "cc-by-sa": "CC BY-SA",
    "no known copyright restrictions": "No known copyright restrictions",
}


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


def _direct_url(url: str) -> str:
    """Turn a Wikimedia Commons file page into a download URL for a 1600px rendition."""
    m = re.match(r"https?://commons\.wikimedia\.org/wiki/(File:.+)$", url)
    if m:
        name = urllib.parse.unquote(m.group(1)).split(":", 1)[1]
        return ("https://commons.wikimedia.org/wiki/Special:FilePath/"
                + urllib.parse.quote(name) + "?width=1600")
    return url


def fetch(url: str, out: Path) -> Path:
    resp = requests.get(_direct_url(url), headers={"User-Agent": USER_AGENT},
                        timeout=90, allow_redirects=True)
    ctype = resp.headers.get("content-type", "")
    if resp.status_code != 200 or not ctype.startswith("image"):
        raise images.ImageGenError(f"archival fetch {resp.status_code} {ctype}: {url}")
    img = Image.open(io.BytesIO(resp.content)).convert("RGB")
    if min(img.size) < 500:
        raise images.ImageGenError(f"archival image too small {img.size}: {url}")
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, quality=93)
    print(f"[media] archival ok -> {out.name} {img.size}")
    return out


COMMONS_API = "https://commons.wikimedia.org/w/api.php"
BAD_TITLE_WORDS = ("logo", "icon", "flag of", "coat of arms", "signature", "diagram", "chart",
                   "screenshot", "poster", "cover", "stamp", "banknote", "coin of")


def _clean(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html or "")).strip()


GENERIC_WORDS = {
    "the", "and", "of", "in", "on", "at", "for", "with", "from", "a", "an", "to", "by",
    "painting", "engraving", "portrait", "illustration", "photo", "photograph", "image", "picture",
    "interior", "exterior", "view", "ruins", "ruin", "ancient", "old", "medieval", "century",
    "museum", "national", "archaeological", "fragment", "close", "detail", "page", "folio",
    "watercolour", "watercolor", "woodcut", "drawing", "map", "historic", "historical",
}


def _keywords(text: str) -> set[str]:
    words = re.findall(r"[a-z]+", text.lower())
    return {w for w in words if len(w) > 2 and w not in GENERIC_WORDS}


def _relevant(query: str, title: str) -> bool:
    """The file title must mention the subject: ≥2 specific query words (or all, if fewer)."""
    want = _keywords(query)
    have = _keywords(title)
    return len(want & have) >= min(2, len(want))


def commons_search(query: str, limit: int = 20) -> dict | None:
    """Find the best openly licensed photo/painting on Wikimedia Commons for `query`."""
    params = {
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": f"filetype:bitmap {query}", "gsrnamespace": 6, "gsrlimit": limit,
        "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 1600,
    }
    resp = requests.get(COMMONS_API, params=params, headers={"User-Agent": USER_AGENT}, timeout=60)
    resp.raise_for_status()
    pages = sorted((resp.json().get("query", {}).get("pages", {}) or {}).values(),
                   key=lambda pg: pg.get("index", 99))
    for pg in pages:
        title = pg.get("title", "")
        if any(w in title.lower() for w in BAD_TITLE_WORDS) or not _relevant(query, title):
            continue
        info = (pg.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata", {})
        lic = normalise_license(_clean(meta.get("LicenseShortName", {}).get("value", "")))
        if not lic or info.get("mime") not in ("image/jpeg", "image/png"):
            continue
        if min(info.get("width", 0), info.get("height", 0)) < 700:
            continue
        artist = _clean(meta.get("Artist", {}).get("value", ""))
        artist = re.sub(r"(?i)^(unknown author)+$", "", artist.replace("Unknown authorUnknown author", ""))
        artist = artist[:80] or "Unknown author"
        return {
            "title": title,
            "url": info.get("thumburl") or info.get("url"),
            "page": info.get("descriptionurl"),
            "license": lic,
            "credit": f"{artist} / Wikimedia Commons",
        }
    return None


def picture(item: dict, out: Path, offline: bool = False, size=(1024, 1024)) -> tuple[Path, str, str | None]:
    """Return (path, on-image tag, credit line or None) for a post or reel scene.

    Order: explicit image_url → Wikimedia Commons search (image_search) → AI illustration."""
    url = item.get("image_url")
    lic = normalise_license(item.get("image_license", ""))
    if url and lic and not offline:
        try:
            path = fetch(url, out)
            credit = item.get("image_credit") or "Wikimedia Commons"
            return path, "Archive image", f"{credit} ({lic})"
        except Exception as exc:  # noqa: BLE001 — fall back to search / AI
            print(f"::warning::archival image failed: {exc}")
    query = item.get("image_search")
    if query and not offline:
        try:
            hit = commons_search(query)
            if hit:
                path = fetch(hit["url"], out)
                print(f"[media] commons '{query}' -> {hit['title']} ({hit['license']})")
                return path, "Archive image", f"{hit['credit']} ({hit['license']})"
            print(f"::notice::no openly licensed Commons image for '{query}', using AI")
        except Exception as exc:  # noqa: BLE001
            print(f"::warning::archival image failed for '{query}': {exc}")
    prompt = item.get("image_prompt") or ""
    path = images.generate(prompt, out, size[0], size[1], offline=offline)
    return path, "AI illustration", None


def preview(dates: list[str]) -> dict:
    """Resolve every image_search in the given queue dates without downloading (for review)."""
    import json
    from . import config
    report = {}
    for date in dates:
        path = config.QUEUE_DIR / f"{date}.json"
        if not path.exists():
            continue
        for post in json.loads(path.read_text(encoding="utf-8"))["posts"]:
            items = [("post", post)] if post["type"] == "photo" else \
                [(f"scene {i + 1}", sc) for i, sc in enumerate(post["scenes"])]
            for where, item in items:
                q = item.get("image_search")
                if not q:
                    continue
                try:
                    hit = commons_search(q)
                except Exception as exc:  # noqa: BLE001
                    hit = {"error": str(exc)}
                report[f"{date}:{post['slot']}:{where}"] = {"query": q, "topic": post["topic"],
                                                            "hit": hit}
    return report


if __name__ == "__main__":
    import json
    import sys
    from . import config
    out = config.ROOT / "content" / "state" / "image_preview.json"
    out.write_text(json.dumps(preview(sys.argv[1:]), indent=2) + "\n", encoding="utf-8")
    print(f"[media] preview written to {out}")
