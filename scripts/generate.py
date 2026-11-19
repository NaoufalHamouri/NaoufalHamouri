#!/usr/bin/env python3
"""Pixel profile generator.

Draws every image in ``assets/`` pixel by pixel from live GitHub data:

    hero.svg       the room: the arched window shows the sky over Tetouan right
                   now, the monitor types my latest commits, one book per language
    player.svg     RPG character card: the FGSM panda that turns into a gibbon
    stats.svg      XP / level / quests / best streak
    inventory.svg  the tech stack, as RPG items
    quests.svg     section title, followed by one quest-N.svg card per project
    activity.svg   contribution heatmap, patrolled by a cat
    footer.svg     CONTINUE? 9.. 8.. 7..

Usage:  python scripts/generate.py
Env:    GITHUB_TOKEN   optional: higher API limits + GraphQL contribution data
        PIXEL_PHASE    force the sky: night | dawn | day | dusk
        PIXEL_OFFLINE  1 = no network, re-render from assets/data.json

Only the standard library is needed. Text and content live in profile.json.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import os
import random
import re
import sys
import unicodedata
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
SNAPSHOT = ASSETS / "data.json"
API = "https://api.github.com"
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
OFFLINE = os.environ.get("PIXEL_OFFLINE") == "1"

# GitHub-dark card palette
CARD, BORDER, INSET = "#161b22", "#30363d", "#0d1117"
WHITE, SOFT, MUTED = "#f0f6fc", "#c9d1d9", "#8b949e"
GREEN, GREEN_DIM, YELLOW, BLUE = "#3fb950", "#238636", "#e3b341", "#58a6ff"
RARITY = {"legendary": "#f0883e", "epic": "#a371f7", "rare": "#58a6ff", "common": "#8b949e"}
MONTHS = "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split()
LANG_COLORS = {
    "Python": "#3572a5", "JavaScript": "#f1e05a", "TypeScript": "#3178c6", "PHP": "#4f5d95",
    "CSS": "#663399", "SCSS": "#c6538c", "HTML": "#e34c26", "Java": "#b07219", "C#": "#178600",
    "C": "#555555", "C++": "#f34b7d", "Jupyter Notebook": "#da5b0b", "Shell": "#89e051",
    "Twig": "#c1d026", "Go": "#00add8", "Rust": "#dea584", "Kotlin": "#a97bff", "Dart": "#00b4ab",
    "Vue": "#41b883", "Dockerfile": "#384d54", "R": "#198ce7", "TSQL": "#e38c00",
    "PLpgSQL": "#336790", "Ruby": "#701516", "Swift": "#f05138", "MATLAB": "#e16737",
}


# ═══════════════════════════════════════════════════════════════════ colour
def rgb(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def hexc(r, g, b):
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(v))) for v in (r, g, b))


def mix(a, b, t):
    (r1, g1, b1), (r2, g2, b2) = rgb(a), rgb(b)
    return hexc(r1 + (r2 - r1) * t, g1 + (g2 - g1) * t, b1 + (b2 - b1) * t)


def bright(c, f):
    return hexc(*(v * f for v in rgb(c)))


def luminance(c):
    r, g, b = rgb(c)
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255


def lang_color(lang):
    if lang in LANG_COLORS:
        return LANG_COLORS[lang]
    h = int(hashlib.md5((lang or "?").encode()).hexdigest()[:6], 16)
    return hexc(80 + h % 150, 80 + (h >> 8) % 150, 80 + (h >> 16) % 150)


BAYER = [[(v + .5) / 16 for v in row] for row in ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))]


def dither(stops, t, x, y):
    """Ordered-dither gradient: picks one of the two neighbouring stop colours."""
    t = min(1.0, max(0.0, t))
    for (p0, c0), (p1, c1) in zip(stops, stops[1:]):
        if t <= p1:
            k = (t - p0) / (p1 - p0) if p1 > p0 else 0
            return c1 if k > BAYER[y % 4][x % 4] else c0
    return stops[-1][1]


# ═══════════════════════════════════════════════════════════════════ fonts
SMALL = {k: v.split("/") for k, v in {  # 3x5, caps only
    "A": ".#./#.#/###/#.#/#.#", "B": "##./#.#/##./#.#/##.", "C": ".##/#../#../#../.##",
    "D": "##./#.#/#.#/#.#/##.", "E": "###/#../##./#../###", "F": "###/#../##./#../#..",
    "G": ".##/#../#.#/#.#/.##", "H": "#.#/#.#/###/#.#/#.#", "I": "###/.#./.#./.#./###",
    "J": "..#/..#/..#/#.#/.#.", "K": "#.#/#.#/##./#.#/#.#", "L": "#../#../#../#../###",
    "M": "#.#/###/###/#.#/#.#", "N": "##./#.#/#.#/#.#/#.#", "O": ".#./#.#/#.#/#.#/.#.",
    "P": "##./#.#/##./#../#..", "Q": ".#./#.#/#.#/##./.##", "R": "##./#.#/##./#.#/#.#",
    "S": ".##/#../.#./..#/##.", "T": "###/.#./.#./.#./.#.", "U": "#.#/#.#/#.#/#.#/###",
    "V": "#.#/#.#/#.#/#.#/.#.", "W": "#.#/#.#/###/###/#.#", "X": "#.#/#.#/.#./#.#/#.#",
    "Y": "#.#/#.#/.#./.#./.#.", "Z": "###/..#/.#./#../###",
    "0": "###/#.#/#.#/#.#/###", "1": ".#./##./.#./.#./###", "2": "##./..#/.#./#../###",
    "3": "##./..#/.#./..#/##.", "4": "#.#/#.#/###/..#/..#", "5": "###/#../##./..#/##.",
    "6": ".##/#../###/#.#/###", "7": "###/..#/.#./.#./.#.", "8": "###/#.#/###/#.#/###",
    "9": "###/#.#/###/..#/##.", " ": ".../.../.../.../...", ".": ".../.../.../.../.#.",
    ",": ".../.../.../.#./#..", ":": ".../.#./.../.#./...", ";": ".../.#./.../.#./#..",
    "-": ".../.../###/.../...", "_": ".../.../.../.../###", "+": ".../.#./###/.#./...",
    "=": ".../###/.../###/...", "/": "..#/..#/.#./#../#..", "\\": "#../#../.#./..#/..#",
    "!": ".#./.#./.#./.../.#.", "?": "##./..#/.#./.../.#.", "'": ".#./.#./.../.../...",
    '"': "#.#/#.#/.../.../...", "(": "..#/.#./.#./.#./..#", ")": "#../.#./.#./.#./#..",
    "[": "##./#../#../#../##.", "]": ".##/..#/..#/..#/.##", "<": "..#/.#./#../.#./..#",
    ">": "#../.#./..#/.#./#..", "#": "#.#/###/#.#/###/#.#", "%": "#.#/..#/.#./#../#.#",
    "&": ".#./#.#/.#./#.#/.##", "*": ".../#.#/.#./#.#/...", "@": "###/#.#/###/#../.##",
    "$": ".##/##./.#./.##/##.", "|": ".#./.#./.#./.#./.#.", "^": ".#./#.#/.../.../...",
    "`": "#../.#./.../.../...", "~": ".../.../.##/##./...", "·": ".../.../.#./.../...",
}.items()}

BIG = {  # 5x7 caps + lowercase with 2-row descenders
    "A": [".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "B": ["####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."],
    "C": [".###.", "#...#", "#....", "#....", "#....", "#...#", ".###."],
    "D": ["####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."],
    "E": ["#####", "#....", "#....", "####.", "#....", "#....", "#####"],
    "F": ["#####", "#....", "#....", "####.", "#....", "#....", "#...."],
    "G": [".###.", "#...#", "#....", "#.###", "#...#", "#...#", ".####"],
    "H": ["#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "I": [".###.", "..#..", "..#..", "..#..", "..#..", "..#..", ".###."],
    "J": ["..###", "...#.", "...#.", "...#.", "#..#.", "#..#.", ".##.."],
    "K": ["#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"],
    "L": ["#....", "#....", "#....", "#....", "#....", "#....", "#####"],
    "M": ["#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"],
    "N": ["#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"],
    "O": [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "P": ["####.", "#...#", "#...#", "####.", "#....", "#....", "#...."],
    "Q": [".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"],
    "R": ["####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"],
    "S": [".###.", "#...#", "#....", ".###.", "....#", "#...#", ".###."],
    "T": ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."],
    "U": ["#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "V": ["#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."],
    "W": ["#...#", "#...#", "#...#", "#.#.#", "#.#.#", "#.#.#", ".#.#."],
    "X": ["#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"],
    "Y": ["#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."],
    "Z": ["#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"],
    "a": [".....", ".....", ".###.", "....#", ".####", "#...#", ".####"],
    "b": ["#....", "#....", "####.", "#...#", "#...#", "#...#", "####."],
    "c": [".....", ".....", ".####", "#....", "#....", "#....", ".####"],
    "d": ["....#", "....#", ".####", "#...#", "#...#", "#...#", ".####"],
    "e": [".....", ".....", ".###.", "#...#", "#####", "#....", ".####"],
    "f": ["..###", "..#..", "..#..", "####.", "..#..", "..#..", "..#.."],
    "g": [".....", ".....", ".####", "#...#", "#...#", "#...#", ".####", "....#", ".###."],
    "h": ["#....", "#....", "####.", "#...#", "#...#", "#...#", "#...#"],
    "i": ["..#..", ".....", ".##..", "..#..", "..#..", "..#..", ".###."],
    "j": ["...#.", ".....", "..##.", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."],
    "k": ["#....", "#....", "#..#.", "#.#..", "##...", "#.#..", "#..#."],
    "l": [".##..", "..#..", "..#..", "..#..", "..#..", "..#..", ".###."],
    "m": [".....", ".....", "##.#.", "#.#.#", "#.#.#", "#.#.#", "#.#.#"],
    "n": [".....", ".....", "####.", "#...#", "#...#", "#...#", "#...#"],
    "o": [".....", ".....", ".###.", "#...#", "#...#", "#...#", ".###."],
    "p": [".....", ".....", "####.", "#...#", "#...#", "#...#", "####.", "#....", "#...."],
    "q": [".....", ".....", ".####", "#...#", "#...#", "#...#", ".####", "....#", "....#"],
    "r": [".....", ".....", "#.##.", "##..#", "#....", "#....", "#...."],
    "s": [".....", ".....", ".####", "#....", ".###.", "....#", "####."],
    "t": ["..#..", "..#..", "####.", "..#..", "..#..", "..#.#", "...#."],
    "u": [".....", ".....", "#...#", "#...#", "#...#", "#...#", ".####"],
    "v": [".....", ".....", "#...#", "#...#", "#...#", ".#.#.", "..#.."],
    "w": [".....", ".....", "#...#", "#...#", "#.#.#", "#.#.#", ".#.#."],
    "x": [".....", ".....", "#...#", ".#.#.", "..#..", ".#.#.", "#...#"],
    "y": [".....", ".....", "#...#", "#...#", "#...#", "#...#", ".####", "....#", ".###."],
    "z": [".....", ".....", "#####", "...#.", "..#..", ".#...", "#####"],
    "0": [".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."],
    "1": ["..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."],
    "2": [".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"],
    "3": ["#####", "...#.", "..#..", "...#.", "....#", "#...#", ".###."],
    "4": ["...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."],
    "5": ["#####", "#....", "####.", "....#", "....#", "#...#", ".###."],
    "6": ["..##.", ".#...", "#....", "####.", "#...#", "#...#", ".###."],
    "7": ["#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#..."],
    "8": [".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."],
    "9": [".###.", "#...#", "#...#", ".####", "....#", "...#.", ".##.."],
    " ": ["....."] * 7,
    ".": [".....", ".....", ".....", ".....", ".....", ".##..", ".##.."],
    ",": [".....", ".....", ".....", ".....", ".##..", "..#..", ".#..."],
    ":": [".....", ".##..", ".##..", ".....", ".##..", ".##..", "....."],
    "-": [".....", ".....", ".....", ".###.", ".....", ".....", "....."],
    "!": ["..#..", "..#..", "..#..", "..#..", "..#..", ".....", "..#.."],
    "?": [".###.", "#...#", "....#", "...#.", "..#..", ".....", "..#.."],
    "'": ["..#..", "..#..", ".#...", ".....", ".....", ".....", "....."],
    ">": [".#...", "..#..", "...#.", "....#", "...#.", "..#..", ".#..."],
    "<": ["...#.", "..#..", ".#...", "#....", ".#...", "..#..", "...#."],
    "/": ["....#", "...#.", "...#.", "..#..", ".#...", ".#...", "#...."],
    "@": [".###.", "#...#", "#.###", "#.#.#", "#.###", "#....", ".####"],
    "+": [".....", "..#..", "..#..", "#####", "..#..", "..#..", "....."],
    "&": [".##..", "#..#.", "#.#..", ".#...", "#.#.#", "#..#.", ".##.#"],
    "·": [".....", ".....", ".....", "..#..", ".....", ".....", "....."],
    "_": [".....", ".....", ".....", ".....", ".....", ".....", "#####"],
    "(": ["...#.", "..#..", ".#...", ".#...", ".#...", "..#..", "...#."],
    ")": [".#...", "..#..", "...#.", "...#.", "...#.", "..#..", ".#..."],
    "#": [".#.#.", ".#.#.", "#####", ".#.#.", "#####", ".#.#.", ".#.#."],
    "%": ["##..#", "##.#.", "...#.", "..#..", ".#...", ".#.##", "#..##"],
    "*": [".....", "#.#.#", ".###.", "#####", ".###.", "#.#.#", "....."],
    "=": [".....", ".....", "#####", ".....", "#####", ".....", "....."],
}
FONTS = {"s": (SMALL, 4), "b": (BIG, 6)}
REPLACE = {"—": "-", "–": "-", "’": "'", "‘": "'", "“": '"', "”": '"', "…": "...", "•": "·",
           "{": "(", "}": ")", "★": "*", "✓": "+"}


def clean(s):
    """Fold text onto the pixel fonts' ASCII set (keeps the middle dot)."""
    s = "".join(REPLACE.get(ch, ch) for ch in str(s)).replace("·", "\x01")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    return s.replace("\x01", "·")


