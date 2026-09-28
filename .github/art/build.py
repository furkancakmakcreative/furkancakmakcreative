"""Build the animated profile artwork in assets/.

Outputs a header and three project cards, each in dark and light themes
and in desktop and mobile sizes. Motion is plain CSS inside the SVG, which
GitHub plays when it shows the file as an image. Every element's resting
state is its final state, so with reduced motion the artwork is static and
complete.

Text is converted to outlines so the artwork renders with the intended
typefaces everywhere, since GitHub cannot load web fonts into images.

Requirements: pip install fonttools uharfbuzz
Fonts (not committed):
  Inter 4.1          https://github.com/rsms/inter/releases
  JetBrains Mono     https://github.com/JetBrains/JetBrainsMono/releases
Point FONT_DIR at a folder holding the TTF files listed in FONTS.

Usage: FONT_DIR=/path/to/fonts python3 .github/art/build.py
"""

import os
import random
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

# For Creative Works palette. Kora keeps its own app colours.
THEMES = {
    "dark": {
        "bg": "#050505",
        "panel": "#0C0D0D",
        "ink": "#F5F7F6",
        "muted": "#8B918E",
        "faint": "#3A3E3C",
        "line": "#262928",
        "accent": "#0B8F63",
        "accent-text": "#22B783",
        "on-accent": "#F5F7F6",
        "indigo": "#4A54E6",
        "amber": "#E7882C",
    },
    "light": {
        "bg": "#F5F7F6",
        "panel": "#FFFFFF",
        "ink": "#050505",
        "muted": "#5E6461",
        "faint": "#C9CFCC",
        "line": "#DCE1DE",
        "accent": "#0B8F63",
        "accent-text": "#0B8F63",
        "on-accent": "#FFFFFF",
        "indigo": "#3F49DC",
        "amber": "#E7882C",
    },
}

SERVICES = ["Brand identity", "Web", "Photography", "Video", "Systems"]

EASE = "cubic-bezier(.16,1,.3,1)"

BASE_CSS = """
.fb{transform-box:fill-box}
.c{transform-origin:center}
.l{transform-origin:left center}
.r{transform-origin:right center}
@keyframes fadeUp{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}
@keyframes fadeLeft{from{opacity:0;transform:translateX(14px)}to{opacity:1;transform:none}}
@keyframes fade{from{opacity:0}to{opacity:1}}
@keyframes rise{from{transform:translateY(120px)}to{transform:none}}
@keyframes drawX{from{transform:scaleX(0)}to{transform:scaleX(1)}}
@keyframes pop{0%{transform:scale(0)}60%{transform:scale(1.35)}100%{transform:scale(1)}}
@keyframes ring{0%{transform:scale(1);opacity:.6}70%,100%{transform:scale(3.6);opacity:0}}
@media (prefers-reduced-motion:reduce){*{animation:none!important}}
"""


def anim(name, dur, delay=0.0, count="1", ease=EASE):
    return f"animation:{name} {dur}s {ease} {delay:.2f}s {count} both"


def loop(name, dur, delay=0.0):
    return f"animation:{name} {dur}s linear {delay:.2f}s infinite both"


