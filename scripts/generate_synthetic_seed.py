"""Generate the synthetic demo seed: procedurally rendered images + seed/metadata.csv (+ projects.json, SOURCES.md).

Every image is drawn from code with Pillow + numpy (no photographs, no real places). Locations and dates are
fictional. The output is deterministic, so re-running produces the same files.

Usage:
    python scripts/generate_synthetic_seed.py            # writes seed/images/*.jpg, seed/metadata.csv, ...
    python scripts/generate_synthetic_seed.py --force    # overwrite existing metadata.csv / projects.json

Then build the analyzed seed with scripts/seed_cloudinary.py (needs Cloudinary + Gemini keys).
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import zlib
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
SEED = ROOT / "seed"
IMAGES = SEED / "images"
GENERATOR = "Procedural (Pillow + numpy), `scripts/generate_synthetic_seed.py`"

W, H = 1600, 1200
PAD = 60  # rendered margin, cropped away to vary the viewpoint between shots


# --- drawing helpers --------------------------------------------------------------------------------------

def rgb(c, k=1.0):
    return tuple(int(max(0, min(255, v * k))) for v in c)


def noise(rng, size, blur, amp):
    """Smooth zero-mean noise field, (h, w)."""
    n = Image.fromarray((rng.random((size[1], size[0])) * 255).astype("uint8"))
    n = np.asarray(n.filter(ImageFilter.GaussianBlur(blur)), dtype=float)
    n = (n - n.mean()) / (n.std() + 1e-6)
    return n * amp


def fill(img, rng, poly, base, amp=18, blur=2.0, coarse=0.0):
    """Fill a polygon with a textured colour."""
    w, h = img.size
    tex = np.ones((h, w, 3)) * np.array(base, dtype=float)
    n = noise(rng, (w, h), blur, amp)
    if coarse:  # large blotches (patchy soil, worn concrete)
        low = Image.fromarray(noise(rng, (w // 8, h // 8), 2, 1).astype("float32")).resize((w, h), Image.BILINEAR)
        n += np.asarray(low, dtype=float) * coarse
    tex += n[..., None]
    layer = Image.fromarray(np.clip(tex, 0, 255).astype("uint8"))
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).polygon(poly, fill=255)
    img.paste(layer, (0, 0), mask)


def sky(img, rng, horizon, top=(118, 164, 214), bottom=(206, 222, 236), clouds=6):
    d = ImageDraw.Draw(img)
    for y in range(horizon + 2):
        t = y / max(1, horizon)
        d.line([(0, y), (img.width, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))
    cl = Image.new("RGBA", img.size, (0, 0, 0, 0))
    cd = ImageDraw.Draw(cl)
    for _ in range(clouds):
        cx, cy = rng.uniform(0, img.width), rng.uniform(20, horizon * 0.6)
        for _ in range(9):
            rx, ry = rng.uniform(50, 130), rng.uniform(18, 40)
            ox, oy = rng.uniform(-120, 120), rng.uniform(-20, 20)
            cd.ellipse([cx + ox - rx, cy + oy - ry, cx + ox + rx, cy + oy + ry], fill=(255, 255, 255, 120))
    img.alpha_composite(cl.filter(ImageFilter.GaussianBlur(14)))


def treeline(img, rng, y, color=(62, 92, 58), height=70, step=26):
    pts = [(0, y)]
    x = 0
    while x <= img.width:
        pts.append((x, y - rng.uniform(0.4, 1.0) * height))
        x += rng.uniform(step * 0.6, step * 1.4)
    pts += [(img.width, y), (img.width, y + 4), (0, y + 4)]
    fill(img, rng, pts, color, amp=10, blur=1.5)


def buildings(img, rng, y, n=9):
    d = ImageDraw.Draw(img)
    x = rng.uniform(-40, 0)
    palette = [(196, 180, 160), (170, 160, 150), (214, 196, 170), (150, 158, 168), (205, 170, 140)]
    while x < img.width:
        bw, bh = rng.uniform(90, 200), rng.uniform(60, 190)
        c = palette[int(rng.integers(len(palette)))]
        d.rectangle([x, y - bh, x + bw, y], fill=c)
        d.rectangle([x, y - bh, x + bw, y - bh + 6], fill=rgb(c, 0.8))
        for wy in np.arange(y - bh + 18, y - 14, 26):
            for wx in np.arange(x + 10, x + bw - 16, 24):
                d.rectangle([wx, wy, wx + 11, wy + 13], fill=rgb(c, 0.55))
        x += bw + rng.uniform(4, 30)


def depth(y, horizon, h):
    """Perspective scale factor at screen row y (0 at the horizon, 1 at the bottom)."""
    return max(0.02, (y - horizon) / (h - horizon))


def finish(img, rng, shot, rotate):
    """Crop a slightly different viewpoint per shot, add grain + vignette, return a W x H RGB image."""
    img = img.convert("RGB")
    if rotate:
        img = img.rotate(rotate, resample=Image.BICUBIC, expand=False)
    ox, oy = PAD + shot[0], PAD + shot[1]
    img = img.crop((ox, oy, ox + W, oy + H))
    a = np.asarray(img, dtype=float)
    a += rng.normal(0, 4.0, a.shape)
    yy, xx = np.mgrid[0:H, 0:W]
    r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    a *= (1 - 0.18 * np.clip(r - 0.55, 0, 1))[..., None]
    return Image.fromarray(np.clip(a, 0, 255).astype("uint8"))


def canvas():
    return Image.new("RGBA", (W + 2 * PAD, H + 2 * PAD), (0, 0, 0, 255))


# --- scene 1: storm drain -----------------------------------------------------------------------------------

def drain(site: int, state: str, shot=(0, 0), rotate=0.0, light=1.0) -> Image.Image:
    geo = np.random.default_rng(100 + site)       # layout shared by before/after at one site
    rng = np.random.default_rng(zlib.crc32(repr((site, state, shot)).encode()))
    img = canvas()
    w, h = img.size
    hz = int(geo.uniform(430, 480))
    vx = w / 2 + geo.uniform(-160, 160)
    sky(img, geo, hz)
    buildings(img, geo, hz + 6)
    treeline(img, geo, hz + 8, color=(70, 98, 62), height=40)
    # banks
    fill(img, rng, [(0, hz), (w, hz), (w, h), (0, h)], (118, 128, 84), amp=14, blur=1.2, coarse=7)
    # walkway strips along the drain
    lw, rw = geo.uniform(0.30, 0.36), geo.uniform(0.64, 0.70)
    def edge(frac, y):
        return vx + (frac * w - vx) * depth(y, hz, h)
    walk = 0.10
    fill(img, rng, [(vx - 8, hz + 4), (vx - 2, hz + 4), (edge(lw, h), h), (edge(lw - walk, h), h)],
         (150, 146, 138), amp=12, blur=1.0)
    fill(img, rng, [(vx + 2, hz + 4), (vx + 8, hz + 4), (edge(rw + walk, h), h), (edge(rw, h), h)],
         (150, 146, 138), amp=12, blur=1.0)
    # concrete channel walls + water
    fill(img, rng, [(vx - 2, hz + 4), (vx + 2, hz + 4), (edge(rw, h), h), (edge(lw, h), h)],
         (128, 124, 116) if state == "before" else (152, 150, 144), amp=14, blur=1.0, coarse=14)
    wl, wr = lw + 0.07, rw - 0.07
    water_poly = [(vx - 1, hz + 6), (vx + 1, hz + 6), (edge(wr, h), h), (edge(wl, h), h)]
    if state == "before":
        fill(img, rng, water_poly, (70, 74, 46), amp=16, blur=3, coarse=20)
    else:
        fill(img, rng, water_poly, (96, 126, 138), amp=10, blur=4, coarse=10)
    d = ImageDraw.Draw(img, "RGBA")
    # stain line on walls
    if state == "before":
        for side in (lw + 0.035, rw - 0.035):
            d.line([(vx, hz + 5), (edge(side, h), h)], fill=(58, 60, 38, 170), width=10)
    else:  # reflections
        for _ in range(60):
            y = rng.uniform(hz + 30, h)
            k = depth(y, hz, h)
            cx = vx + (w / 2 - vx) * k + rng.uniform(-0.1, 0.1) * w * k
            d.line([(cx - 40 * k, y), (cx + 40 * k, y)], fill=(210, 226, 232, 90), width=max(1, int(3 * k)))
    # silt, weeds and trash (before) / removed-silt sacks on the bank (after)
    if state == "before":
        for _ in range(420):
            y = hz + (h - hz) * rng.uniform(0.04, 1) ** 0.8
            k = depth(y, hz, h)
            x = edge(rng.uniform(wl, wr), y)
            s = rng.uniform(8, 26) * k
            kind = rng.random()
            if kind < 0.35:    # plastic bottle
                c = [(170, 210, 225), (60, 150, 80), (230, 230, 230), (200, 60, 50)][int(rng.integers(4))]
                a = rng.uniform(0, math.pi)
                dx, dy = math.cos(a) * s * 1.6, math.sin(a) * s * 0.5
                d.line([(x - dx, y - dy), (x + dx, y + dy)], fill=c + (235,), width=max(2, int(s * 0.7)))
            elif kind < 0.65:  # plastic bag
                c = [(235, 235, 240), (60, 90, 170), (30, 30, 30), (210, 70, 140)][int(rng.integers(4))]
                d.ellipse([x - s * 1.3, y - s * 0.6, x + s * 1.3, y + s * 0.6], fill=c + (225,))
            elif kind < 0.85:  # silt mound
                d.ellipse([x - s * 2, y - s * 0.5, x + s * 2, y + s * 0.5], fill=(92, 80, 52, 200))
            else:              # weeds
                for _ in range(5):
                    d.line([(x, y), (x + rng.uniform(-1, 1) * s, y - rng.uniform(1, 2.5) * s)],
                           fill=(70, 120, 50, 230), width=max(1, int(s * 0.2)))
    else:
        for i in range(int(geo.integers(5, 9))):
            y = h - 120 - i * 38 + rng.uniform(-6, 6)
            k = depth(y, hz, h)
            x = edge(lw - walk * 0.5, y) + rng.uniform(-8, 8)
            s = 34 * k
            d.rounded_rectangle([x - s * 1.4, y - s, x + s * 1.4, y + s * 0.4], radius=int(s * 0.5),
                                fill=(214, 204, 170, 255), outline=(150, 140, 110, 255), width=2)
    return finish(ImageEnhance.Brightness(img.convert("RGB")).enhance(light).convert("RGBA"), rng, shot, rotate)


# --- scene 2: lakeside tree planting ------------------------------------------------------------------------

def lakeside(site: int, state: str, shot=(0, 0), rotate=0.0, growth=1.0) -> Image.Image:
    geo = np.random.default_rng(200 + site)
    rng = np.random.default_rng(zlib.crc32(repr((site, state, shot, growth)).encode()))
    img = canvas()
    w, h = img.size
    hz = int(geo.uniform(420, 470))
    sky(img, geo, hz, top=(126, 172, 220))
    treeline(img, geo, hz, color=(52, 84, 60), height=60)
    shore = hz + int(geo.uniform(90, 130))
    fill(img, rng, [(0, hz), (w, hz), (w, shore), (0, shore)], (92, 134, 168), amp=8, blur=6)
    d = ImageDraw.Draw(img, "RGBA")
    for _ in range(90):
        y = rng.uniform(hz + 4, shore - 4)
        x = rng.uniform(0, w)
        d.line([(x, y), (x + rng.uniform(20, 70), y)], fill=(200, 222, 236, 100), width=2)
    fill(img, rng, [(0, shore - 6), (w, shore - 6), (w, shore + 14), (0, shore + 14)], (160, 150, 118), amp=10)
    soil = (128, 96, 66) if state == "before" else (116, 90, 62)
    fill(img, rng, [(0, shore + 10), (w, shore + 10), (w, h), (0, h)], soil, amp=16, blur=1.0, coarse=9)
    rows, cols = 5, 7
    vx = w / 2 + geo.uniform(-120, 120)
    if state == "before":
        for _ in range(260):   # clods and dry grass
            y = shore + 20 + (h - shore - 20) * rng.random() ** 0.9
            k = depth(y, shore, h) + 0.15
            x = rng.uniform(0, w)
            if rng.random() < 0.6:
                s = rng.uniform(4, 12) * k
                d.ellipse([x - s, y - s * 0.6, x + s, y + s * 0.6], fill=(96, 70, 46, 200))
            else:
                for _ in range(6):
                    d.line([(x, y), (x + rng.uniform(-1, 1) * 14 * k, y - rng.uniform(8, 22) * k)],
                           fill=(176, 160, 96, 220), width=max(1, int(2 * k)))
        return finish(img, rng, shot, rotate)
    # planted: rows of saplings in mulch basins with stakes
    for _ in range(int(300 * min(1.0, growth))):   # new grass
        y = shore + 20 + (h - shore - 20) * rng.random()
        k = depth(y, shore, h) + 0.15
        x = rng.uniform(0, w)
        d.line([(x, y), (x + rng.uniform(-4, 4) * k, y - rng.uniform(6, 16) * k * growth)],
               fill=(96, 150, 70, 220), width=max(1, int(2 * k)))
    for r in range(rows, 0, -1):
        t = r / rows
        y = shore + 30 + (h - shore - 90) * t ** 1.3
        k = depth(y, shore, h) + 0.12
        for c in range(cols):
            fx = (c + 0.5) / cols
            x = vx + (fx * w - vx) * (0.35 + 0.9 * k) + geo.uniform(-10, 10) * k
            bw = 95 * k
            d.ellipse([x - bw, y - bw * 0.3, x + bw, y + bw * 0.3], fill=(72, 52, 36, 255))
            d.line([(x + bw * 0.5, y), (x + bw * 0.5, y - 230 * k)], fill=(170, 130, 80, 255),
                   width=max(2, int(6 * k)))
            th = 190 * k * growth
            d.line([(x, y), (x, y - th)], fill=(96, 72, 48, 255), width=max(2, int(5 * k)))
            for _ in range(int(10 * growth) + 4):
                lx = x + rng.uniform(-45, 45) * k * growth
                ly = y - th + rng.uniform(-45, 35) * k * growth
                s = rng.uniform(16, 28) * k
                d.ellipse([lx - s, ly - s * 0.6, lx + s, ly + s * 0.6],
                          fill=(int(rng.uniform(60, 90)), int(rng.uniform(130, 170)), 60, 240))
    return finish(img, rng, shot, rotate)


# --- scene 3: park litter clean-up --------------------------------------------------------------------------

def park(site: int, state: str, shot=(0, 0), rotate=0.0) -> Image.Image:
    geo = np.random.default_rng(300 + site)
    rng = np.random.default_rng(zlib.crc32(repr((site, state, shot)).encode()))
    img = canvas()
    w, h = img.size
    hz = int(geo.uniform(470, 520))
    sky(img, geo, hz)
    treeline(img, geo, hz, color=(58, 96, 56), height=110, step=40)
    fill(img, rng, [(0, hz), (w, hz), (w, h), (0, h)], (104, 148, 72), amp=14, blur=1.0, coarse=6)
    vx = w / 2 + geo.uniform(-200, 200)
    fill(img, rng, [(vx - 10, hz), (vx + 10, hz), (w * 0.72, h), (w * 0.42, h)], (186, 172, 146), amp=12)
    d = ImageDraw.Draw(img, "RGBA")
    # bench + bin
    by = hz + (h - hz) * 0.5
    k = depth(by, hz, h) * 2.2
    bx = w * geo.uniform(0.12, 0.25)
    d.rectangle([bx, by - 70 * k, bx + 260 * k, by - 55 * k], fill=(120, 80, 50, 255))
    d.rectangle([bx, by - 110 * k, bx + 260 * k, by - 90 * k], fill=(120, 80, 50, 255))
    for lx in (bx + 15 * k, bx + 240 * k):
        d.rectangle([lx, by - 110 * k, lx + 10 * k, by], fill=(60, 60, 60, 255))
    cx = w * geo.uniform(0.78, 0.86)
    d.rectangle([cx, by - 120 * k, cx + 80 * k, by], fill=(46, 104, 70, 255))
    d.rectangle([cx - 6 * k, by - 128 * k, cx + 86 * k, by - 116 * k], fill=(36, 84, 56, 255))
    if state == "before":
        for _ in range(12):    # overflowing bin
            s = rng.uniform(10, 20) * k
            x, y = cx + rng.uniform(0, 80) * k, by - 128 * k - rng.uniform(0, 30) * k
            d.ellipse([x - s, y - s * 0.7, x + s, y + s * 0.7],
                      fill=[(240, 240, 240, 255), (40, 40, 40, 255), (210, 60, 60, 255)][int(rng.integers(3))])
        for _ in range(320):   # scattered litter
            y = hz + (h - hz) * rng.uniform(0.05, 1) ** 0.8
            kk = depth(y, hz, h)
            x = rng.uniform(0, w)
            s = rng.uniform(12, 28) * kk
            c = [(240, 240, 235), (220, 60, 50), (60, 110, 190), (240, 200, 60), (30, 30, 30)][int(rng.integers(5))]
            if rng.random() < 0.5:
                d.polygon([(x - s, y), (x, y - s * 0.6), (x + s * 1.2, y + s * 0.2), (x, y + s * 0.5)], fill=c + (235,))
            else:
                d.line([(x - s, y), (x + s, y - s * 0.3)], fill=c + (235,), width=max(2, int(s * 0.6)))
    return finish(img, rng, shot, rotate)


# --- fillers ------------------------------------------------------------------------------------------------

def nursery() -> Image.Image:
    rng = np.random.default_rng(401)
    img = canvas()
    w, h = img.size
    fill(img, rng, [(0, 0), (w, 0), (w, h), (0, h)], (132, 112, 84), amp=18, coarse=14)
    d = ImageDraw.Draw(img, "RGBA")
    for r in range(9):
        for c in range(12):
            x, y = 140 + c * 120 + rng.uniform(-4, 4), 120 + r * 120 + rng.uniform(-4, 4)
            d.ellipse([x - 44, y - 44, x + 44, y + 44], fill=(28, 28, 30, 255))
            d.ellipse([x - 36, y - 36, x + 36, y + 36], fill=(84, 62, 42, 255))
            for _ in range(7):
                a = rng.uniform(0, 2 * math.pi)
                lx, ly = x + math.cos(a) * 20, y + math.sin(a) * 20
                d.ellipse([lx - 16, ly - 9, lx + 16, ly + 9], fill=(70, int(rng.uniform(130, 170)), 60, 245))
    return finish(img, rng, (0, 0), 0)


def signboard() -> Image.Image:
    rng = np.random.default_rng(402)
    img = canvas()
    w, h = img.size
    hz = 560
    sky(img, rng, hz)
    buildings(img, rng, hz + 4)
    fill(img, rng, [(0, hz), (w, hz), (w, h), (0, h)], (150, 146, 138), amp=14, coarse=10)
    d = ImageDraw.Draw(img, "RGBA")
    for px in (w / 2 - 330, w / 2 + 310):
        d.rectangle([px, 520, px + 20, 1150], fill=(90, 90, 96, 255))
    d.rectangle([w / 2 - 380, 360, w / 2 + 380, 760], fill=(240, 236, 222, 255), outline=(40, 90, 60, 255), width=14)
    d.rectangle([w / 2 - 366, 374, w / 2 + 366, 470], fill=(40, 110, 70, 255))
    try:
        from PIL import ImageFont
        big, small = ImageFont.load_default(56), ImageFont.load_default(38)
    except Exception:
        big = small = None
    d.text((w / 2, 422), "WARD 12 DRAIN CLEANING DRIVE", fill=(255, 255, 255), font=big, anchor="mm")
    d.text((w / 2, 560), "Community clean-up in progress", fill=(40, 40, 40), font=small, anchor="mm")
    d.text((w / 2, 640), "SYNTHETIC DEMO IMAGE", fill=(190, 60, 40), font=small, anchor="mm")
    return finish(img, rng, (0, 0), 0)


def near_duplicate(src: Image.Image) -> Image.Image:
    """Same shot re-saved: slight crop, rescale and brightness change (tests the near-duplicate flag)."""
    im = src.crop((24, 18, W - 24, H - 18)).resize((W, H), Image.LANCZOS)
    return ImageEnhance.Brightness(im).enhance(1.04)


# --- manifest ---------------------------------------------------------------------------------------------

DRAIN, LAKE, PARK = "Drain Cleaning Ward 12", "Tree Planting Lakeside", "Park Clean-up Riverside"

# filename, project, captured_at, lat, lng, role, renderer, description (goes to SOURCES.md)
SHOTS = [
    ("drain_before_01.jpg", DRAIN, "2026-05-10 09:15", 12.971600, 77.594600, "before",
     lambda: drain(1, "before"), "Concrete storm drain, site 1, clogged with plastic waste, silt and weeds"),
    ("drain_after_01.jpg", DRAIN, "2026-05-24 10:05", 12.971650, 77.594640, "after",
     lambda: drain(1, "after", shot=(18, -12), rotate=0.6), "Same drain, site 1, cleared; removed silt in sacks on the bank"),
    ("drain_after_01_copy.jpg", DRAIN, "2026-05-24 10:06", 12.971650, 77.594640, "duplicate",
     None, "Near-duplicate of drain_after_01.jpg (cropped, rescaled, brightened)"),
    ("drain_before_02.jpg", DRAIN, "2026-05-11 08:40", 12.974900, 77.598300, "before",
     lambda: drain(2, "before", light=0.92), "Concrete storm drain, site 2, blocked with plastic waste"),
    ("drain_after_02.jpg", DRAIN, "2026-05-26 09:20", 12.974930, 77.598270, "after",
     lambda: drain(2, "after", shot=(-20, 10), rotate=-0.5), "Same drain, site 2, cleared and flowing"),
    ("drain_signboard.jpg", DRAIN, "2026-05-10 08:55", 12.971420, 77.594380, "filler",
     signboard, "Roadside project signboard for the fictional drive"),
    ("lakeside_before_01.jpg", LAKE, "2026-06-02 07:50", 12.956200, 77.612400, "before",
     lambda: lakeside(1, "before"), "Bare, dry plot on a lake shore before planting"),
    ("lakeside_after_01.jpg", LAKE, "2026-07-14 08:10", 12.956230, 77.612440, "after",
     lambda: lakeside(1, "after", shot=(14, 8), rotate=0.4, growth=0.7),
     "Same plot, six weeks later: rows of staked saplings in mulch basins"),
    ("lakeside_after_01_late.jpg", LAKE, "2026-09-01 08:30", 12.956210, 77.612420, "after",
     lambda: lakeside(1, "after", shot=(-10, 4), growth=1.25), "Same plot, three months later: saplings taller, grass returning"),
    ("lakeside_before_02.jpg", LAKE, "2026-06-03 08:05", 12.958900, 77.615100, "before",
     lambda: lakeside(2, "before"), "Second bare lake-shore plot before planting"),
    ("lakeside_after_02.jpg", LAKE, "2026-07-15 07:45", 12.958880, 77.615130, "after",
     lambda: lakeside(2, "after", shot=(-16, -6), growth=0.8), "Second plot after planting"),
    ("lakeside_nursery.jpg", LAKE, "", "", "", "filler",
     nursery, "Top-down view of sapling nursery trays (no date or GPS on purpose)"),
    ("park_before_01.jpg", PARK, "2026-08-03 16:30", 12.989100, 77.571800, "before",
     lambda: park(1, "before"), "Park lawn with scattered litter and an overflowing bin"),
    ("park_after_01.jpg", PARK, "2026-08-03 18:40", 12.989120, 77.571830, "after",
     lambda: park(1, "after", shot=(12, -8), rotate=0.3), "Same lawn after the clean-up the same evening"),
    ("park_after_01_offsite.jpg", PARK, "2026-08-04 09:00", "", "", "after",
     lambda: park(1, "after", shot=(-24, 14)), "Same lawn next morning (GPS missing on purpose)"),
]

PROJECTS = [
    {"id": "drain-cleaning-ward-12", "name": "Drain Cleaning, Ward 12 (synthetic)",
     "description": "Synthetic demo project: computer-generated images of a fictional drain-cleaning drive.",
     "location_name": "Fictional location"},
    {"id": "tree-planting-lakeside", "name": "Tree Planting, Lakeside (synthetic)",
     "description": "Synthetic demo project: computer-generated images of a fictional lake-shore planting drive.",
     "location_name": "Fictional location"},
    {"id": "park-clean-up-riverside", "name": "Park Clean-up, Riverside (synthetic)",
     "description": "Synthetic demo project: computer-generated images of a fictional park litter clean-up.",
     "location_name": "Fictional location"},
]


def write_sources(rows) -> None:
    path = SEED / "SOURCES.md"
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    by_file = {r[0]: r for r in rows}
    out = []
    for line in lines:  # fill _TODO_ rows the seeding script may have appended
        cells = [c.strip() for c in line.strip("|").split("|")]
        if line.startswith("| ") and cells[0] in by_file and "_TODO_" in line:
            f = by_file.pop(cells[0])
            line = f"| {f[0]} | {GENERATOR} | {f[7]} |"
        elif line.startswith("| ") and cells[0] in by_file:
            by_file.pop(cells[0])
        out.append(line)
    out += [f"| {f[0]} | {GENERATOR} | {f[7]} |" for f in by_file.values()]
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="overwrite existing metadata.csv and projects.json")
    args = ap.parse_args()
    IMAGES.mkdir(parents=True, exist_ok=True)

    rendered = {}
    for fname, *_, render, _desc in SHOTS:
        if render is None:
            continue
        rendered[fname] = render()
        rendered[fname].save(IMAGES / fname, "JPEG", quality=88, optimize=True)
        print(f"  wrote seed/images/{fname}")
    near_duplicate(rendered["drain_after_01.jpg"]).save(IMAGES / "drain_after_01_copy.jpg", "JPEG", quality=80)
    print("  wrote seed/images/drain_after_01_copy.jpg")

    meta, pj = SEED / "metadata.csv", SEED / "projects.json"
    for p in (meta, pj):
        if p.exists() and not args.force:
            sys.exit(f"{p} exists; pass --force to overwrite")
    with meta.open("w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(["filename", "project", "captured_at", "lat", "lng", "role", "synthetic"])
        for fname, project, cap, lat, lng, role, *_ in SHOTS:
            fmt = (lambda v: f"{v:.6f}" if isinstance(v, float) else v)
            wr.writerow([fname, project, cap, fmt(lat), fmt(lng), role, "true"])
    pj.write_text(json.dumps(PROJECTS, indent=2) + "\n", encoding="utf-8")
    write_sources(SHOTS)
    print(f"Wrote {meta.relative_to(ROOT)}, {pj.relative_to(ROOT)} and updated seed/SOURCES.md")


if __name__ == "__main__":
    main()
