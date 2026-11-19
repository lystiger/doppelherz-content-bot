"""Make a 1000x1500 (2:3) Pinterest image from the post's featured image.

Layout: the original photo is fitted whole (never cropped) on a blurred copy of
itself in the top area, and the pin title sits in a solid band below it.
No AI image generation is involved: no packaging errors, no AI-image label.
"""
import io
import textwrap
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

PIN_SIZE = (1000, 1500)
PHOTO_H = 960
BAND = (14, 42, 74)        # deep navy
ACCENT = (226, 0, 26)      # brand red accent line
FONT_BOLD = "/usr/share/fonts/noto/NotoSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/noto/NotoSans-Medium.ttf"


def _font(path: str, size: int):
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default(size)


def _photo_area(src: Image.Image, w: int, h: int) -> Image.Image:
    scale = max(w / src.width, h / src.height)
    bg = src.resize((round(src.width * scale), round(src.height * scale)))
    left, top = (bg.width - w) // 2, (bg.height - h) // 2
    bg = bg.crop((left, top, left + w, top + h)).filter(ImageFilter.GaussianBlur(40))
    bg = ImageEnhance.Brightness(bg).enhance(0.8)
    pad = 40
    fit = min((w - 2 * pad) / src.width, (h - 2 * pad) / src.height)
    fg = src.resize((round(src.width * fit), round(src.height * fit)))
    bg.paste(fg, ((w - fg.width) // 2, (h - fg.height) // 2))
    return bg


def make_pin_image(src: Image.Image, title: str = "") -> Image.Image:
    src = src.convert("RGB")
    w, h = PIN_SIZE
    canvas = Image.new("RGB", PIN_SIZE, BAND)
    canvas.paste(_photo_area(src, w, PHOTO_H), (0, 0))

    d = ImageDraw.Draw(canvas)
    d.rectangle((0, PHOTO_H, w, PHOTO_H + 10), fill=ACCENT)
    font = _font(FONT_BOLD, 54)
    lines = textwrap.wrap(title, width=30)[:5]
    y = PHOTO_H + 70
    for line in lines:
        d.text((70, y), line, font=font, fill="white")
        y += 72
    d.text((70, h - 95), "doppelherz.vn", font=_font(FONT_REG, 34), fill=(200, 210, 225))
    return canvas


def download_and_make_pin(url: str, out: Path, title: str = "") -> Path:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        img = Image.open(io.BytesIO(r.read()))
    out.parent.mkdir(parents=True, exist_ok=True)
    make_pin_image(img, title).save(out, "JPEG", quality=88)
    return out
