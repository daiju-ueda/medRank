"""OGP card generation — 1200x630 PNG with the citation pulse as the visual signature."""
import io
import json

from PIL import Image, ImageDraw, ImageFont

from medrank.config import CURRENT_YEAR

W, H = 1200, 630
PAPER = (239, 236, 228)
INK = (23, 32, 29)
SLATE = (106, 113, 108)
TEAL = (12, 81, 72)
TEAL_FILL = (12, 81, 72, 34)
CRIMSON = (178, 58, 46)

_FONT_DIR = "/usr/share/fonts/truetype/dejavu"


def _font(name, size):
    return ImageFont.truetype(f"{_FONT_DIR}/{name}.ttf", size)


def _fit_font(draw, text, name, size, max_w, min_size=34):
    while size > min_size:
        f = _font(name, size)
        if draw.textlength(text, font=f) <= max_w:
            return f
        size -= 4
    return _font(name, min_size)


def _pulse_points(counts, x0, y0, w, h, span=11):
    if isinstance(counts, str):
        counts = json.loads(counts) if counts else []
    by_year = {c["year"]: c.get("cited_by_count", 0) for c in (counts or [])}
    vals = [by_year.get(y, 0) for y in range(CURRENT_YEAR - span + 1, CURRENT_YEAR + 1)]
    if not any(vals):
        return None
    hi = max(vals)
    dx = w / (len(vals) - 1)
    return [(x0 + i * dx, y0 + h - (v / hi) * h) for i, v in enumerate(vals)]


def render_card(title: str, subtitle: str, stat_value: str, stat_label: str,
                counts=None) -> bytes:
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img, "RGBA")

    # brand
    d.text((64, 48), "Med", font=_font("DejaVuSerif-Bold", 34), fill=INK)
    bw = d.textlength("Med", font=_font("DejaVuSerif-Bold", 34))
    d.ellipse((64 + bw + 8, 74, 64 + bw + 18, 84), fill=CRIMSON)
    d.text((64 + bw + 26, 48), "Rank", font=_font("DejaVuSerif-Bold", 34), fill=INK)

    # pulse (背景の主役)
    pts = _pulse_points(counts, 64, 330, W - 128, 190) if counts else None
    if pts:
        area = [(64, 560)] + pts + [(W - 64, 560)]
        d.polygon(area, fill=TEAL_FILL)
        d.line(pts, fill=CRIMSON, width=5, joint="curve")
        d.ellipse((pts[-1][0] - 7, pts[-1][1] - 7, pts[-1][0] + 7, pts[-1][1] + 7), fill=CRIMSON)

    # title / subtitle
    tf = _fit_font(d, title, "DejaVuSerif-Bold", 64, W - 128)
    d.text((64, 150), title, font=tf, fill=INK)
    if subtitle:
        sf = _fit_font(d, subtitle, "DejaVuSans", 30, W - 128, min_size=22)
        d.text((64, 165 + tf.size), subtitle, font=sf, fill=SLATE)

    # stat (右下)
    if stat_value:
        vf = _font("DejaVuSansMono-Bold", 72)
        lf = _font("DejaVuSansMono", 24)
        vw = d.textlength(stat_value, font=vf)
        lw = d.textlength(stat_label.upper(), font=lf)
        d.text((W - 64 - vw, H - 170), stat_value, font=vf, fill=TEAL)
        d.text((W - 64 - lw, H - 88), stat_label.upper(), font=lf, fill=SLATE)

    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()
