"""Image generation: Cloudflare Workers AI (primary), Pollinations (fallback), placeholder (offline tests)."""
import base64
import io
import time
import urllib.parse
from pathlib import Path

import requests
from PIL import Image, ImageDraw

from . import config


class ImageGenError(RuntimeError):
    pass


def _cloudflare(prompt: str) -> Image.Image:
    if not (config.CF_ACCOUNT_ID and config.CF_API_TOKEN):
        raise ImageGenError("Cloudflare credentials not set")
    url = (
        f"https://api.cloudflare.com/client/v4/accounts/{config.CF_ACCOUNT_ID}"
        f"/ai/run/{config.CF_MODEL}"
    )
    resp = requests.post(
        url,
        headers={"Authorization": f"Bearer {config.CF_API_TOKEN}"},
        json={"prompt": prompt[:2000], "steps": 8},
        timeout=120,
    )
    if resp.status_code != 200:
        raise ImageGenError(f"Cloudflare {resp.status_code}: {resp.text[:300]}")
    data = resp.json()
    b64 = (data.get("result") or {}).get("image")
    if not b64:
        raise ImageGenError(f"Cloudflare returned no image: {str(data)[:300]}")
    return Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")


def _pollinations(prompt: str, width: int, height: int) -> Image.Image:
    url = (
        "https://image.pollinations.ai/prompt/"
        + urllib.parse.quote(prompt[:1500])
        + f"?width={width}&height={height}&nologo=true&model=flux&seed={int(time.time()) % 100000}"
    )
    resp = requests.get(url, timeout=180)
    if resp.status_code != 200 or not resp.headers.get("content-type", "").startswith("image"):
        raise ImageGenError(f"Pollinations {resp.status_code}: {resp.text[:200]}")
    return Image.open(io.BytesIO(resp.content)).convert("RGB")


def _placeholder(prompt: str, width: int, height: int) -> Image.Image:
    img = Image.new("RGB", (width, height), (40, 33, 24))
    d = ImageDraw.Draw(img)
    for i in range(0, width + height, 60):
        d.line([(i, 0), (i - height, height)], fill=(60, 50, 36), width=2)
    d.text((40, 40), "OFFLINE PLACEHOLDER\n" + prompt[:120], fill=(201, 162, 90))
    return img


def generate(prompt: str, out_path: Path, width: int = 1024, height: int = 1024,
             offline: bool = False) -> Path:
    """Generate an image for `prompt` and save it as JPEG. Tries providers in order."""
    full_prompt = prompt.strip().rstrip(".") + config.IMAGE_STYLE_SUFFIX
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if offline:
        _placeholder(prompt, width, height).save(out_path, quality=92)
        return out_path

    errors = []
    for attempt in range(2):
        for name, fn in (("cloudflare", lambda: _cloudflare(full_prompt)),
                         ("pollinations", lambda: _pollinations(full_prompt, width, height))):
            try:
                img = fn()
                img.save(out_path, quality=92)
                print(f"[images] {name} ok -> {out_path.name} {img.size}")
                return out_path
            except Exception as exc:  # noqa: BLE001 - try the next provider
                errors.append(f"{name}#{attempt + 1}: {exc}")
                print(f"[images] {name} failed: {exc}")
        time.sleep(10)
    raise ImageGenError("All image providers failed: " + " | ".join(errors))