def text_width(s, font="s", scale=1):
    return max(0, len(clean(s)) * FONTS[font][1] * scale - scale)


def wrap(s, width):
    lines, cur = [], ""
    for word in clean(s).split():
        if cur and len(cur) + 1 + len(word) > width:
            lines.append(cur)
            cur = ""
        cur = f"{cur} {word}" if cur else word[:width]
    return lines + [cur] if cur else lines


# ═══════════════════════════════════════════════════════════════════ canvas
class Canvas:
    """A grid of hex colours that serialises to compact SVG paths."""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.px = [[None] * w for _ in range(h)]

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[y][x] = c

    def get(self, x, y):
        return self.px[y][x] if 0 <= x < self.w and 0 <= y < self.h else None

    def rect(self, x, y, w, h, c):
        for yy in range(max(0, y), min(self.h, y + h)):
            row = self.px[yy]
            for xx in range(max(0, x), min(self.w, x + w)):
                row[xx] = c

    def blend(self, x, y, c, a):
        cur = self.get(x, y)
        if cur:
            self.px[y][x] = mix(cur, c, a)

    def ellipse(self, cx, cy, rx, ry, c, keep=None):
        for y in range(math.floor(cy - ry) - 1, math.ceil(cy + ry) + 1):
            for x in range(math.floor(cx - rx) - 1, math.ceil(cx + rx) + 1):
                if ((x + .5 - cx) / rx) ** 2 + ((y + .5 - cy) / ry) ** 2 <= 1 and (keep is None or keep(x, y)):
                    self.set(x, y, c)

    def line(self, x0, y0, x1, y1, c):
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        err = dx + dy
        while True:
            self.set(x0, y0, c)
            if x0 == x1 and y0 == y1:
                return
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def sprite(self, x, y, rows, pal, scale=1, keep=None):
        for r, row in enumerate(rows):
            for k, ch in enumerate(row):
                if ch in pal and (keep is None or keep(r, k)):
                    self.rect(x + k * scale, y + r * scale, scale, scale, pal[ch])

    def text(self, x, y, s, c, font="s", scale=1, shadow=None):
        table, adv = FONTS[font]
        s = clean(s)
        for col, off in ([(shadow, 1)] if shadow else []) + [(c, 0)]:
            cx = x
            for ch in s:
                g = table.get(ch.upper() if font == "s" else ch) or table.get(ch.upper())
                for r, row in enumerate(g or ()):
                    for k, v in enumerate(row):
                        if v == "#":
                            self.rect(cx + k * scale + off, y + r * scale + off, scale, scale, col)
                cx += adv * scale
        return len(s) * adv * scale - scale

    def rects(self):
        """Merge pixels into rectangles: horizontal runs, then identical runs stacked vertically."""
        done, active = [], {}
        for y in range(self.h + 1):
            runs = set()
            if y < self.h:
                row, x = self.px[y], 0
                while x < self.w:
                    c = row[x]
                    if c is None:
                        x += 1
                        continue
                    x2 = x
                    while x2 + 1 < self.w and row[x2 + 1] == c:
                        x2 += 1
                    runs.add((x, x2 - x + 1, c))
                    x = x2 + 1
            for key in [k for k in active if k not in runs]:
                y0 = active.pop(key)
                done.append((key[0], y0, key[1], y - y0, key[2]))
            for key in runs:
                active.setdefault(key, y)
        return sorted(done, key=lambda r: (r[4], r[1], r[0]))

    def paths(self):
        by_colour = {}
        for x, y, w, h, c in self.rects():
            by_colour.setdefault(c, []).append(f"M{x} {y}h{w}v{h}h-{w}z")
        return "".join(f'<path fill="{c}" d="{"".join(d)}"/>' for c, d in sorted(by_colour.items()))

    def outline(self):
        return "".join(f"M{x} {y}h{w}v{h}h-{w}z" for x, y, w, h, _ in self.rects())


def rounded(c, x, y, w, h, col, r=2):
    for j in range(h):
        d = r - j if j < r else (r - (h - 1 - j) if j >= h - r else 0)
        c.rect(x + d, y + j, w - 2 * d, 1, col)


def card(c, bg=CARD, border=BORDER):
    rounded(c, 0, 0, c.w, c.h, border, 3)
    rounded(c, 1, 1, c.w - 2, c.h - 2, bg, 2)


def layer(cls, cv, extra=""):
    p = cv.paths()
    return f'<g class="{cls}"{extra}>{p}</g>' if p else ""


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


MOTION = "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"


def svg(w, h, body, label, css="", defs=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w * 3}" height="{h * 3}" '
            f'shape-rendering="crispEdges" role="img" aria-label="{esc(label)}"><title>{esc(label)}</title>'
            f'<style>{css}{MOTION}</style>{defs}{body}</svg>\n')