class Font:
    def __init__(self, filename):
        path = FONT_DIR / filename
        self.tt = TTFont(path)
        self.glyphs = self.tt.getGlyphSet()
        self.order = self.tt.getGlyphOrder()
        self.upem = self.tt["head"].unitsPerEm
        self.hb = hb.Font(hb.Face(hb.Blob.from_file_path(str(path))))

    def shape(self, text, size, tracking=0.0):
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(self.hb, buf, {"kern": True, "liga": True})
        scale = size / self.upem
        placed, pen_x = [], 0.0
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            placed.append((self.order[info.codepoint], pen_x + pos.x_offset * scale, pos.y_offset * scale))
            pen_x += pos.x_advance * scale + tracking * size
        return placed, pen_x - tracking * size

    def width(self, text, size, tracking=0.0):
        return self.shape(text, size, tracking)[1]

    def _draw(self, pen, name, size, x, y):
        s = size / self.upem
        # Font units are y-up; SVG is y-down.
        self.glyphs[name].draw(TransformPen(pen, (s, 0, 0, -s, x, y)))

    def _pen(self):
        return SVGPathPen(self.glyphs, ntos=lambda v: f"{v:.2f}".rstrip("0").rstrip("."))

    def path(self, text, size, x, y, tracking=0.0, anchor="start"):
        placed, width = self.shape(text, size, tracking)
        x -= {"start": 0, "middle": width / 2, "end": width}[anchor]
        pen = self._pen()
        for name, gx, gy in placed:
            self._draw(pen, name, size, x + gx, y - gy)
        return pen.getCommands()

    def glyph_paths(self, text, size, x, y, tracking=0.0):
        """One path per visible glyph, for letter-by-letter motion."""
        out = []
        for name, gx, gy in self.shape(text, size, tracking)[0]:
            pen = self._pen()
            self._draw(pen, name, size, x + gx, y - gy)
            if pen.getCommands():
                out.append(pen.getCommands())
        return out


class Canvas:
    """Collects SVG elements and keyframes for one file."""

    def __init__(self, w, h, fonts, colors):
        self.w, self.h, self.f, self.c = w, h, fonts, colors
        self.body, self.css = [], []

    def add(self, s):
        self.body.append(s)

    def keyframes(self, name, frames):
        self.css.append(f"@keyframes {name}{{{frames}}}")

    def text(self, font, s, size, x, y, color, tracking=0.0, anchor="start", style="", cls=""):
        d = self.f[font].path(s, size, x, y, tracking, anchor)
        attr = f' class="{cls}"' if cls else ""
        st = f' style="{style}"' if style else ""
        return f'<path{attr}{st} d="{d}" fill="{self.c[color]}"/>'

    def crop_marks(self, inset, length, gap):
        d = []
        for cx, sx in ((inset, 1), (self.w - inset, -1)):
            for cy, sy in ((inset, 1), (self.h - inset, -1)):
                d.append(f"M{cx - sx * (gap + length)} {cy}h{sx * length}")
                d.append(f"M{cx} {cy - sy * (gap + length)}v{sy * length}")
        return (
            f'<path style="{anim("fade", 1.2, 0.1)}" d="{"".join(d)}" '
            f'stroke="{self.c["faint"]}" stroke-width="1.5" fill="none"/>'
        )

    def render(self, title, desc):
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
            f'viewBox="0 0 {self.w} {self.h}" role="img" aria-labelledby="title desc">\n'
            f"<title id=\"title\">{title}</title>\n<desc id=\"desc\">{desc}</desc>\n"
            f"<style>{BASE_CSS}{''.join(self.css)}</style>\n"
            + "\n".join(self.body)
            + "\n</svg>\n"
        )


# ---------------------------------------------------------------- header

HEADER_TITLE = "Furkan Çakmak, designer and founder of For Creative Works"
HEADER_DESC = (
    "Designer. I build the systems my one-person studio runs on. "
    "Brand identity, web, photography, video, systems. İzmir."
)


def header_name(cv, size, x, y, delay):
    """Letters rise one by one out of a mask."""
    clip = f'<clipPath id="nm"><rect x="0" y="{y - size}" width="{cv.w}" height="{size * 1.3:.0f}"/></clipPath>'
    cv.add(clip)
    parts = []
    for i, d in enumerate(cv.f["display"].glyph_paths("Furkan Çakmak", size, x, y, -0.02)):
        parts.append(f'<path style="{anim("rise", 1.1, delay + i * 0.045)}" d="{d}"/>')
    cv.add(f'<g clip-path="url(#nm)" fill="{cv.c["ink"]}">{"".join(parts)}</g>')


