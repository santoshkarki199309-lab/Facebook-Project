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
    v = (value or "").strip().lower()
    v = re.sub(r"\s+\d(\.\d)?$", "", v)  # "CC BY-SA 4.0" -> "cc by-sa"
    return ALLOWED_LICENSES.get(v)


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


def picture(item: dict, out: Path, offline: bool = False, size=(1024, 1024)) -> tuple[Path, str, str | None]:
    """Return (path, on-image tag, credit line or None) for a post or reel scene."""
    url = item.get("image_url")
    lic = normalise_license(item.get("image_license", ""))
    if url and lic and not offline:
        try:
            path = fetch(url, out)
            credit = item.get("image_credit") or "Wikimedia Commons"
            return path, "Archive image", f"{credit} ({lic})"
        except Exception as exc:  # noqa: BLE001 — fall back to an AI illustration
            print(f"::warning::archival image failed, using AI instead: {exc}")
    prompt = item.get("image_prompt") or ""
    path = images.generate(prompt, out, size[0], size[1], offline=offline)
    return path, "AI illustration", None