# ═══════════════════════════════════════════════════════════════════ sprites
ICONS = {
    "python": ({"B": "#3776ab", "Y": "#ffd43b", "W": "#ffffff"}, [
        "...BBBBB....", "...BWBBB....", "...BBBBB....", ".BBBBBBB.YY.", "BBBBBBBB.YYY", "BBB......YYY",
        "BBB......YYY", "BBB.YYYYYYYY", ".BB.YYYYYYY.", "....YYYYY...", "....YYYWY...", "....YYYYY..."]),
    "pytorch": ({"R": "#ee4c2c"}, [
        ".....RR.....", "....RR......", "...RR...RR..", "..RR....RR..", ".RR.........", ".RR......RR.",
        "RR........RR", "RR........RR", "RR........RR", ".RR......RR.", "..RRR..RRR..", "...RRRRRR..."]),
    "docker": ({"c": "#7cc4fa", "B": "#1d63ed", "W": "#ffffff"}, [
        "............", "......cc....", "...cc.cc....", "cc.cc.cc....", "cc.cc.cc..B.", "BBBBBBBBBBBB",
        "BBBBBBBBBBB.", "BWBBBBBBBBB.", ".BBBBBBBBB..", "..BBBBBBB...", "....BBBB....", "............"]),
    "database": ({"T": "#ffcf7a", "L": "#fff0c9", "B": "#e38c00", "d": "#94570a"}, [
        "...TTTTTT...", ".TTLLLLLLTT.", ".TTTTTTTTTT.", ".BBBBBBBBBB.", ".dBBBBBBBBd.", "..dddddddd..",
        ".BBBBBBBBBB.", ".dBBBBBBBBd.", "..dddddddd..", ".BBBBBBBBBB.", ".dBBBBBBBBd.", "..dddddddd.."]),
    "elephant": ({"P": "#8892bf", "d": "#4f5b93", "E": "#1b1f2e"}, [
        "............", "...PPPPPPP..", "..PPPPPPPPP.", ".PEPdPPPPPPP", ".PPPdPPPPPPP", "PPPPdPPPPPPP",
        "P.PdPPPPPPPP", "P..PPPPPPPP.", "P..PP.PP.PP.", "PP.PP.PP.PP.", "...dd.dd.dd.", "............"]),
    "potion": ({"k": "#a0703a", "g": "#cfe3ea", "Y": "#f7df1e", "w": "#fffbe0"}, [
        "....kkkk....", "....kkkk....", "....g..g....", "....g..g....", "...g....g...", "..gYYYYYYg..",
        ".gYYwYYYYYg.", ".gYYYYYYYYg.", ".gYYYYYwYYg.", ".gYYYYYYYYg.", "..gYYYYYYg..", "...gggggg..."]),
    "git": ({"O": "#f05033"}, [
        "..OO........", ".OOOO.......", ".OOOO...OO..", "..OO...OOOO.", "..O....OOOO.", "..O.....OO..",
        "..O....O....", "..O...O.....", "..OOOO......", ".OOOO.......", ".OOOO.......", "..OO........"]),
    "antenna": ({"W": "#2bd9c5", "R": "#ff5b5b", "A": "#9aa4b1"}, [
        ".W........W.", "W..W....W..W", "W.W..RR..W.W", "W.W..RR..W.W", "W..W.AA.W..W", ".W...AA...W.",
        ".....AA.....", "....A..A....", "....A..A....", "...A.AA.A...", "...A....A...", "..AAAAAAAA.."]),
    "dagger": ({"W": "#9aa4b1", "L": "#f0f6fc", "G": "#e3b341", "h": "#8a5a2b"}, [
        "..........WL", ".........WLW", "........WLW.", ".......WLW..", "......WLW...", "..G..WLW....",
        "...GWLW.....", "....GW......", "...h.G......", "..hh..G.....", ".hh.........", "hh.........."]),
    "coffee": ({"C": "#5382a1", "K": "#6f4428", "s": "#f89820", "D": "#2f4b63"}, [
        "...s..s.....", "....s..s....", "...s..s.....", "............", ".CCCCCCCC...", ".CKKKKKKCCC.",
        ".CCCCCCCC..C", ".CCCCCCCC..C", ".CCCCCCCCCC.", "..CCCCCC....", "DDDDDDDDDD..", ".DDDDDDDD..."]),
    "gem": ({"G": "#3fb950", "g": "#1a7f37", "L": "#aff5b4"}, [
        "............", "...gGGGGg...", "..gGLLGGGg..", ".gGLLGGGGGg.", "gggggggggggg", ".gGGGGGGGGg.",
        "..gGGGGGGg..", "...gGGGGg...", "....gGGg....", ".....gg.....", "............", "............"]),
    "star": ({"Y": "#e3b341", "W": "#fff2c2"}, [
        ".....YY.....", ".....YY.....", "....YYYY....", "YYYYYWYYYYYY", ".YYYYWYYYYY.", "..YYYYYYYY..",
        "...YYYYYY...", "..YYYYYYYY..", "..YYY..YYY..", ".YY......YY.", ".Y........Y.", "............"]),
    "scroll": ({"P": "#e8d5a3", "d": "#a8844a", "k": "#6b4e2a"}, [
        ".dddddddddd.", "dPPPPPPPPPPd", ".dPPPPPPPPd.", "..PkkkkkkP..", "..PPPPPPPP..", "..PkkkkkPP..",
        "..PPPPPPPP..", "..PkkkkkkP..", "..PPPPPPPP..", ".dPPPPPPPPd.", "dPPPPPPPPPPd", ".dddddddddd."]),
    "flame": ({"R": "#b8321e", "O": "#f07a1a", "Y": "#ffd23f", "W": "#fff3b0"}, [
        "......R.....", ".....RR.....", ".....ROR....", "....ROOR....", "...ROOOR..R.", "...ROYOORRR.",
        "..ROOYYOOOR.", ".ROOYYWYOOR.", ".ROYYWWYYOR.", ".ROYWWWWYOR.", "..ROYWWYOR..", "...RRRRRR..."]),
}
STAR5 = ["..#..", ".###.", "#####", ".###.", ".#.#."]
CHECK = ["....#", "...##", "#.##.", "###..", ".#..."]
SPARK = [".#.", "###", ".#."]
CAT_SLEEP = [
    "..K...K...............", ".KGK.KGK..............", ".KGGGGGK..KKKKKKKK....",
    "KGGGGGGGKKGGgGGgGGKK..", "KGKKGKKGKGGgGGgGGGGGK.", "KGGGPGGGKGgGGgGGgGGGGK",
    ".KLLLLLKGGGGGGGGGGGGGK", "..KLLLKGGgGGgGGgGGGGGK", ".KKKKKKKKKKKKKKKKKgGGK",
    "KggggggggggggggggggGK.", ".KKKKKKKKKKKKKKKKKKK.."]
CAT_PAL = {"K": "#24243a", "G": "#9a9cab", "g": "#6e7082", "L": "#d8d9e3", "P": "#f0a5b5"}
CAT_WALK = [
    [".........W.W", "W........WWW", ".W.......WEW", ".WWWWWWWWWWW", "..WWWWWWWWW.", "..WWWWWWWW..", "..W.W...W.W."],
    ["...........", "W........W.W", ".W.......WWW", ".W.......WEW", ".WWWWWWWWWWW", "..WWWWWWWWW.", "...W.W.W.W.."],
]
LANTERN = [
    ".....bBb.....", "....bBBBb....", "...bBBBBBb...", "..bbbbbbbbb..", ".bbbbbbbbbbb.", "bAAAbRRRbTTTb",
    "bAaAbRrRbTtTb", "bAAAbRRRbTTTb", "bAAAbRRRbTTTb", "bbbbbbbbbbbbb", "bAAAbRRRbTTTb", "bAaAbRrRbTtTb",
    "bAAAbRRRbTTTb", ".bbbbbbbbbbb.", "..bbbbbbbbb..", "...bBBBBBb...", "....bBBBb....", ".....bBb.....",
    "......b......"]
LANTERN_PAL = {"b": "#8a5f1c", "B": "#c9952f", "A": "#ffb347", "a": "#ffe0a0", "R": "#ef5b3c",
               "r": "#ffb39e", "T": "#3fc1ad", "t": "#b8fff2"}
XRAY = [
    "............", "............", ".rrr.ss.rrr.", "r....ss....r", ".rrr.ss.rrr.", "r....ss....r",
    ".rrr.ss.rrr.", "r....ss....r", ".rrr.ss.rrr.", "r....ss....r", ".rr..ss..rr.", ".....ss.....",
    ".....ss.....", "...rrssrr...", "..r......r..", "............"]
TEAPOT = [
    "......hS........", ".....hSSs.......", "....dddddd......", "....hSSSSs......", "...hSSSSSSs...S.",
    ".s.hSSSSSSs..Ss.", "s..dddddddd.Ss..", "s.hSSSSSSSSsSs..", "s.hSSSSSSSSSs...", ".shSSSSSSSSs....",
    "..hSSSSSSSSs....", "...sSSSSSSs.....", "....dddddd......", "...dddddddd....."]
TEAPOT_PAL = {"h": "#f4f6fa", "S": "#c3c9d3", "s": "#8a919e", "d": "#5c6370"}
GLASS = ["gwwwwg", "gTTTTg", "gTLTTg", "gTTTTg", "gYYYYg", "gTTTTg", "gTTTTg", ".gTTg.", ".gggg."]
GLASS_PAL = {"g": "#cfe0e6", "w": "#e9f4f7", "T": "#c2862e", "L": "#5cb85c", "Y": "#e8c14a"}
DUCK = ["..YYY...", ".YEYYY..", "OOYYYY..", "..YYY..Y", ".YYYYYYY", ".YYYYYYY", "..ddddd."]
DUCK_PAL = {"Y": "#ffd23f", "O": "#ff8c1a", "E": "#1a1a1a", "d": "#d9a400"}
MINT = [
    "...g.G....", "..gGG.Gg..", ".GgG.gGG..", "..GGgGg.G.", ".gG.GGgGg.", "..gGGGG...", "...GgG....",
    "....G.....", "RRRRRRRRRR", ".PPPPPPPp.", ".PPPPPPPp.", "..PPPPPp..", "..PPPPPp..", "..PPPPPp..",
    "...PPPp..."]
MINT_PAL = {"G": "#5cb85c", "g": "#2e7d32", "R": "#d06b3f", "P": "#b4532c", "p": "#8a3d1f"}
TROPHY = ["YYYYYYY", "YhYYYYY", ".YhYYY.", ".YYYYY.", "..YYY..", "...Y...", "...Y...", "..ddd..", ".ddddd."]
SUCCULENT = ["..g..", "g.G.g", ".GgG.", "GgGgG", "rrrrr", ".rrr.", ".rrr."]
CLOUD_BIG = ["....WWWW........", "..WWWWWWWW.WW...", ".WWWWWWWWWWWWWW.", "WWWWWWWWWWWWWWWW", ".SSSSSSSSSSSSSS."]
CLOUD_SMALL = ["..WWW.....", ".WWWWWWW..", "WWWWWWWWWW", ".SSSSSSSS."]
GULL = [["W.....W", ".W...W.", "..WWW.."], [".......", "WWW.WWW", "...W..."]]
ZELLIGE = ["KWWBBWWK", "WWBYYBWW", "WBYGGYBW", "BYGWWGYB", "BYGWWGYB", "WBYGGYBW", "WWBYYBWW", "KWWBBWWK"]
ZELLIGE_PAL = {"K": "#18263f", "W": "#cfc6ae", "B": "#2b5c9c", "Y": "#c8963a", "G": "#2c7a58"}

# ═══════════════════════════════════════════════════════════════════ hero
W, H = 320, 180
HZ = 72                      # horizon line inside the window
WX0, WX1, WCY, WR, WY1 = 24, 103, 54, 40, 97   # arched window opening
IRON = "#15162a"
PHASES = {
    "night": {"room": 1.0, "cape": "#0c1130", "rim": "#151b42", "house": "#20264f", "stars": 30,
              "sky": [(0, "#070b24"), (.45, "#0e1540"), (.8, "#1a2460"), (1, "#27316f")],
              "sea": [(0, "#1c2659"), (.35, "#121a45"), (1, "#080d2a")]},
    "dawn": {"room": 1.12, "cape": "#3a2c58", "rim": "#4b3a6b", "house": "#d9c6d4", "stars": 5,
             "sky": [(0, "#1d2a5c"), (.3, "#4b3f80"), (.55, "#b0608c"), (.78, "#ee8a5c"), (1, "#ffc56e")],
             "sea": [(0, "#f0a060"), (.2, "#b0607a"), (.55, "#4a3a72"), (1, "#1c2350")]},
    "day": {"room": 1.35, "cape": "#5d8b58", "rim": "#7fae6c", "house": "#f5f2ea", "stars": 0,
            "sky": [(0, "#3a8ee0"), (.6, "#6db8f2"), (1, "#c4e9fc")],
            "sea": [(0, "#8fd3f5"), (.15, "#3b9be0"), (.6, "#2272bf"), (1, "#16508f")]},
    "dusk": {"room": 1.1, "cape": "#2f2350", "rim": "#3e2e64", "house": "#3a3466", "stars": 10,
             "sky": [(0, "#191340"), (.35, "#3b2a6c"), (.65, "#87478c"), (.88, "#de7889"), (1, "#f5aa8c")],
             "sea": [(0, "#c77a92"), (.25, "#6a4282"), (.6, "#33295f"), (1, "#15153a")]},
}


def phase_for(hour):
    if 5 <= hour < 8:
        return "dawn"
    if 8 <= hour < 17:
        return "day"
    if 17 <= hour < 21:
        return "dusk"
    return "night"


def in_win(x, y, grow=0):
    if y > WY1 + grow:
        return False
    if y + .5 >= WCY:
        return WX0 - grow <= x <= WX1 + grow
    return (x + .5 - 64) ** 2 + (y + .5 - WCY) ** 2 <= (WR + grow) ** 2