def pulse_dot(cv, x, y, delay):
    c = cv.c["accent"]
    cv.add(f'<circle class="fb c" style="{loop("ring", 2.8, delay + 0.6)}" cx="{x}" cy="{y}" r="6" fill="none" stroke="{c}" stroke-width="1.5"/>')
    cv.add(f'<circle class="fb c" style="{anim("pop", 0.7, delay)}" cx="{x}" cy="{y}" r="6" fill="{c}"/>')


def service_marker(cv, x, y0, step, delay):
    n = len(SERVICES)
    frames = []
    for i in range(n):
        a, b = i * 100 / n, (i + 0.8) * 100 / n
        frames.append(f"{a:.1f}%,{b:.1f}%{{transform:translateY({i * step}px)}}")
    frames.append("100%{transform:translateY(0)}")
    cv.keyframes("svc", "".join(frames))
    cv.add(
        f'<rect style="animation:svc 12.5s {EASE} {delay}s infinite both" '
        f'x="{x}" y="{y0 - 9}" width="7" height="7" fill="{cv.c["accent"]}"/>'
    )


def header_desktop(f, c):
    w, h, m = 1280, 400, 72
    cv = Canvas(w, h, f, c)
    cv.add(f'<rect width="{w}" height="{h}" fill="{c["bg"]}"/>')
    cv.add(cv.crop_marks(28, 16, 6))
    cv.add(cv.text("mono-medium", "FOR CREATIVE WORKS", 14, m, 92, "ink", 0.14, style=anim("fadeUp", 0.9, 0.15)))
    cv.add(cv.text("mono", "İZMİR, TÜRKİYE", 14, m + 250, 92, "muted", 0.14, style=anim("fadeUp", 0.9, 0.3)))
    header_name(cv, 92, m - 5, 208, 0.35)
    cv.add(cv.text("text", "Designer. I build the systems my one-person studio runs on.", 25, m - 1, 260, "muted",
                   style=anim("fadeUp", 1.0, 1.05)))
    x, y = w - m - 190, 92
    for i, name in enumerate(SERVICES):
        st = anim("fadeLeft", 0.8, 0.6 + i * 0.09)
        cv.add(f'<g style="{st}">'
               + cv.text("mono", f"0{i + 1}", 14, x, y + i * 31, "muted", 0.08)
               + cv.text("mono", name.upper(), 14, x + 40, y + i * 31, "ink", 0.08) + "</g>")
    service_marker(cv, x - 22, y, 31, 2.2)
    cv.add(f'<path class="fb l" style="{anim("drawX", 1.4, 0.9)}" d="M{m} 316H{w - m}" stroke="{c["line"]}" stroke-width="1.5"/>')
    pulse_dot(cv, m + 6, 316, 0.8)
    cv.add(cv.text("mono", "ONE-PERSON CREATIVE STUDIO", 13, m, 352, "muted", 0.14, style=anim("fadeUp", 0.9, 1.3)))
    cv.add(cv.text("mono", "FORCREATIVEWORKS.COM", 13, w - m, 352, "muted", 0.14, "end", style=anim("fadeUp", 0.9, 1.4)))
    return cv.render(HEADER_TITLE, HEADER_DESC)


