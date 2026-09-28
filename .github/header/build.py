"""Build the profile header SVGs in assets/.

Text is converted to outlines so the header renders with the intended
typefaces everywhere, since GitHub serves SVGs as images and cannot load
web fonts.

Requirements: pip install fonttools uharfbuzz
Fonts (not committed):
  Inter 4.1          https://github.com/rsms/inter/releases
  JetBrains Mono     https://github.com/JetBrains/JetBrainsMono/releases
Point FONT_DIR at a folder holding the TTF files listed in FONTS.

Usage: FONT_DIR=/path/to/fonts python3 .github/header/build.py
"""

import os
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[2]
FONT_DIR = Path(os.environ.get("FONT_DIR", ROOT / ".fonts"))

FONTS = {
    "display": "InterDisplay-SemiBold.ttf",
    "text": "Inter-Regular.ttf",
    "mono": "JetBrainsMono-Regular.ttf",
    "mono-medium": "JetBrainsMono-Medium.ttf",
}

# For Creative Works palette.
THEMES = {
    "dark": {
        "bg": "#050505",
        "ink": "#F5F7F6",
        "muted": "#8B918E",
        "line": "#2A2D2C",
        "accent": "#0B8F63",
    },
    "light": {
        "bg": "#F5F7F6",
        "ink": "#050505",
        "muted": "#5E6461",
        "line": "#D5DAD7",
        "accent": "#0B8F63",
    },
}

SERVICES = ["Brand identity", "Web", "Photography", "Video", "Systems"]


class Font:
    def __init__(self, filename):
        path = FONT_DIR / filename
        self.tt = TTFont(path)
        self.glyphs = self.tt.getGlyphSet()
        self.order = self.tt.getGlyphOrder()
        self.upem = self.tt["head"].unitsPerEm
        blob = hb.Blob.from_file_path(str(path))
        self.hb = hb.Font(hb.Face(blob))

    def shape(self, text, size, tracking=0.0):
        """Return (glyph placements, advance width) in px."""
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(self.hb, buf, {"kern": True, "liga": True})
        scale = size / self.upem
        track = tracking * size
        placed, pen_x = [], 0.0
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            name = self.order[info.codepoint]
            placed.append((name, pen_x + pos.x_offset * scale, pos.y_offset * scale))
            pen_x += pos.x_advance * scale + track
        return placed, pen_x - track

    def width(self, text, size, tracking=0.0):
        return self.shape(text, size, tracking)[1]

    def path(self, text, size, x, y, tracking=0.0, anchor="start"):
        placed, width = self.shape(text, size, tracking)
        if anchor == "end":
            x -= width
        elif anchor == "middle":
            x -= width / 2
        scale = size / self.upem
        pen = SVGPathPen(self.glyphs, ntos=lambda v: f"{v:.2f}".rstrip("0").rstrip("."))
        for name, gx, gy in placed:
            # Font units are y-up; SVG is y-down.
            t = TransformPen(pen, (scale, 0, 0, -scale, x + gx, y - gy))
            self.glyphs[name].draw(t)
        return pen.getCommands()


def crop_marks(w, h, inset, length, gap, color):
    """Printer's crop marks at the four corners."""
    d = []
    for cx, sx in ((inset, 1), (w - inset, -1)):
        for cy, sy in ((inset, 1), (h - inset, -1)):
            d.append(f"M{cx - sx * (gap + length)} {cy}h{sx * length}")
            d.append(f"M{cx} {cy - sy * (gap + length)}v{sy * length}")
    return f'<path d="{"".join(d)}" stroke="{color}" stroke-width="1.5" fill="none"/>'


def svg(w, h, body, title, desc):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}" role="img" aria-labelledby="title desc">\n'
        f'  <title id="title">{title}</title>\n'
        f'  <desc id="desc">{desc}</desc>\n'
        + "".join(f"  {line}\n" for line in body)
        + "</svg>\n"
    )


TITLE = "Furkan Çakmak, designer and founder of For Creative Works"
DESC = (
    "Designer. I build the systems my one-person studio runs on. "
    "Brand identity, web, photography, video, systems. İzmir."
)


