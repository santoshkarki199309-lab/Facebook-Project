"""Branding: square photo-post frames and 9:16 reel frames, with a small AI-disclosure mark."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from . import config

GOLD = (201, 162, 90)
PARCHMENT = (233, 223, 201)


def _font(path: Path, size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype(str(path), size)
    except OSError:
        return ImageFont.load_default()


def _mark(img: Image.Image, scale: float = 1.0) -> None:
    """Bottom-right brand mark: 'HISTORY UNSEALED · AI illustration'."""
    d = ImageDraw.Draw(img, "RGBA")
    w, h = img.size
    f1 = _font(config.FONT_SERIF_BOLD, int(26 * scale))
    f2 = _font(config.FONT_SANS, int(17 * scale))
    t1, t2 = config.BRAND_NAME.upper(), config.BRAND_TAGLINE
    b1, b2 = d.textbbox((0, 0), t1, font=f1), d.textbbox((0, 0), t2, font=f2)
    tw = max(b1[2], b2[2])
    pad = int(18 * scale)
    x = w - tw - pad * 2
    y = h - (b1[3] + b2[3]) - pad * 3
    d.rounded_rectangle([x - pad, y - pad // 2, w - pad, h - pad], radius=int(10 * scale),
                        fill=(14, 13, 11, 170))
    d.text((x, y), t1, font=f1, fill=PARCHMENT)
    d.text((x, y + b1[3] + int(6 * scale)), t2, font=f2, fill=GOLD)


def photo_post(src: Path, out: Path, size: int = 1080) -> Path:
    """Square 1080x1080 feed image with brand mark."""
    img = ImageOps.fit(Image.open(src).convert("RGB"), (size, size), Image.LANCZOS)
    _mark(img)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, quality=93)
    return out


def reel_frame(src: Path, out: Path, w: int = 1080, h: int = 1920) -> Path:
    """9:16 frame: blurred, darkened fill + full image centred, brand mark at bottom."""
    im = Image.open(src).convert("RGB")
    bg = ImageOps.fit(im, (w, h), Image.LANCZOS).filter(ImageFilter.GaussianBlur(40))
    bg = Image.blend(bg, Image.new("RGB", (w, h), (10, 9, 8)), 0.55)
    fg = ImageOps.contain(im, (w, int(h * 0.62)), Image.LANCZOS)
    if fg.width < w:
        fg = ImageOps.fit(im, (w, w), Image.LANCZOS)
    bg.paste(fg, ((w - fg.width) // 2, int(h * 0.16)))
    d = ImageDraw.Draw(bg)
    # Kept away from the edges: the slow zoom in the reel crops up to ~5% per side.
    ft, fs = _font(config.FONT_SERIF_BOLD, 46), _font(config.FONT_SANS, 24)
    title, sub = config.BRAND_NAME.upper(), config.BRAND_TAGLINE
    tb, sb = d.textbbox((0, 0), title, font=ft), d.textbbox((0, 0), sub, font=fs)
    d.text(((w - tb[2]) // 2, int(h * 0.085)), title, font=ft, fill=GOLD)
    d.text(((w - sb[2]) // 2, int(h * 0.085) + tb[3] + 10), sub, font=fs, fill=PARCHMENT)
    out.parent.mkdir(parents=True, exist_ok=True)
    bg.save(out, quality=93)
    return out