def header_mobile(f, c):
    w, h, m = 720, 520, 44
    cv = Canvas(w, h, f, c)
    cv.add(f'<rect width="{w}" height="{h}" fill="{c["bg"]}"/>')
    cv.add(cv.crop_marks(20, 12, 5))
    cv.add(cv.text("mono-medium", "FOR CREATIVE WORKS", 15, m, 80, "ink", 0.14, style=anim("fadeUp", 0.9, 0.15)))
    cv.add(cv.text("mono", "İZMİR", 15, w - m, 80, "muted", 0.14, "end", style=anim("fadeUp", 0.9, 0.3)))
    header_name(cv, 80, m - 4, 186, 0.35)
    cv.add(cv.text("text", "Designer. I build the systems", 30, m - 1, 246, "muted", style=anim("fadeUp", 1.0, 1.0)))
    cv.add(cv.text("text", "my one-person studio runs on.", 30, m - 1, 286, "muted", style=anim("fadeUp", 1.0, 1.1)))
    for i, name in enumerate(SERVICES):
        col, row = divmod(i, 3)
        x, y = m + col * 330, 352 + row * 32
        cv.add(f'<g style="{anim("fadeUp", 0.8, 1.2 + i * 0.08)}">'
               + cv.text("mono", f"0{i + 1}", 15, x, y, "muted", 0.08)
               + cv.text("mono", name.upper(), 15, x + 42, y, "ink", 0.08) + "</g>")
    cv.add(f'<path class="fb l" style="{anim("drawX", 1.4, 1.0)}" d="M{m} 458H{w - m}" stroke="{c["line"]}" stroke-width="1.5"/>')
    pulse_dot(cv, m + 6, 458, 0.9)
    return cv.render(HEADER_TITLE, HEADER_DESC)


# ---------------------------------------------------------------- motifs
# Each motif draws into a local 608 x 352 frame and loops forever.

FW, FH = 608, 352


def caption(cv, fig, text):
    return (cv.text("mono", fig, 12, 22, 34, "muted", 0.1)
            + cv.text("mono", text, 12, 22 + cv.f["mono"].width(fig, 12, 0.1) + 16, 34, "ink", 0.1))


def kora(cv, p):
    """Scattered to-dos collapse into one orb; one critical task comes out."""
    c, T = cv.c, 9
    out = [caption(cv, "FIG. 01", "TWENTY TASKS IN, ONE OUT")]
    ox, oy = 150, 196
    rnd = random.Random(7)
    for i in range(20):
        bw = rnd.choice([26, 34, 44, 56, 70, 84])
        x = rnd.uniform(24, FW - 24 - bw)
        y = rnd.uniform(62, FH - 30)
        dx, dy = ox - (x + bw / 2), oy - (y + 4)
        k = f"{p}b{i}"
        a = 2 + i * 0.3
        cv.keyframes(k, f"0%{{opacity:0;transform:none}}{a:.1f}%{{opacity:0;transform:translateY(8px)}}"
                        f"{a + 5:.1f}%,{24 + i * 0.2:.1f}%{{opacity:1;transform:none}}"
                        f"{34 + i * 0.1:.1f}%,100%{{opacity:0;transform:translate({dx:.1f}px,{dy:.1f}px) scale(.15)}}")
        out.append(f'<rect class="fb c" style="{loop(k, T)}" x="{x:.1f}" y="{y:.1f}" width="{bw}" height="8" rx="4" fill="{c["muted"]}" fill-opacity=".55"/>')
    cv.keyframes(f"{p}orb", "0%,28%{transform:scale(0)}36%{transform:scale(1.15)}40%,86%{transform:scale(1)}94%,100%{transform:scale(0)}")
    out.append(f'<circle class="fb c" style="{loop(p + "orb", T)}" cx="{ox}" cy="{oy}" r="46" fill="{c["indigo"]}"/>')
    cv.keyframes(f"{p}ln", "0%,38%{transform:scaleX(0);opacity:1}48%,86%{transform:scaleX(1);opacity:1}94%,100%{transform:scaleX(1);opacity:0}")
    out.append(f'<path class="fb l" style="{loop(p + "ln", T)}" d="M222 210H580" stroke="{c["amber"]}" stroke-width="3"/>')
    cv.keyframes(f"{p}tx", "0%,42%{opacity:0;transform:translateY(10px)}50%,86%{opacity:1;transform:none}94%,100%{opacity:0}")
    out.append(f'<g style="{loop(p + "tx", T)}">'
               + cv.text("mono", "TODAY", 12, 226, 160, "muted", 0.14)
               + cv.text("display", "One critical task.", 32, 224, 196, "ink", -0.01) + "</g>")
    for i, t in enumerate(["08:30", "13:00", "21:00"]):
        x, on = 226 + i * 118, 56 + i * 9
        k = f"{p}t{i}"
        cv.keyframes(k, f"0%,{on}%{{fill:{c['faint']}}}{on + 2}%,86%{{fill:{c['amber']}}}94%,100%{{fill:{c['faint']}}}")
        out.append(f'<g style="{loop(p + "tx", T)}">'
                   f'<circle style="{loop(k, T)}" cx="{x + 5}" cy="{276}" r="5" fill="{c["faint"]}"/>'
                   + cv.text("mono", t, 13, x + 18, 281, "muted", 0.06) + "</g>")
    return out


