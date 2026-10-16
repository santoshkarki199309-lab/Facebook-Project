"""Branding: photo-post frames (full or headline card) and 9:16 reel frames.

Every image carries a small honest tag: "AI illustration" or "Archive image".
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from . import config

GOLD = (201, 162, 90)
PARCHMENT = (233, 223, 201)
INK = (14, 13, 11)


def _font(path: Path, size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype(str(path), size)
    except OSError:
        return ImageFont.load_default()


def _wrap(d: ImageDraw.ImageDraw, text: str, font, max_w: int, max_lines: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for wd in words:
        trial = (cur + " " + wd).strip()
        if d.textbbox((0, 0), trial, font=font)[2] <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines[:max_lines]


def _mark(img: Image.Image, tagline: str, scale: float = 1.0, top: bool = False) -> None:
    """Brand mark: 'HISTORY UNSEALED' + tag ('AI illustration' / 'Archive image')."""
    d = ImageDraw.Draw(img, "RGBA")
    w, h = img.size
    f1 = _font(config.FONT_SERIF_BOLD, int(26 * scale))
    f2 = _font(config.FONT_SANS, int(17 * scale))
    t1 = config.BRAND_NAME.upper()
    b1, b2 = d.textbbox((0, 0), t1, font=f1), d.textbbox((0, 0), tagline, font=f2)
    tw = max(b1[2], b2[2])
    pad = int(18 * scale)
    box_h = b1[3] + b2[3] + int(6 * scale) + pad
    x = w - tw - pad * 2
    y = pad + pad // 2 if top else h - box_h - pad
    d.rounded_rectangle([x - pad, y - pad // 2, w - pad, y + box_h], radius=int(10 * scale),
                        fill=(14, 13, 11, 170))
    d.text((x, y), t1, font=f1, fill=PARCHMENT)
    d.text((x, y + b1[3] + int(6 * scale)), tagline, font=f2, fill=GOLD)


def photo_post(src: Path, out: Path, tagline: str = config.BRAND_TAGLINE, layout: str = "full",
               headline: str | None = None, kicker: str | None = None, size: int = 1080) -> Path:
    """Square 1080x1080 feed image.

    layout="full": the picture with a brand mark.
    layout="card": the picture with a dark gradient and a bold headline (and optional series
    kicker) across the bottom — a different look so the feed never feels template-made."""
    img = ImageOps.fit(Image.open(src).convert("RGB"), (size, size), Image.LANCZOS)
    if layout == "card" and headline:
        grad = Image.new("L", (1, size))
        for y in range(size):
            t = max(0.0, (y - size * 0.40) / (size * 0.60))
            grad.putpixel((0, y), int(235 * min(1.0, t * 1.15)))
        shade = Image.new("RGB", (size, size), INK)
        img = Image.composite(shade, img, grad.resize((size, size)))
        d = ImageDraw.Draw(img)
        fh = _font(config.FONT_SERIF_BOLD, 66)
        lines = _wrap(d, headline, fh, int(size * 0.86), 3)
        line_h = d.textbbox((0, 0), "Ag", font=fh)[3] + 14
        y = size - 70 - line_h * len(lines)
        if kicker:
            fk = _font(config.FONT_SANS, 28)
            d.text((int(size * 0.07), y - 52), kicker.upper(), font=fk, fill=GOLD)
        for line in lines:
            d.text((int(size * 0.07), y), line, font=fh, fill=PARCHMENT)
            y += line_h
        _mark(img, tagline, top=True)
    else:
        _mark(img, tagline)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, quality=93)
    return out


def reel_frame(src: Path, out: Path, w: int = 1080, h: int = 1920, hook: str | None = None,
               tagline: str = config.BRAND_TAGLINE, label: str | None = None) -> Path:
    """9:16 frame: blurred, darkened fill + full picture centred, brand at top.

    `hook`: large headline in the top band (first scene — the first 3 seconds decide retention).
    `label`: a gold chip on the picture, e.g. a year ("1908"), a place, or a countdown ("#3")."""
    im = Image.open(src).convert("RGB")
    bg = ImageOps.fit(im, (w, h), Image.LANCZOS).filter(ImageFilter.GaussianBlur(40))
    bg = Image.blend(bg, Image.new("RGB", (w, h), (10, 9, 8)), 0.55)
    fg = ImageOps.contain(im, (w, int(h * 0.62)), Image.LANCZOS)
    if fg.width < w:
        fg = ImageOps.fit(im, (w, w), Image.LANCZOS)
    img_top = int(h * 0.16)
    bg.paste(fg, ((w - fg.width) // 2, img_top))
    d = ImageDraw.Draw(bg, "RGBA")
    # Kept away from the edges: the slow zoom in the reel crops up to ~5% per side.
    fs = _font(config.FONT_SANS, 24)
    if hook:
        fh = _font(config.FONT_SERIF_BOLD, 60)
        lines = _wrap(d, hook.upper(), fh, int(w * 0.84), 2)
        y = int(h * 0.045)
        for line in lines:
            lb = d.textbbox((0, 0), line, font=fh)
            x = (w - lb[2]) // 2
            d.text((x + 3, y + 3), line, font=fh, fill=(0, 0, 0))
            d.text((x, y), line, font=fh, fill=PARCHMENT)
            y += lb[3] + 12
        brand = f"{config.BRAND_NAME.upper()} · {tagline}"
        bb = d.textbbox((0, 0), brand, font=fs)
        d.text(((w - bb[2]) // 2, min(y + 8, img_top - bb[3] - 6)), brand, font=fs, fill=GOLD)
    else:
        ft = _font(config.FONT_SERIF_BOLD, 46)
        title = config.BRAND_NAME.upper()
        tb = d.textbbox((0, 0), title, font=ft)
        sb = d.textbbox((0, 0), tagline, font=fs)
        d.text(((w - tb[2]) // 2, int(h * 0.085)), title, font=ft, fill=GOLD)
        d.text(((w - sb[2]) // 2, int(h * 0.085) + tb[3] + 10), tagline, font=fs, fill=PARCHMENT)
    if label:
        fl = _font(config.FONT_SERIF_BOLD, 54)
        lb = d.textbbox((0, 0), label.upper(), font=fl)
        x0, y0 = int(w * 0.11), img_top + 40
        d.rounded_rectangle([x0 - 18, y0 - 10, x0 + lb[2] + 18, y0 + lb[3] + 16], radius=12,
                            fill=(14, 13, 11, 200), outline=GOLD, width=3)
        d.text((x0, y0), label.upper(), font=fl, fill=GOLD)
    out.parent.mkdir(parents=True, exist_ok=True)
    bg.save(out, quality=93)
    return out