def draw_window(base, overlay, sky, P, phase, now, rng):
    is_sky = lambda x, y: in_win(x, y) and y <= HZ
    for y in range(14, WY1 + 1):
        for x in range(WX0, WX1 + 1):
            if in_win(x, y):
                base.set(x, y, dither(P["sky"], (y - 14) / (HZ - 14), x, y) if y <= HZ
                         else dither(P["sea"], (y - HZ - 1) / (WY1 - HZ - 1), x, y))

    hour = now.hour + now.minute / 60
    wa, wb = Canvas(W, H), Canvas(W, H)
    glint = None
    avoid = (0, 0, 0)
    if phase == "day":
        t = min(1, max(0, (hour - 8) / 9))
        sx, sy = 36 + t * 56, 42 - math.sin(math.pi * t) * 20
        for y in range(int(sy) - 12, int(sy) + 13):
            for x in range(int(sx) - 12, int(sx) + 13):
                if is_sky(x, y) and (x + .5 - sx) ** 2 + (y + .5 - sy) ** 2 <= 110:
                    base.blend(x, y, "#fff6d0", .22)
        base.ellipse(sx, sy, 6, 6, "#ffe27a", lambda x, y: is_sky(x, y))
        base.ellipse(sx - .5, sy - .5, 4.4, 4.4, "#fff6c4", lambda x, y: is_sky(x, y))
        glint, avoid = ("#fff6c4", sx), (sx, sy, 12)
    elif phase == "night":
        t = min(1, ((hour - 21) % 24) / 8)
        mx, my = 36 + t * 56, 44 - math.sin(math.pi * t) * 18
        for y in range(int(my) - 9, int(my) + 10):
            for x in range(int(mx) - 9, int(mx) + 10):
                if is_sky(x, y) and (x + .5 - mx) ** 2 + (y + .5 - my) ** 2 <= 64:
                    base.blend(x, y, "#9fb0ff", .16)
        base.ellipse(mx, my, 5, 5, "#efe9cc", lambda x, y: is_sky(x, y))
        for dx, dy in ((-2, -1), (1, 1), (2, -2), (-1, 2)):
            base.set(int(mx) + dx, int(my) + dy, "#d3cba9")
        glint, avoid = ("#d9d2a8", mx), (mx, my, 9)
    elif phase == "dawn":
        sx, sy = 46, HZ + 2
        for y in range(HZ - 18, HZ + 1):
            for x in range(sx - 22, sx + 23):
                d2 = (x + .5 - sx) ** 2 + ((y + .5 - sy) * 1.6) ** 2
                if is_sky(x, y) and d2 <= 22 ** 2:
                    base.blend(x, y, "#ffd9a0", .3 * (1 - d2 / 22 ** 2))
        base.ellipse(sx, sy, 8, 8, "#ffb347", lambda x, y: y <= HZ and in_win(x, y))
        base.ellipse(sx, sy, 6, 6, "#ffd77a", lambda x, y: y <= HZ and in_win(x, y))
        glint, avoid = ("#ffc070", sx), (sx, sy, 10)
    else:  # dusk: the sun sets behind the house, a thin moon rises over the sea
        base.ellipse(40, 28, 4, 4, "#f2ecd0", lambda x, y: (x + .5 - 42) ** 2 + (y + .5 - 27) ** 2 > 16)
        avoid = (40, 28, 6)

    # Cabo Negro headland with a few white houses
    tops = {}
    for x in range(76, WX1 + 1):
        t = (x - 76) / 27
        h = max(1, round(1 + 11 * t ** .85 + 1.3 * math.sin(x * .8)))
        tops[x] = HZ - h
        for y in range(HZ - h, HZ + 1):
            if in_win(x, y):
                base.set(x, y, P["cape"])
        base.set(x, HZ - h, P["rim"])
    town = Canvas(W, H), Canvas(W, H)
    for i, (hx, hw) in enumerate(((83, 2), (87, 3), (91, 2), (94, 3), (98, 2), (101, 2))):
        top = min(tops[x] for x in range(hx, hx + hw))
        base.rect(hx, top - 2, hw, 2, P["house"])
        if phase == "day":
            base.set(hx + hw - 1, top - 2, "#c9c4b8")
        elif phase in ("night", "dusk") and i != 3:
            town[i % 2].set(hx, top - 1, "#ffd27a")

    # stars
    tw = [Canvas(W, H) for _ in range(3)]
    placed = tries = 0
    while placed < P["stars"] and tries < 4000:
        tries += 1
        x, y = rng.randint(WX0 + 2, WX1 - 2), rng.randint(16, (40 if phase != "night" else HZ - 12))
        ax, ay, ar = avoid
        if not is_sky(x, y) or x in (63, 64) or y == WCY or (x - ax) ** 2 + (y - ay) ** 2 < ar * ar:
            continue
        cv = tw[placed % 3]
        if rng.random() < .15 and phase == "night":
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                cv.set(x + dx, y + dy, "#7f90d8")
            cv.set(x, y, "#ffffff")
        else:
            cv.set(x, y, rng.choice(["#cfd8ff", "#fff4d6", "#e8ecff"]) if phase == "night" else "#f6e6ef")
        placed += 1

    # sea shimmer + light path
    for cv in (wa, wb):
        for _ in range(16):
            y, x, w = rng.randint(HZ + 2, WY1 - 1), rng.randint(WX0, WX1 - 3), rng.randint(2, 4)
            for xx in range(x, x + w):
                if in_win(xx, y) and base.get(xx, y):
                    cv.set(xx, y, mix(base.get(xx, y), "#ffffff", .3))
    if glint:
        col, gx = glint
        for y in range(HZ + 2, WY1 + 1, 2):
            w = 1 + (y - HZ) // 6 + (2 if phase == "dawn" else 0)
            cv = wa if (y // 2) % 2 else wb
            jit = rng.randint(-1, 1)
            for xx in range(int(gx) - w // 2 + jit, int(gx) + (w + 1) // 2 + jit):
                if in_win(xx, y) and base.get(xx, y):
                    cv.set(xx, y, mix(base.get(xx, y), col, .7))
                    (wb if cv is wa else wa).set(xx + 2, y, mix(base.get(xx, y), col, .45))

    sky += [layer("tw1", tw[0]), layer("tw2", tw[1]), layer("tw3", tw[2]),
            layer("tw2", town[0]), layer("tw3", town[1]), layer("wa", wa), layer("wb", wb)]

    if phase in ("day", "dawn"):
        clouds = Canvas(W, H)
        pal = {"W": "#ffffff", "S": "#d6e6f2"} if phase == "day" else {"W": "#f7c6c0", "S": "#c98a9e"}
        spots = ((30, 22, CLOUD_BIG), (72, 31, CLOUD_SMALL), (48, 44, CLOUD_SMALL)) if phase == "day" \
            else ((34, 34, CLOUD_BIG), (76, 44, CLOUD_SMALL))
        for cx, cy, spr in spots:
            for dx in (0, -96):
                clouds.sprite(cx + dx, cy, spr, pal)
        sky.append(layer("cloud", clouds))
        gull_col = "#ffffff" if phase == "day" else "#2a2340"
        for n, gy in ((1, 30), (2, 40)):
            frames = []
            for f, frame in enumerate(GULL):
                cv = Canvas(W, H)
                cv.sprite(12 - n * 4, gy, frame, {"W": gull_col})
                frames.append(layer("fa" if f == 0 else "fb", cv))
            sky.append(f'<g class="gull{n}">{"".join(frames)}</g>')

    # frame: shadow, carved plaster, groove, zellige band, outline
    for y in range(6, WY1 + 8):
        for x in range(WX0 - 8, WX1 + 9):
            if in_win(x, y):
                continue
            k = next((g for g in range(1, 8) if in_win(x, y, g)), None)
            if k is None:
                continue
            col = {1: "#5e5244", 2: "#cbbd9f", 3: "#ddd1b5", 4: "#8c7d64", 7: "#14152a"}.get(k)
            if col is None:
                col = "#2b5c9c" if (x // 2 + y // 2) % 2 else "#e2dccb"
            base.set(x, y, col)
    base.rect(14, 98, 100, 3, "#e6dbc2")
    base.rect(14, 101, 100, 3, "#b9aa8b")
    base.rect(14, 104, 100, 1, "#121326")

    # in front of the glass: iron grille and the mint pot on the sill
    for x in range(WX0, WX1 + 1):
        overlay.set(x, WCY, IRON)
    for y in range(14, WY1 + 1):
        for x in (63, 64):
            if in_win(x, y):
                overlay.set(x, y, IRON)
    overlay.sprite(26, 83, MINT, MINT_PAL)


def render_hero(cfg, data, st, now, phase):
    P = PHASES[phase]
    lit = lambda c, k=1.0: bright(c, P["room"] * k)
    rng = random.Random(1907)
    base, overlay, front = Canvas(W, H), Canvas(W, H), Canvas(W, H)
    sky, anim = [], []

    # walls, trim, floor
    base.rect(0, 0, W, 110, lit("#1d2040"))
    for x in range(4, W, 10):
        base.rect(x, 0, 1, 110, lit("#212548"))
    base.rect(0, 110, W, 2, lit("#4b3c62"))
    base.rect(0, 112, W, 2, lit("#3a2d4d"))
    base.rect(0, 130, W, 2, lit("#2a1b13"))
    planks = ("#4a2d1d", "#51321f", "#45291a")
    for i, y in enumerate(range(132, H, 6)):
        x, j = -((i * 23) % 47), 0
        while x < W:
            n = 38 + (i * 7 + j * 13) % 20
            base.rect(x, y, n, 6, lit(planks[(i + j) % 3]))
            base.rect(x, y, 1, 6, lit("#2e1b11"))
            x, j = x + n, j + 1
        base.rect(0, y, W, 1, lit("#2e1b11"))
        base.rect(0, y + 1, W, 1, lit("#5e3c26"))
    for y in range(132, 144):
        for x in range(112, 276):
            base.blend(x, y, "#000000", .3 if y < 140 else .15)
    if phase == "day":
        for y in range(136, H):
            t = (y - 136) / 44
            for x in range(round(30 + 40 * t), round(104 + 66 * t)):
                base.blend(x, y, "#ffe9b0", .12)

    draw_window(base, overlay, sky, P, phase, now, rng)

    # light spill from the monitor and the neon sign, in soft pixel bands
    def spill(x0, y0, x1, y1, col, bands):
        reach = bands[-1][0]
        for y in range(y0 - reach, y1 + reach + 1):
            for x in range(x0 - reach, x1 + reach + 1):
                d = max(x0 - x, x - x1, y0 - y, y - y1)
                alpha = next((a for r, a in bands if 0 < d <= r), 0)
                if alpha:
                    base.blend(x, y, col, alpha)

    spill(134, 44, 250, 102, "#4f7fd0", ((3, .09), (7, .06), (13, .03)))
    name = cfg["name"].upper()
    tw_ = text_width(name, "b")
    bw = tw_ + 12
    bx = 192 - bw // 2
    spill(bx, 5, bx + bw - 1, 24, "#5ef2ff", ((2, .09), (5, .055), (9, .025)))

    # hanging lantern
    for y in range(0, 14):
        base.set(122, y, "#7a5a24" if y % 2 else "#a07a34")
    base.sprite(116, 14, LANTERN, LANTERN_PAL)

    # chest X-ray on a light box (the dataset behind the edge-AI project)
    base.rect(114, 56, 16, 20, "#30334a")
    base.rect(115, 57, 14, 18, "#132a3c")
    base.sprite(116, 58, XRAY, {"r": "#9db6c8", "s": "#d7e6f0"})

    # neon name sign
    base.rect(bx + 6, 0, 1, 5, "#3a3d5c")
    base.rect(bx + bw - 7, 0, 1, 5, "#3a3d5c")
    rounded(base, bx, 5, bw, 20, "#2b2e52", 2)
    rounded(base, bx + 1, 6, bw - 2, 18, "#11132a", 1)
    tx, ty = bx + 6, 11
    glyphs = Canvas(W, H)
    glyphs.text(tx, ty, name, "#ffffff", "b")
    for y in range(ty - 1, ty + 8):
        for x in range(tx - 1, tx + tw_ + 1):
            if not glyphs.get(x, y) and any(glyphs.get(x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
                base.set(x, y, "#1b5a66")
    k = max(i for i, ch in enumerate(name) if ch != " ") - 2
    while name[k] == " ":
        k -= 1
    for i, ch in enumerate(name):
        base.text(tx + i * 6, ty, ch, "#2d6f78" if i == k else "#8ff7ff", "b")
    flick = Canvas(W, H)
    flick.text(tx + k * 6, ty, name[k], "#8ff7ff", "b")
    anim.append(layer("flick", flick))

    # wall clock, set to local time
    cx, cy = 290, 21
    base.ellipse(cx + .5, cy + .5, 10, 10, "#3b3552")
    base.ellipse(cx + .5, cy + .5, 8.6, 8.6, "#ebe5d5")
    for dx, dy in ((0, -7), (7, 0), (0, 7), (-7, 0)):
        base.set(cx + dx, cy + dy, "#3b3552")
    ah = math.radians(((now.hour % 12) + now.minute / 60) * 30)
    am = math.radians(now.minute * 6)
    base.line(cx, cy, cx + round(math.sin(ah) * 4), cy - round(math.cos(ah) * 4), "#1a1a2a")
    base.line(cx, cy, cx + round(math.sin(am) * 6), cy - round(math.cos(am) * 6), "#1a1a2a")
    base.set(cx, cy, "#c0392b")

    # shelves: one book per language, then the edge-AI board
    for sy in (58, 84):
        base.rect(260, sy, 55, 2, "#7a5232")
        base.rect(260, sy + 2, 55, 1, "#4e331e")
        for bxx in (264, 309):
            base.rect(bxx, sy + 3, 2, 3, "#3b2616")
    langs = [lang for lang, _ in data.get("languages") or []] or ["Python"]
    x = 263
    for lang in langs[:7]:
        col = lang_color(lang)
        h = 12 + int(hashlib.md5(lang.encode()).hexdigest(), 16) % 6
        base.rect(x, 58 - h, 6, h, col)
        base.rect(x + 5, 58 - h, 1, h, bright(col, .7))
        base.rect(x, 58 - h + 2, 5, 1, mix(col, "#ffffff", .35))
        base.rect(x, 55, 5, 1, mix(col, "#ffffff", .35))
        base.text(x + 1, 58 - h + 4, lang[0], "#1b1b22" if luminance(col) > .55 else "#f0f0f0")
        x += 7
    base.rect(264, 79, 17, 5, "#1f6f46")
    base.rect(264, 83, 17, 1, "#15502f")
    base.rect(267, 80, 5, 3, "#1b1c22")
    for px_ in range(273, 280, 2):
        base.set(px_, 79, "#d4c050")
    base.set(276, 81, "#1d4a2a")
    base.set(278, 81, "#5a1d1d")
    led1, led2 = Canvas(W, H), Canvas(W, H)
    led1.set(278, 81, "#ff4d4d")
    led2.set(276, 81, "#3fff7a")
    anim += [layer("led1", led1), layer("led2", led2)]
    base.sprite(286, 77, SUCCULENT, {"g": "#2e7d32", "G": "#5cb85c", "r": "#b4532c"})

    # a stop sign wearing adversarial stickers (to a CNN it reads "speed limit 45")
    scx, scy = 296.5, 99.5
    octa = lambda x, y, r: max(abs(x + .5 - scx), abs(y + .5 - scy)) <= r and \
        abs(x + .5 - scx) + abs(y + .5 - scy) <= r * 1.42
    for y in range(90, 110):
        for x in range(286, 308):
            if octa(x, y, 8.5):
                base.set(x, y, "#c62828" if octa(x, y, 7.4) else "#f0f6fc")
    base.text(289, 98, "STOP", "#f0f6fc")
    base.rect(291, 94, 3, 3, "#111318")
    base.rect(298, 103, 4, 2, "#f0f6fc")
    base.set(299, 103, "#111318")
    base.set(301, 104, "#111318")
    base.rect(292, 103, 2, 2, "#ffd23f")
    base.sprite(300, 75, TROPHY, {"Y": "#e8b730", "h": "#fff1b0", "d": "#6b4c1c"})

    # monitor
    rounded(base, 134, 44, 117, 59, "#262a36", 2)
    base.rect(136, 45, 113, 1, "#353b4b")
    base.rect(137, 47, 111, 53, "#0a0e14")
    base.rect(137, 47, 111, 6, "#161b24")
    for i, col in enumerate(("#ff5f56", "#ffbd2e", "#27c93f")):
        base.rect(139 + i * 4, 49, 2, 2, col)
    title = f"ZSH - {cfg['name'].split()[0]}"
    base.text(192 - text_width(title) // 2, 48, title, "#6e7681")
    base.rect(190, 101, 4, 1, "#3d4456")
    base.sprite(236, 37, DUCK, DUCK_PAL)

    # desk and everything on it
    front.rect(116, 104, 157, 7, "#6b4529")
    front.rect(116, 104, 157, 1, "#7d5534")
    for gx, gy, gw in ((130, 107, 30), (196, 106, 40), (242, 108, 20)):
        front.rect(gx, gy, gw, 1, "#61402a")
    front.rect(116, 111, 157, 3, "#4f321d")
    front.rect(116, 114, 157, 1, "#2c1b10")
    for lx in (118, 267):
        front.rect(lx, 115, 4, 27, "#4f321d")
        front.rect(lx + 3, 115, 1, 27, "#2c1b10")
    front.rect(236, 115, 27, 23, "#5a3a22")
    for dy in (122, 130):
        front.rect(236, dy, 27, 1, "#3d2715")
    for dy in (118, 126, 134):
        front.rect(248, dy, 4, 1, "#c9a24a")
    front.rect(187, 102, 10, 4, "#262a36")
    front.rect(178, 105, 28, 2, "#262a36")
    front.rect(178, 105, 28, 1, "#353b4b")
    front.rect(166, 107, 44, 3, "#2a303d")
    front.rect(166, 107, 44, 1, "#3a4152")
    for kx in range(167, 209, 2):
        front.set(kx, 108, "#4d5568")
    front.rect(216, 108, 3, 2, "#c9d1d9")
    front.sprite(140, 99, GLASS, GLASS_PAL)
    front.sprite(253, 94, TEAPOT, TEAPOT_PAL)
    for cls, pts in (("st1", ((142, 96), (143, 94), (142, 92))), ("st2", ((144, 95), (143, 93), (144, 91)))):
        cv = Canvas(W, H)
        for sx_, sy_ in pts:
            cv.set(sx_, sy_, "#d9dee8")
        anim.append(layer(cls, cv))

    # office chair, seen from behind
    rounded(front, 174, 108, 33, 21, "#1d2029", 3)
    rounded(front, 175, 109, 31, 19, "#2b2f3d", 2)
    front.rect(177, 110, 27, 1, "#3c4255")
    front.rect(176, 111, 1, 14, "#3c4255")
    front.rect(190, 112, 1, 13, "#1d2029")
    front.rect(189, 129, 3, 10, "#1b1d26")
    front.rect(178, 139, 25, 2, "#1b1d26")
    for wx in (177, 189, 201):
        front.rect(wx, 141, 3, 2, "#0f1016")

    # berber rug + sleeping cat
    rx0, rx1, ry0, ry1 = 196, 293, 150, 171
    for x in range(rx0 + 1, rx1, 2):
        for y in (ry0 - 2, ry0 - 1, ry1 + 1, ry1 + 2):
            front.set(x, y, "#e6d8bb")
    front.rect(rx0, ry0, rx1 - rx0 + 1, ry1 - ry0 + 1, "#c8963a")
    front.rect(rx0 + 2, ry0 + 2, rx1 - rx0 - 3, ry1 - ry0 - 3, "#9a2c25")
    mid = (ry0 + ry1 + 1) / 2
    for y in range(ry0 + 3, ry1 - 1):
        for x in range(rx0 + 3, rx1 - 2):
            d = abs(((x - rx0 - 3) % 16) - 7.5) + abs(y + .5 - mid)
            col = "#efe0c2" if 6 <= d < 7.2 else "#1d2f4a" if d < 2.5 else "#e0a546" if d < 3.6 else None
            if col:
                front.set(x, y, col)
    catx, caty = 214, 145
    tip = lambda r, k: r >= 9 and k <= 3
    front.sprite(catx, caty, CAT_SLEEP, CAT_PAL, keep=lambda r, k: not tip(r, k))
    tail = Canvas(W, H)
    tail.sprite(catx, caty, CAT_SLEEP, CAT_PAL, keep=tip)
    anim.append(layer("tail", tail))
    for cls in ("z1", "z2", "z3"):
        cv = Canvas(W, H)
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            cv.text(catx + 6 + dx, caty - 7 + dy, "Z", "#1a1b2e")
        cv.text(catx + 6, caty - 7, "Z", "#e6edf3")
        anim.append(layer(cls, cv))

    # leather pouf
    pcx = 55
    front.ellipse(pcx, 166, 19, 3, "#2a190f")
    front.rect(pcx - 16, 150, 32, 14, "#a8512a")
    front.ellipse(pcx, 163.5, 16, 3.5, "#a8512a")
    front.rect(pcx - 16, 150, 5, 14, "#c2652f")
    front.rect(pcx + 8, 150, 8, 14, "#8c4120")
    for y in range(152, 166):
        for x in range(pcx - 15, pcx + 16):
            if front.get(x, y) and ((x - pcx) + abs(y - 158)) % 6 == 0:
                front.set(x, y, "#f0b25a")
    front.ellipse(pcx, 150, 16, 4, "#cf7a3e")
    front.ellipse(pcx, 150, 7, 2, "#f0b25a")
    front.ellipse(pcx, 150, 5.5, 1.2, "#cf7a3e")

    # snake plant in a terracotta pot
    for lx_, top in ((298, 128), (301, 118), (304, 124), (307, 132), (300, 136)):
        for y in range(top, 160):
            front.set(lx_ + 1, y, "#2f6b3a" if (y // 3) % 2 else "#4d8c4f")
            if y > top + 1:
                front.set(lx_, y, "#b8b85a")
                front.set(lx_ + 2, y, "#2a5c33")
    front.rect(295, 158, 17, 2, "#cf6a3d")
    for i, y in enumerate(range(160, 172)):
        front.rect(296 + i // 4, y, 15 - (i // 4) * 2, 1, "#b4532c")
        front.set(310 - i // 4, y, "#8a3d1f")

    # the terminal: types `git log`, then the latest commits appear one by one
    commits = data.get("commits") or [{"sha": "0000000", "message": "hello world"}]
    lines = [(c["sha"][:5], clean(c["message"]).upper()[:20]) for c in commits[:5]]
    cmd = "GIT LOG --ONELINE"
    term, css_lines = [], []
    head = Canvas(W, H)
    head.text(140, 56, "$", GREEN)
    head.text(148, 56, cmd, SOFT)
    term.append(head.paths())
    cw = text_width(cmd) + 1
    term.append(f'<rect class="cover" x="{148 + cw}" y="56" width="{cw}" height="5" fill="#0a0e14"/>')
    css_lines.append(
        f".cover{{animation:type 16s infinite}}@keyframes type{{0%{{transform:translateX(-{cw}px);"
        f"animation-timing-function:steps({len(cmd)},end)}}10%,95%{{transform:translateX(0)}}"
        f"95.5%,100%{{transform:translateX(-{cw}px)}}}}")
    for i, (sha, msg) in enumerate(lines + [(None, None)]):
        cv = Canvas(W, H)
        y = 63 + i * 6 if sha else 63 + len(lines) * 6 + 1
        extra = ""
        if sha is None:
            cv.text(140, y, "$", GREEN)
            cur = Canvas(W, H)
            cur.rect(148, y, 3, 5, SOFT)
            extra = layer("cur", cur)
        else:
            cv.text(140, y, sha, YELLOW)
            cv.text(164, y, msg, SOFT)
        at = 12 + i * 3.5 + (2 if sha is None else 0)
        term.append(f'<g class="ln{i}">{cv.paths()}{extra}</g>')
        css_lines.append(f".ln{i}{{animation:ln{i} 16s linear infinite}}@keyframes ln{i}{{0%,{at:.2f}%{{opacity:0}}"
                         f"{at + .01:.2f}%,95%{{opacity:1}}95.5%,100%{{opacity:0}}}}")
    anim.append(f'<g clip-path="url(#scr)">{"".join(term)}</g>')

    # warm lantern glow, flickering over everything
    glow = []
    for r, op in ((32, .05), (21, .06), (12, .08)):
        cv = Canvas(W, H)
        cv.ellipse(122.5, 24.5, r, r, "#ffb35c")
        glow.append(layer("g", cv, f' opacity="{op}"'))
    anim.append(f'<g class="glow">{"".join(glow)}</g>')

    tile = Canvas(8, 8)
    tile.sprite(0, 0, ZELLIGE, {k: lit(v, .85) for k, v in ZELLIGE_PAL.items()})
    win_mask = Canvas(W, H)
    for y in range(14, WY1 + 1):
        for x in range(WX0, WX1 + 1):
            if in_win(x, y):
                win_mask.set(x, y, "#000")
    defs = (f'<defs><clipPath id="win"><path d="{win_mask.outline()}"/></clipPath>'
            f'<clipPath id="scr"><rect x="137" y="53" width="111" height="47"/></clipPath>'
            f'<pattern id="zel" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="translate(0 114)">'
            f'{tile.paths()}</pattern></defs>')
    body = (base.paths() + f'<g clip-path="url(#win)">{"".join(sky)}</g>' + overlay.paths()
            + '<rect x="0" y="114" width="320" height="16" fill="url(#zel)"/>'
            + '<rect x="116" y="114" width="157" height="16" fill="#000" opacity=".35"/>'
            + front.paths() + "".join(anim))
    label = (f"Pixel-art room in {cfg.get('city', 'Morocco')} at {now:%H:%M}: the arched window shows the {phase} "
             f"sky over the Mediterranean, the monitor types my latest commits, a stop sign wears adversarial "
             f"stickers, mint tea steams and a cat sleeps on the rug.")
    return svg(W, H, body, label, HERO_CSS + "".join(css_lines), defs)


HERO_CSS = (
    "@keyframes tw{0%,100%{opacity:1}50%{opacity:.15}}"
    ".tw1{animation:tw 2.8s ease-in-out infinite}.tw2{animation:tw 3.7s ease-in-out -1.3s infinite}"
    ".tw3{animation:tw 4.6s ease-in-out -2.9s infinite}"
    "@keyframes sw{0%,49.9%{opacity:1}50%,100%{opacity:0}}"
    ".wa{animation:sw 1.8s infinite}.wb{animation:sw 1.8s -.9s infinite}"
    "@keyframes drift{to{transform:translateX(96px)}}.cloud{animation:drift 90s linear infinite}"
    "@keyframes fly{to{transform:translateX(104px)}}"
    ".gull1{animation:fly 17s linear infinite}.gull2{animation:fly 23s linear -11s infinite}"
    ".fa{animation:sw .6s infinite}.fb{animation:sw .6s -.3s infinite}"
    "@keyframes flick{0%,41%,43%,47%,100%{opacity:1}42%,44%,46%{opacity:0}}"
    ".flick{animation:flick 6s steps(1) infinite}"
    "@keyframes glow{0%,100%{opacity:1}20%{opacity:.8}45%{opacity:.95}70%{opacity:.75}85%{opacity:.9}}"
    ".glow{animation:glow 4s ease-in-out infinite}"
    "@keyframes steam{0%{transform:translateY(0);opacity:0}25%{opacity:.85}100%{transform:translateY(-8px);opacity:0}}"
    ".st1{animation:steam 3s linear infinite}.st2{animation:steam 3s linear -1.5s infinite}"
    ".cur{animation:sw 1s infinite}.led1{animation:sw 1.3s infinite}.led2{animation:sw 2.1s -.6s infinite}"
    "@keyframes tail{0%,78%,83%,89%,100%{transform:translateY(0)}80%,86%,92%{transform:translateY(-1px)}}"
    ".tail{animation:tail 5s steps(1) infinite}"
    "@keyframes zz{0%{transform:translate(0,0);opacity:0}20%{opacity:1}100%{transform:translate(5px,-12px);opacity:0}}"
    ".z1{animation:zz 4.5s linear infinite}.z2{animation:zz 4.5s linear -1.5s infinite}"
    ".z3{animation:zz 4.5s linear -3s infinite}"
)
BLINK = "@keyframes sw{0%,49.9%{opacity:1}50%,100%{opacity:0}}"


# ═══════════════════════════════════════════════════════════════════ cards
def blit(dst, src, x, y, scale=1):
    for yy, row in enumerate(src.px):
        for xx, col in enumerate(row):
            if col:
                dst.rect(x + xx * scale, y + yy * scale, scale, scale, col)


def panda():
    ink, fur = "#1b1b22", "#f2f2f2"
    p = Canvas(32, 32)
    p.rect(0, 0, 32, 32, "#24402f")
    for bx in (3, 27):  # bamboo
        p.rect(bx, 0, 2, 32, "#3f7a4a")
        for ny in (6, 15, 24):
            p.rect(bx - 1, ny, 4, 1, "#5fa36a")
    p.ellipse(16, 34, 14, 7, ink)
    p.ellipse(9, 9, 4.5, 4.5, ink)
    p.ellipse(23, 9, 4.5, 4.5, ink)
    p.ellipse(16, 18, 11.5, 10, fur)
    for y in range(24, 29):
        for x in range(32):
            if p.get(x, y) == fur:
                p.set(x, y, "#d9d9e1")
    p.ellipse(11.5, 17.5, 3, 3.8, ink)
    p.ellipse(20.5, 17.5, 3, 3.8, ink)
    p.set(12, 16, "#ffffff")
    p.set(19, 16, "#ffffff")
    p.rect(15, 21, 2, 2, ink)
    for x, y in ((14, 23), (15, 24), (16, 24), (17, 23)):
        p.set(x, y, ink)
    p.set(9, 22, "#f4a6b7")
    p.set(22, 22, "#f4a6b7")
    return p


def render_player(cfg, st):
    c = Canvas(320, 104)
    card(c)
    c.text(12, 10, "> PLAYER 1", GREEN)
    c.text(12, 20, cfg["name"], WHITE, "b", 2, shadow="#1f6feb")
    for i, (key, val) in enumerate((("CLASS", cfg["class"]), ("GUILD", cfg["guild"]), ("SPAWN", cfg["base"]))):
        c.text(12, 42 + i * 8, key, MUTED)
        c.text(36, 42 + i * 8, val, WHITE)
    for i, line in enumerate(wrap(cfg["tagline"], 37)[:2]):
        c.text(12, 68 + i * 11, line, SOFT, "b")

    lvl, lo, hi, xp = st["level"], st["lo"], st["hi"], st["xp"]
    c.text(12, 93, f"LV {lvl}", YELLOW)
    bx, bw = 36, 120
    fill = max(1, round((bw - 2) * (xp - lo) / max(1, hi - lo)))
    c.rect(bx, 92, bw, 7, BORDER)
    c.rect(bx + 1, 93, bw - 2, 5, INSET)
    c.rect(bx + 1, 93, fill, 5, "#2ea043")
    c.rect(bx + 1, 93, fill, 1, "#56d364")
    c.text(bx + bw + 6, 93, f"{xp - lo}/{hi - lo} XP TO LV {lvl + 1}", MUTED)
    shine = Canvas(320, 104)
    shine.rect(bx - 2, 93, 2, 5, "#aff5b4")

    # portrait slot: the classic FGSM panda. Every few seconds an epsilon-perturbation
    # washes over it and the classifier flips from "panda" to a very confident "gibbon".
    c.rect(240, 10, 70, 70, BORDER)
    c.rect(241, 11, 68, 68, "#e6edf3")
    c.rect(242, 12, 66, 66, INSET)
    blit(c, panda(), 243, 13, 2)
    rng = random.Random(7)
    noise_px = Canvas(32, 32)
    for y in range(32):
        for x in range(32):
            if rng.random() < .55:
                noise_px.set(x, y, rng.choice(("#ff4d6d", "#4dd2ff", "#7dff6a", "#ffd84d", "#b36bff")))
    noise, clean_lbl, adv_lbl = Canvas(320, 104), Canvas(320, 104), Canvas(320, 104)
    blit(noise, noise_px, 243, 13, 2)
    for cv, top, sub, col in ((clean_lbl, "PANDA 57.7%", "CLEAN INPUT", GREEN),
                              (adv_lbl, "GIBBON 99.3%", "+ EPS·SIGN(GRAD)", "#ff7b72")):
        cv.text(275 - text_width(top) // 2, 84, top, col)
        cv.text(275 - text_width(sub) // 2, 92, sub, MUTED)
    css = (BLINK + ".cln{animation:sw 6s infinite}.adv{opacity:0;animation:sw 6s -3s infinite}"
           f".shine{{animation:shine 3.2s linear infinite}}@keyframes shine{{0%{{transform:translateX(0)}}"
           f"60%,100%{{transform:translateX({fill + 2}px)}}}}")
    defs = f'<defs><clipPath id="xp"><rect x="{bx + 1}" y="93" width="{fill}" height="5"/></clipPath></defs>'
    body = (c.paths() + f'<g class="adv"><g opacity=".5">{noise.paths()}</g>{adv_lbl.paths()}</g>'
            + layer("cln", clean_lbl) + f'<g clip-path="url(#xp)">{layer("shine", shine)}</g>')
    label = f"Player 1: {cfg['name']}. Class: {cfg['class']}. Guild: {cfg['guild']}. {cfg['tagline']} Level {lvl}."
    return svg(320, 104, body, label, css, defs)


def fmt(n):
    if n < 1000:
        return str(n)
    if n < 10000:
        return f"{n / 1000:.1f}".rstrip("0").rstrip(".") + "K"
    return f"{n // 1000}K"


def render_stats(st):
    c, anim = Canvas(320, 40), []
    card(c)
    tiles = (("gem", fmt(st["xp"]), "XP EARNED"), ("star", str(st["level"]), "LEVEL"),
             ("scroll", str(st["quests"]), "QUESTS"), ("flame", f"{st['best']}D", "BEST STREAK"))
    for i, (icon, val, lab) in enumerate(tiles):
        x0 = i * 80
        if i:
            c.rect(x0, 8, 1, 24, BORDER)
        pal, rows = ICONS[icon]
        c.sprite(x0 + 10, 14, rows, pal)
        c.text(x0 + 28, 9, val, WHITE, "b", 2)
        c.text(x0 + 28, 27, lab, MUTED)
    spark = Canvas(320, 40)
    spark.sprite(19, 10, SPARK, {"#": "#e6ffec"})
    ember = Canvas(320, 40)
    for x, y in ((250, 12), (253, 10), (248, 9)):
        ember.set(x, y, "#ffd23f")
    body = c.paths() + layer("sp", spark) + layer("em", ember)
    css = BLINK + ".sp{animation:sw 2.4s infinite}.em{animation:sw .7s infinite}"
    label = (f"{st['xp']} XP earned (all-time contributions), level {st['level']}, {st['quests']} quests "
             f"(public repositories), best streak {st['best']} days")
    return svg(320, 40, body, label, css)


def render_inventory(cfg):
    items = cfg.get("inventory", [])[:12]
    rows = max(1, math.ceil(len(items) / 3))
    h = 24 + rows * 36
    c, spark = Canvas(320, h), Canvas(320, h)
    card(c)
    c.text(12, 10, "> INVENTORY", GREEN)
    tag = f"{len(items)} ITEMS EQUIPPED"
    c.text(308 - text_width(tag), 10, tag, MUTED)
    for i, it in enumerate(items):
        sx, sy = 12 + (i % 3) * 101, 22 + (i // 3) * 36
        rar = RARITY.get(it.get("rarity", "common"), RARITY["common"])
        rounded(c, sx, sy, 94, 30, mix(rar, CARD, .45), 2)
        rounded(c, sx + 1, sy + 1, 92, 28, INSET, 1)
        c.rect(sx + 3, sy + 3, 24, 24, CARD)
        pal, rows_ = ICONS.get(it.get("icon"), ICONS["scroll"])
        c.sprite(sx + 3, sy + 3, rows_, pal, 2)
        c.text(sx + 31, sy + 6, it["name"], WHITE, "b")
        c.text(sx + 31, sy + 19, it.get("item", ""), rar)
        if it.get("rarity") == "legendary":
            spark.sprite(sx + 87, sy + 3, SPARK, {"#": mix(rar, "#ffffff", .5)})
    label = "Inventory: " + ", ".join(it["name"] for it in items)
    return svg(320, h, c.paths() + layer("sp", spark), label, BLINK + ".sp{animation:sw 1.6s infinite}")


def render_quest_header():
    c = Canvas(320, 14)
    w = c.text(1, 3, "> QUEST LOG", GREEN, "b")
    for x in range(w + 8, 318, 4):
        c.rect(x, 6, 2, 1, GREEN_DIM)
    return svg(320, 14, c.paths(), "Quest log")


def invader(seed):
    bits = int(hashlib.md5(seed.encode()).hexdigest(), 16)
    grid = [[0] * 7 for _ in range(7)]
    for r in range(7):
        for k in range(4):
            grid[r][k] = grid[r][6 - k] = (bits >> (r * 4 + k)) & 1
    return grid


def render_quest(q, idx):
    w, h = 156, 78
    c = Canvas(w, h)
    card(c)
    c.rect(8, 8, 30, 30, "#1f3b66")
    c.rect(9, 9, 28, 28, "#0c2240")
    col = mix(lang_color(q.get("language")), "#ffffff", .35)
    for r, row in enumerate(invader(q["repo"])):
        for k, on in enumerate(row):
            if on:
                c.rect(12 + k * 3, 12 + r * 3, 3, 3, col)
                c.set(12 + k * 3, 12 + r * 3, mix(col, "#ffffff", .5))
    c.text(44, 9, f"QUEST {idx:02d}", MUTED)
    done = q.get("status", "cleared").lower() in ("cleared", "complete", "done")
    status = "CLEARED" if done else "IN PROGRESS"
    sx = w - 8 - text_width(status)
    c.text(sx, 9, status, GREEN if done else YELLOW)
    if done:
        c.sprite(sx - 7, 9, CHECK, {"#": GREEN})
    c.text(44, 18, q["title"], WHITE, "b")
    c.text(44, 31, q["repo"], BLUE)
    desc = wrap(q.get("description", ""), 35)
    if len(desc) > 3:
        desc = desc[:2] + [desc[2][:32].rstrip() + "..."]
    for i, line in enumerate(desc):
        c.text(8, 43 + i * 7, line, SOFT)
    lang = q.get("language") or "Code"
    c.rect(8, 68, 4, 4, lang_color(lang))
    c.text(15, 68, lang, MUTED)
    if q.get("stars"):
        right = str(q["stars"])
        rx = w - 8 - text_width(right)
        c.text(rx, 68, right, YELLOW)
        c.sprite(rx - 7, 68, STAR5, {"#": YELLOW})
    elif q.get("pushed_at"):
        right = f"UPDATED {MONTHS[int(q['pushed_at'][5:7]) - 1]} {q['pushed_at'][:4]}"
        c.text(w - 8 - text_width(right), 68, right, MUTED)
    label = f"Quest {idx:02d} ({status.lower()}): {q['title']} - {q['repo']}. {q.get('description', '')}"
    return svg(w, h, c.paths(), label)


def render_activity(data, st, today):
    w, h = 320, 84
    c, here = Canvas(w, h), Canvas(w, h)
    card(c)
    c.text(12, 9, "> ACTIVITY", GREEN)
    c.text(223 - text_width("LAST 12 MONTHS"), 9, "LAST 12 MONTHS", MUTED)
    levels = ("#21262d", "#0e4429", "#006d32", "#26a641", "#39d353")
    cal = sorted(data.get("calendar") or [])
    if cal:
        first = dt.date.fromisoformat(cal[0][0])
        start = first - dt.timedelta(days=(first.weekday() + 1) % 7)
        last_label, prev_month = -99, None
        for col in range(53):
            day = start + dt.timedelta(days=col * 7)
            if day.month != prev_month:
                x = 12 + col * 4
                if x - last_label >= 16 and x <= 212:
                    c.text(x, 19, MONTHS[day.month - 1], MUTED)
                    last_label = x
                prev_month = day.month
        for date, count, level in cal:
            k = (dt.date.fromisoformat(date) - start).days
            x, y = 12 + (k // 7) * 4, 28 + (k % 7) * 4
            if k // 7 < 53:
                c.rect(x, y, 3, 3, levels[min(4, max(0, int(level)))])
                if date == today.isoformat():
                    here.rect(x, y, 3, 3, WHITE)
    c.rect(12, 70, 212, 1, "#262c36")
    c.rect(230, 18, 1, 58, BORDER)
    stats = (("CURRENT STREAK", f"{st['current']} day" + ("" if st["current"] == 1 else "s")),
             ("BEST STREAK", f"{st['best']} day" + ("" if st["best"] == 1 else "s")),
             (f"CONTRIBS IN {today.year}", str(st["year"])))
    for i, (lab, val) in enumerate(stats):
        c.text(238, 20 + i * 22, lab, MUTED)
        c.text(238, 27 + i * 22, val, WHITE, "b")
    frames = []
    for f, rows in enumerate(CAT_WALK):
        cv = Canvas(w, h)
        cv.sprite(0, 70 - len(rows), rows, {"W": "#c9d1d9", "E": INSET})
        frames.append(layer("fa" if f == 0 else "fb", cv))
    defs = '<defs><clipPath id="walk"><rect x="12" y="56" width="212" height="14"/></clipPath></defs>'
    body = (c.paths() + layer("here", here)
            + f'<g clip-path="url(#walk)"><g class="cat">{"".join(frames)}</g></g>')
    css = (BLINK + ".here{animation:sw 1.2s infinite}.fa{animation:sw .5s infinite}.fb{animation:sw .5s -.25s infinite}"
           "@keyframes walk{to{transform:translateX(236px)}}.cat{animation:walk 30s linear infinite}")
    label = (f"Contribution heatmap for the last 12 months. Current streak {st['current']} days, best streak "
             f"{st['best']} days, {st['year']} contributions in {today.year}.")
    return svg(w, h, body, label, css, defs)


def render_footer(cfg, now):
    w, h = 320, 46
    c, blink = Canvas(w, h), Canvas(w, h)
    card(c)
    title = "CONTINUE?"
    x0 = (w - (text_width(title, "b", 2) + 22)) // 2
    c.text(x0, 8, title, "#79c0ff", "b", 2, shadow="#1f3b66")
    digits = []
    for slot, d in enumerate("9876543210"):
        cv = Canvas(w, h)
        cv.text(x0 + text_width(title, "b", 2) + 12, 8, d, YELLOW, "b", 2, shadow="#5a3d0a")
        digits.append(f'<g class="d" style="animation-delay:{slot - 10}s{";opacity:1" if slot == 0 else ""}">'
                      f'{cv.paths()}</g>')
    line = "PRESS FOLLOW TO JOIN THE PARTY"
    blink.text((w - text_width(line)) // 2, 27, line, YELLOW)
    saved = (f"GAME SAVED {now.day:02d} {MONTHS[now.month - 1]} {now.year} · {now:%H:%M} "
             f"{cfg.get('timezone_label', '')}").strip()
    c.text((w - text_width(saved)) // 2, 36, saved, MUTED)
    css = (BLINK + ".bl{animation:sw 1.4s infinite}.d{opacity:0;animation:cd 10s infinite}"
           "@keyframes cd{0%,9.9%{opacity:1}10%,100%{opacity:0}}")
    body = c.paths() + "".join(digits) + layer("bl", blink)
    return svg(w, h, body, f"Continue? Press follow to join the party. Last saved {now:%Y-%m-%d %H:%M}.", css)


# ═══════════════════════════════════════════════════════════════════ data
def http(url, data=None, accept="application/vnd.github+json"):
    headers = {"User-Agent": "pixel-profile-generator", "Accept": accept}
    if TOKEN and url.startswith(API):
        headers["Authorization"] = f"Bearer {TOKEN}"
    if data is not None:
        headers["Content-Type"] = "application/json"
    with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers), timeout=30) as resp:
        return resp.read()


def api(path):
    return json.loads(http(API + path))


def attempt(label, fn):
    try:
        return fn()
    except Exception as exc:  # keep the last good snapshot instead of failing the run
        print(f"[warn] {label}: {exc}", file=sys.stderr)
        return None


def fetch_languages(login, repos):
    total = {}
    for r in repos:
        for lang, n in api(f"/repos/{login}/{r['name']}/languages").items():
            total[lang] = total.get(lang, 0) + n
    return sorted(total.items(), key=lambda kv: (-kv[1], kv[0]))


def fetch_commits(login, repos):
    out = []
    for r in sorted(repos, key=lambda r: r["pushed_at"], reverse=True)[:4]:
        items = attempt(f"commits {r['name']}", lambda: api(f"/repos/{login}/{r['name']}/commits?author={login}&per_page=6"))
        for it in items or []:
            msg = (it["commit"]["message"] or "").strip().splitlines()
            out.append({"repo": r["name"], "sha": it["sha"][:7], "message": msg[0] if msg else "",
                        "date": it["commit"]["author"]["date"]})
    return sorted(out, key=lambda c: c["date"], reverse=True)[:5]


def fetch_contrib_graphql(login, first_year, now):
    years = range(first_year, now.year + 1)
    stamp = now.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    days_q = "contributionCalendar { weeks { contributionDays { date contributionCount contributionLevel } } }"
    parts = [f'y{y}: contributionsCollection(from: "{y}-01-01T00:00:00Z", to: "{stamp if y == now.year else f"{y}-12-31T23:59:59Z"}") {{ {days_q} }}'
             for y in years]
    query = f"query($login: String!) {{ user(login: $login) {{ recent: contributionsCollection {{ {days_q} }} {' '.join(parts)} }} }}"
    res = json.loads(http(API + "/graphql", json.dumps({"query": query, "variables": {"login": login}}).encode()))
    if res.get("errors") or not (res.get("data") or {}).get("user"):
        raise RuntimeError(res.get("errors") or "user not found")
    user = res["data"]["user"]
    level = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}
    flat = lambda key: [d for wk in user[key]["contributionCalendar"]["weeks"] for d in wk["contributionDays"]]
    calendar = [[d["date"], d["contributionCount"], level.get(d["contributionLevel"], 0)] for d in flat("recent")]
    days = {d["date"]: d["contributionCount"] for y in years for d in flat(f"y{y}") if d["contributionCount"]}
    days.update({d: n for d, n, _ in calendar if n})
    return sorted(calendar), days


def fetch_contrib_html(login, first_year, now):
    def page(query=""):
        html = http(f"https://github.com/users/{login}/contributions{query}", accept="text/html").decode("utf-8", "replace")
        tips = dict(re.findall(r'<tool-tip[^>]*?\bfor="([^"]+)"[^>]*>([^<]*)</tool-tip>', html))
        out = []
        for tag in re.findall(r"<td\b[^>]*ContributionCalendar-day[^>]*>", html):
            date, lvl = re.search(r'data-date="([\d-]+)"', tag), re.search(r'data-level="(\d)"', tag)
            cid = re.search(r'\bid="([^"]+)"', tag)
            if not date:
                continue
            m = re.match(r"\s*([\d,]+) contribution", tips.get(cid.group(1), "") if cid else "")
            out.append([date.group(1), int(m.group(1).replace(",", "")) if m else 0, int(lvl.group(1)) if lvl else 0])
        if not out:
            raise RuntimeError("contribution calendar markup not found")
        return sorted(out)

    calendar = page()
    days = {}
    for year in range(first_year, now.year + 1):
        days.update({d: n for d, n, _ in page(f"?from={year}-01-01&to={year}-12-31") if n})
    days.update({d: n for d, n, _ in calendar if n})
    return calendar, days


def collect(cfg, snap, now):
    data = dict(snap)
    data.pop("avatar", None)  # never store the profile photo
    if OFFLINE:
        return data
    login = cfg["login"]
    user = attempt("user", lambda: api(f"/users/{login}"))
    if user:
        data["user"] = {k: user.get(k) for k in ("login", "name", "created_at", "public_repos", "followers")}
    repos = attempt("repos", lambda: api(f"/users/{login}/repos?per_page=100&type=owner&sort=pushed"))
    if isinstance(repos, list):
        data["repos"] = [{"name": r["name"], "description": r.get("description") or "", "language": r.get("language"),
                          "stars": r.get("stargazers_count", 0), "pushed_at": r.get("pushed_at") or "",
                          "fork": bool(r.get("fork"))} for r in repos]
    own = [r for r in data.get("repos", []) if not r["fork"]]
    langs = attempt("languages", lambda: fetch_languages(login, own))
    if langs:
        data["languages"] = langs
    commits = attempt("commits", lambda: fetch_commits(login, own))
    if commits:
        data["commits"] = commits
    created = ((data.get("user") or {}).get("created_at") or "")[:4]
    first_year = int(created) if created.isdigit() else now.year - 1
    cal = attempt("contributions (graphql)", lambda: fetch_contrib_graphql(login, first_year, now)) if TOKEN else None
    cal = cal or attempt("contributions (html)", lambda: fetch_contrib_html(login, first_year, now))
    if cal:
        data["calendar"], data["days"] = cal
    return data


def derive(data, today):
    days = {}
    for key, n in (data.get("days") or {}).items():
        try:
            days[dt.date.fromisoformat(key)] = int(n)
        except ValueError:
            continue
    active = {d for d, n in days.items() if n > 0}
    best = run = 0
    prev = None
    for d in sorted(active):
        run = run + 1 if prev and (d - prev).days == 1 else 1
        best, prev = max(best, run), d
    current, d = 0, (today if today in active else today - dt.timedelta(days=1))
    while d in active:
        current, d = current + 1, d - dt.timedelta(days=1)
    xp = sum(days.values())
    level = 1 + math.isqrt(xp // 5)     # level L starts at 5*(L-1)^2 XP
    return {"xp": xp, "level": level, "lo": 5 * (level - 1) ** 2, "hi": 5 * level ** 2,
            "current": current, "best": best, "year": sum(n for d, n in days.items() if d.year == today.year),
            "quests": len([r for r in data.get("repos", []) if not r.get("fork")])}


def pick_quests(cfg, data):
    repos = {r["name"].lower(): r for r in data.get("repos", [])}
    quests = []
    for q in cfg.get("quests") or []:
        r = repos.get(q["repo"].lower(), {})
        quests.append({**q, "language": r.get("language"), "stars": r.get("stars", 0),
                       "pushed_at": r.get("pushed_at", ""), "description": q.get("description") or r.get("description", "")})
    if not quests:  # nothing configured: feature the most starred / recent repos
        pool = [r for r in data.get("repos", []) if not r["fork"] and r["name"].lower() != cfg["login"].lower()]
        pool.sort(key=lambda r: r["pushed_at"], reverse=True)
        for r in sorted(pool, key=lambda r: -r["stars"])[:4]:
            quests.append({"repo": r["name"], "title": r["name"].replace("-", " ").replace("_", " ").title()[:17],
                           "status": "cleared", **{k: r[k] for k in ("language", "stars", "pushed_at", "description")}})
    return quests[:4]


def replace_block(text, name, inner):
    pattern = re.compile(rf"(<!-- {name}:start -->).*?(<!-- {name}:end -->)", re.S)
    return pattern.sub(lambda m: f"{m.group(1)}\n{inner}\n{m.group(2)}", text)


def update_readme(cfg, quests):
    path = ROOT / "README.md"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    cards = "\n".join(
        f'  <a href="https://github.com/{cfg["login"]}/{q["repo"]}"><img src="assets/quest-{i}.svg" width="49%" '
        f'alt="Quest {i:02d}: {esc(q["title"])}. {esc(q.get("description", ""))}"></a>' for i, q in enumerate(quests, 1))
    text = replace_block(text, "quests", f'<p align="center">\n{cards}\n</p>')
    names = ", ".join(it["name"] for it in cfg.get("inventory", []))
    text = replace_block(text, "inventory", f'<p align="center">\n  <img src="assets/inventory.svg" width="100%" '
                                            f'alt="Inventory: {esc(names)}">\n</p>')
    path.write_text(text, encoding="utf-8", newline="\n")


def local_now(tz):
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.now(ZoneInfo(tz))
    except Exception:  # no tz database (bare Windows): Morocco is UTC+1 most of the year
        return dt.datetime.now(dt.timezone(dt.timedelta(hours=1)))


def main():
    cfg = json.loads((ROOT / "profile.json").read_text(encoding="utf-8"))
    now = local_now(cfg.get("timezone", "Africa/Casablanca"))
    phase = os.environ.get("PIXEL_PHASE", "").lower()
    phase = phase if phase in PHASES else phase_for(now.hour)
    snap = json.loads(SNAPSHOT.read_text(encoding="utf-8")) if SNAPSHOT.exists() else {}
    data = collect(cfg, snap, now)
    ASSETS.mkdir(exist_ok=True)
    SNAPSHOT.write_text("{\n" + ",\n".join(f"{json.dumps(k)}: {json.dumps(data[k], separators=(',', ':'), sort_keys=True)}"
                                           for k in sorted(data)) + "\n}\n", encoding="utf-8", newline="\n")
    st = derive(data, now.date())
    quests = pick_quests(cfg, data)
    out = {
        "hero.svg": render_hero(cfg, data, st, now, phase),
        "player.svg": render_player(cfg, st),
        "stats.svg": render_stats(st),
        "inventory.svg": render_inventory(cfg),
        "quests.svg": render_quest_header(),
        "activity.svg": render_activity(data, st, now.date()),
        "footer.svg": render_footer(cfg, now),
    }
    out.update({f"quest-{i}.svg": render_quest(q, i) for i, q in enumerate(quests, 1)})
    for stale in ASSETS.glob("quest-*.svg"):
        if stale.name not in out:
            stale.unlink()
    for name, text in out.items():
        (ASSETS / name).write_text(text, encoding="utf-8", newline="\n")
    update_readme(cfg, quests)
    print(f"rendered {len(out)} images | sky: {phase} | {now:%Y-%m-%d %H:%M} | xp {st['xp']} lv {st['level']}")


if __name__ == "__main__":
    main()