def imece(cv, p):
    """A brief moves through the stages; review sends it back once; you approve."""
    c, T = cv.c, 10
    out = [caption(cv, "FIG. 02", "EVERY OUTPUT PASSES A GATE")]
    # Eight roles, lit in a chase.
    rx = FW - 22 - 8 * 14 + 6
    out.append(cv.text("mono", "8 ROLES", 12, rx - 14, 34, "muted", 0.1, "end"))
    cv.keyframes(f"{p}role", f"0%{{fill:{c['accent']}}}12%,100%{{fill:{c['faint']}}}")
    for i in range(8):
        out.append(f'<rect style="{loop(p + "role", 2.4, i * 0.3)}" x="{rx + i * 14}" y="{25}" width="8" height="8" fill="{c["faint"]}"/>')

    stages = ["BRAND", "PLAN", "PROMPTS", "VISUALS", "REVIEW", "YOU"]
    x0, y, step = 56, 196, 99.2
    xs = [x0 + i * step for i in range(6)]
    arrive = [2, 10, 16, 22, 30, 66]
    out.append(f'<path d="M{x0} {y}H{xs[-1]}" stroke="{c["line"]}" stroke-width="2"/>')
    span = xs[-1] - x0
    cv.keyframes(f"{p}pr", "0%,2%{transform:scaleX(0);opacity:1}10%{transform:scaleX(.2)}16%{transform:scaleX(.4)}"
                           "22%{transform:scaleX(.6)}30%,60%{transform:scaleX(.8)}66%,88%{transform:scaleX(1);opacity:1}"
                           "95%,100%{transform:scaleX(1);opacity:0}")
    out.append(f'<path class="fb l" style="{loop(p + "pr", T)}" d="M{x0} {y}H{xs[-1]}" stroke="{c["accent"]}" stroke-width="2"/>')
    # Revision arc from REVIEW back to VISUALS.
    ax0, ax1 = xs[4], xs[3]
    arc = f"M{ax0} {y - 14}C{ax0 - 10} {y - 86} {ax1 + 10} {y - 86} {ax1} {y - 14}"
    cv.keyframes(f"{p}arc", "0%,32%{opacity:0}36%,88%{opacity:1}95%,100%{opacity:0}")
    out.append(f'<path style="{loop(p + "arc", T)}" d="{arc}" fill="none" stroke="{c["muted"]}" stroke-width="1.5" stroke-dasharray="4 6"/>')

    for i, (sx, name) in enumerate(zip(xs, stages)):
        a = arrive[i]
        k = f"{p}n{i}"
        cv.keyframes(k, f"0%,{max(a - 1, 0)}%{{fill:{c['panel']}}}{a}%,88%{{fill:{c['accent']}}}95%,100%{{fill:{c['panel']}}}")
        cv.keyframes(k + "s", f"0%,{max(a - 1, 0)}%{{stroke:{c['muted']}}}{a}%,88%{{stroke:{c['accent']}}}95%,100%{{stroke:{c['muted']}}}")
        out.append(f'<rect style="{loop(k, T)},{loop(k + "s", T).replace("animation:", "")}" x="{sx - 11}" y="{y - 11}" width="22" height="22" '
                   f'fill="{c["panel"]}" stroke="{c["muted"]}" stroke-width="1.5"/>')
        out.append(cv.text("mono", name, 11, sx, y + 40, "ink" if name == "YOU" else "muted", 0.1, "middle"))
    # Check mark on YOU.
    cv.keyframes(f"{p}ck", "0%,67%{opacity:0;transform:scale(.4)}71%,88%{opacity:1;transform:none}95%,100%{opacity:0}")
    yx = xs[-1]
    out.append(f'<path class="fb c" style="{loop(p + "ck", T)}" d="M{yx - 5} {y}l3.5 3.5 6.5-7" fill="none" '
               f'stroke="{c["on-accent"]}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>')
    # Status labels above the line.
    labels = [
        (xs[4], "REVISE", "muted", "0%,29%{opacity:0;transform:translateY(6px)}31%,48%{opacity:1;transform:none}52%,100%{opacity:0}"),
        (xs[3], "V2", "accent-text", "0%,44%{opacity:0;transform:translateY(6px)}46%,88%{opacity:1;transform:none}95%,100%{opacity:0}"),
        (xs[4], "PASS", "accent-text", "0%,53%{opacity:0;transform:translateY(6px)}55%,88%{opacity:1;transform:none}95%,100%{opacity:0}"),
        (xs[5], "APPROVED", "accent-text", "0%,66%{opacity:0;transform:translateY(6px)}69%,88%{opacity:1;transform:none}95%,100%{opacity:0}"),
    ]
    for i, (lx, name, col, frames) in enumerate(labels):
        k = f"{p}lb{i}"
        cv.keyframes(k, frames)
        out.append(cv.text("mono-medium", name, 11, lx, y - 104 if name != "V2" else y - 28, col, 0.12, "middle", style=loop(k, T)))
    # The travelling dot.
    X = [sx - x0 for sx in xs]
    pts = [(0, 0, 0), (2, 0, 0), (10, X[1], 0), (16, X[2], 0), (22, X[3], 0), (30, X[4], 0), (36, X[4], 0),
           (38, X[4] - 12, -44), (40, (X[3] + X[4]) / 2, -64), (42, X[3] + 12, -44), (44, X[3], 0), (48, X[3], 0),
           (54, X[4], 0), (60, X[4], 0), (66, X[5], 0), (88, X[5], 0)]
    frames = "".join(f"{t}%{{transform:translate({dx:.1f}px,{dy}px);opacity:1}}" for t, dx, dy in pts)
    frames += f"95%,100%{{transform:translate({X[5]:.1f}px,0);opacity:0}}"
    cv.keyframes(f"{p}dot", frames)
    out.append(f'<circle style="animation:{p}dot {T}s ease-in-out 0s infinite both" cx="{x0}" cy="{y}" r="5" fill="{c["ink"]}"/>')
    out.append(cv.text("mono", "THE REVIEWER RUNS ON CLEAN CONTEXT.", 12, 22, FH - 26, "muted", 0.14))
    return out