def desktop(f, c):
    w, h, m = 1280, 400, 72
    body = [
        f'<rect width="{w}" height="{h}" fill="{c["bg"]}"/>',
        crop_marks(w, h, 28, 16, 6, c["line"]),
        f'<path d="{f["mono-medium"].path("FOR CREATIVE WORKS", 14, m, 92, 0.14)}" fill="{c["ink"]}"/>',
        f'<path d="{f["mono"].path("İZMİR, TÜRKİYE", 14, m + 250, 92, 0.14)}" fill="{c["muted"]}"/>',
        f'<path d="{f["display"].path("Furkan Çakmak", 92, m - 5, 208, -0.02)}" fill="{c["ink"]}"/>',
        f'<path d="{f["text"].path("Designer. I build the systems my one-person studio runs on.", 25, m - 1, 260)}" fill="{c["muted"]}"/>',
    ]
    y, x = 92, w - m - 190
    for i, name in enumerate(SERVICES, 1):
        body.append(f'<path d="{f["mono"].path(f"0{i}", 14, x, y, 0.08)}" fill="{c["muted"]}"/>')
        body.append(f'<path d="{f["mono"].path(name.upper(), 14, x + 40, y, 0.08)}" fill="{c["ink"]}"/>')
        y += 31
    body += [
        f'<path d="M{m} 316H{w - m}" stroke="{c["line"]}" stroke-width="1.5"/>',
        f'<circle cx="{m + 6}" cy="316" r="6" fill="{c["accent"]}"/>',
        f'<path d="{f["mono"].path("ONE-PERSON CREATIVE STUDIO", 13, m, 352, 0.14)}" fill="{c["muted"]}"/>',
        f'<path d="{f["mono"].path("FORCREATIVEWORKS.COM", 13, w - m, 352, 0.14, "end")}" fill="{c["muted"]}"/>',
    ]
    return svg(w, h, body, TITLE, DESC)


def mobile(f, c):
    w, h, m = 720, 520, 44
    body = [
        f'<rect width="{w}" height="{h}" fill="{c["bg"]}"/>',
        crop_marks(w, h, 20, 12, 5, c["line"]),
        f'<path d="{f["mono-medium"].path("FOR CREATIVE WORKS", 15, m, 80, 0.14)}" fill="{c["ink"]}"/>',
        f'<path d="{f["mono"].path("İZMİR", 15, w - m, 80, 0.14, "end")}" fill="{c["muted"]}"/>',
        f'<path d="{f["display"].path("Furkan Çakmak", 80, m - 4, 186, -0.02)}" fill="{c["ink"]}"/>',
        f'<path d="{f["text"].path("Designer. I build the systems", 30, m - 1, 246)}" fill="{c["muted"]}"/>',
        f'<path d="{f["text"].path("my one-person studio runs on.", 30, m - 1, 286)}" fill="{c["muted"]}"/>',
    ]
    y = 352
    for i, name in enumerate(SERVICES, 1):
        col, row = divmod(i - 1, 3)
        x = m + col * 330
        yy = y + row * 32
        body.append(f'<path d="{f["mono"].path(f"0{i}", 15, x, yy, 0.08)}" fill="{c["muted"]}"/>')
        body.append(f'<path d="{f["mono"].path(name.upper(), 15, x + 42, yy, 0.08)}" fill="{c["ink"]}"/>')
    body += [
        f'<path d="M{m} 458H{w - m}" stroke="{c["line"]}" stroke-width="1.5"/>',
        f'<circle cx="{m + 6}" cy="458" r="6" fill="{c["accent"]}"/>',
    ]
    return svg(w, h, body, TITLE, DESC)


def main():
    fonts = {key: Font(name) for key, name in FONTS.items()}
    out = ROOT / "assets"
    for theme, colors in THEMES.items():
        (out / f"header-{theme}.svg").write_text(desktop(fonts, colors), encoding="utf-8")
        (out / f"header-mobile-{theme}.svg").write_text(mobile(fonts, colors), encoding="utf-8")


if __name__ == "__main__":
    main()