def curator(cv, p):
    """A scan reads each source; stale ones are struck and removed."""
    c, T = cv.c, 9
    out = [caption(cv, "FIG. 03", "FRESHNESS AUDIT")]
    dates = ["2026-09", "2024-11", "2026-07", "2023-05", "2026-08", "2024-02"]
    stale = [False, True, False, True, False, True]
    widths = [300, 240, 330, 210, 280, 260]
    top, gap = 84, 40
    fresh_index = 0
    for i in range(6):
        y = top + i * gap
        t = 10 + (i + 0.6) / 6 * 34
        if stale[i]:
            move = "translateX(-24px)"
            end = f"{t:.1f}%,52%{{opacity:1;transform:none}}60%,100%{{opacity:0;transform:{move}}}"
        else:
            dy = (fresh_index - i) * gap
            fresh_index += 1
            end = f"{t:.1f}%,52%{{opacity:1;transform:none}}60%,88%{{opacity:1;transform:translateY({dy}px)}}95%,100%{{opacity:0;transform:translateY({dy}px)}}"
        k = f"{p}r{i}"
        cv.keyframes(k, f"0%{{opacity:0;transform:none}}{2 + i:.1f}%{{opacity:0;transform:translateY(6px)}}{6 + i:.1f}%,{end}")
        row = [
            f'<rect x="24" y="{y - 13}" width="13" height="17" rx="1.5" fill="none" stroke="{c["muted"]}" stroke-width="1.5"/>',
            f'<rect x="54" y="{y - 8}" width="{widths[i]}" height="8" rx="4" fill="{c["faint"]}"/>',
            cv.text("mono", dates[i], 12, 430, y, "muted", 0.06),
        ]
        sk = f"{p}s{i}"
        cv.keyframes(sk, f"0%,{t - 1:.1f}%{{opacity:0;transform:translateX(8px)}}{t + 1:.1f}%,100%{{opacity:1;transform:none}}")
        row.append(cv.text("mono-medium", "STALE" if stale[i] else "FRESH", 11, FW - 22, y, "muted" if stale[i] else "accent-text",
                           0.12, "end", style=loop(sk, T)))
        if stale[i]:
            lk = f"{p}x{i}"
            cv.keyframes(lk, f"0%,{t + 1:.1f}%{{transform:scaleX(0)}}{t + 5:.1f}%,100%{{transform:scaleX(1)}}")
            row.append(f'<path class="fb l" style="{loop(lk, T)}" d="M20 {y - 4}H{500}" stroke="{c["ink"]}" stroke-width="1.5"/>')
        out.append(f'<g style="{loop(k, T)}">{"".join(row)}</g>')
    cv.keyframes(f"{p}scan", "0%,8%{transform:translateY(0);opacity:0}10%{opacity:1}44%{transform:translateY(250px);opacity:1}"
                             "48%,100%{transform:translateY(250px);opacity:0}")
    out.append(f'<g style="{loop(p + "scan", T)}"><rect x="16" y="{top - 30}" width="{FW - 32}" height="26" fill="{c["accent"]}" opacity=".08"/>'
               f'<path d="M16 {top - 4}H{FW - 16}" stroke="{c["accent"]}" stroke-width="1.5"/></g>')
    cv.keyframes(f"{p}done", "0%,62%{opacity:0;transform:translateY(8px)}68%,88%{opacity:1;transform:none}95%,100%{opacity:0}")
    out.append(f'<g style="{loop(p + "done", T)}"><rect x="22" y="{top + 3 * gap + 18}" width="8" height="8" fill="{c["accent"]}"/>'
               + cv.text("mono", "STALE SOURCES REMOVED. LIBRARY FRESH.", 12, 40, top + 3 * gap + 27, "ink", 0.12) + "</g>")
    return out


# ---------------------------------------------------------------- cards

PROJECTS = [
    {
        "slug": "kora",
        "index": "01",
        "kind": "PRIVATE · CLAUDE CODE",
        "name": "Kora",
        "tagline": ["An accountability partner.", "One critical task a day."],
        "tags": "MORNING · NOON · EVENING",
        "motif": kora,
        "desc": "Kora: scattered to-dos collapse into one orb and a single critical task comes out, followed by morning, noon and evening check-ins.",
    },
    {
        "slug": "imece",
        "index": "02",
        "kind": "PRIVATE · CLAUDE CODE",
        "name": "İmece",
        "tagline": ["Studio production system.", "Nothing approves itself."],
        "tags": "8 ROLES · REVIEW · APPROVAL",
        "motif": imece,
        "desc": "İmece: a brief moves through brand, plan, prompts and visuals. Review sends it back once, the second version passes, and the final approval is mine.",
    },
    {
        "slug": "curator",
        "index": "03",
        "kind": "OPEN SOURCE · MCP",
        "name": "notebooklm-curator",
        "tagline": ["Audits NotebookLM libraries", "and prunes stale sources."],
        "tags": "MCP · BROWSER AUTOMATION",
        "motif": curator,
        "desc": "notebooklm-curator: a scan reads each source in a NotebookLM library, marks stale ones and removes them.",
    },
]


def frame(cv, x, y, scale, motif, prefix):
    c = cv.c
    w, h = FW * scale, FH * scale
    cv.add(f'<rect x="{x}" y="{y}" width="{w:.0f}" height="{h:.0f}" fill="{c["panel"]}" stroke="{c["line"]}" stroke-width="1.5"/>')
    cv.add(f'<g transform="translate({x} {y}) scale({scale:.4f})">{"".join(motif(cv, prefix))}</g>')


def card_text(cv, pr, x, label_y, name_y, name_max, name_w, tag_y, tag_size, line_gap):
    cv.add(cv.text("mono", pr["index"], tag_size + 1, x, label_y, "muted", 0.12))
    cv.add(cv.text("mono", pr["kind"], tag_size + 1, x + 44, label_y, "ink", 0.12))
    size = min(name_max, name_max * name_w / cv.f["display"].width(pr["name"], name_max, -0.02))
    cv.add(cv.text("display", pr["name"], size, x - size * 0.05, name_y, "ink", -0.02))
    for i, line in enumerate(pr["tagline"]):
        cv.add(cv.text("text", line, line_gap * 0.75, x, name_y + line_gap * 1.7 + i * line_gap, "muted"))
    if tag_y:
        cv.add(f'<rect x="{x}" y="{tag_y - 8}" width="7" height="7" fill="{cv.c["accent"]}"/>')
        cv.add(cv.text("mono", pr["tags"], tag_size, x + 18, tag_y, "muted", 0.14))


def card_desktop(f, c, pr):
    w, h = 1280, 440
    cv = Canvas(w, h, f, c)
    cv.add(f'<rect width="{w}" height="{h}" fill="{c["bg"]}"/>')
    cv.add(cv.crop_marks(24, 14, 5))
    card_text(cv, pr, 72, 100, 204, 84, 470, 376, 13, 32)
    frame(cv, 604, 44, 1.0, pr["motif"], pr["slug"])
    return cv.render(f"{pr['name']}", pr["desc"])


def card_mobile(f, c, pr):
    w, h = 720, 780
    cv = Canvas(w, h, f, c)
    cv.add(f'<rect width="{w}" height="{h}" fill="{c["bg"]}"/>')
    cv.add(cv.crop_marks(18, 12, 5))
    card_text(cv, pr, 44, 78, 164, 76, 632, None, 14, 38)
    frame(cv, 44, 318, 632 / FW, pr["motif"], pr["slug"])
    cv.add(f'<rect x="44" y="{h - 52}" width="7" height="7" fill="{c["accent"]}"/>')
    cv.add(cv.text("mono", pr["tags"], 15, 62, h - 44, "muted", 0.14))
    return cv.render(f"{pr['name']}", pr["desc"])


def main():
    fonts = {key: Font(name) for key, name in FONTS.items()}
    out = ROOT / "assets"
    for theme, colors in THEMES.items():
        (out / f"header-{theme}.svg").write_text(header_desktop(fonts, colors), encoding="utf-8")
        (out / f"header-mobile-{theme}.svg").write_text(header_mobile(fonts, colors), encoding="utf-8")
        for pr in PROJECTS:
            (out / f"card-{pr['slug']}-{theme}.svg").write_text(card_desktop(fonts, colors, pr), encoding="utf-8")
            (out / f"card-{pr['slug']}-mobile-{theme}.svg").write_text(card_mobile(fonts, colors, pr), encoding="utf-8")


if __name__ == "__main__":
    main()
