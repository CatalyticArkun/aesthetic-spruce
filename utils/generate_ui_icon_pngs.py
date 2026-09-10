#!/usr/bin/env python3
"""Rasterise the SVG icons the app draws at runtime into white-on-transparent PNGs.

Replaces the TÖVE (libTove.so) runtime SVG renderer: on device the app loads these PNGs and
tints them with love.graphics.setColor. Output mirrors the source tree:
  assets/icons/<set>/<name>.svg  ->  assets/icons/png/<set>/<name>.png

Requires: pip install cairosvg   (host only; nothing is rendered on device)
Usage:    utils/generate_ui_icon_pngs.py [--size 128] [--check]
"""
import argparse, os, re, sys
import cairosvg

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
SETS = ["lucide/ui", "lucide/glyph", "kenney_input_prompts", "material_symbols"]

def render(src, dst, size):
    svg = open(src, encoding="utf-8").read()
    # Lucide uses stroke="currentColor"; Material uses fill="#E3E3E3" or similar. Force white so
    # the PNG is a pure alpha mask that setColor() can tint.
    svg = svg.replace("currentColor", "#ffffff")
    svg = re.sub(r'fill="#[0-9a-fA-F]{3,8}"', 'fill="#ffffff"', svg)
    svg = re.sub(r'stroke="#[0-9a-fA-F]{3,8}"', 'stroke="#ffffff"', svg)
    # Kenney/Fluent use CSS style attributes and named colours
    svg = re.sub(r'fill:\s*#[0-9a-fA-F]{3,8}', 'fill:#ffffff', svg)
    svg = re.sub(r'stroke:\s*#[0-9a-fA-F]{3,8}', 'stroke:#ffffff', svg)
    svg = re.sub(r'fill="(black|white|gray|grey)"', 'fill="#ffffff"', svg)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    cairosvg.svg2png(bytestring=svg.encode("utf-8"), write_to=dst, output_width=size, output_height=size)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=int, default=128)
    ap.add_argument("--check", action="store_true", help="exit 1 if any PNG is missing or stale")
    a = ap.parse_args()
    missing, done = [], 0
    for s in SETS:
        sdir = os.path.join(ROOT, "assets", "icons", s)
        for name in sorted(os.listdir(sdir)):
            if not name.endswith(".svg"):
                continue
            src = os.path.join(sdir, name)
            dst = os.path.join(ROOT, "assets", "icons", "png", s, name[:-4] + ".png")
            stale = not os.path.exists(dst) or os.path.getmtime(dst) < os.path.getmtime(src)
            if a.check:
                if stale: missing.append(dst)
                continue
            if stale:
                render(src, dst, a.size); done += 1
    if a.check:
        print("stale/missing:", len(missing)); sys.exit(1 if missing else 0)
    print("rendered", done, "icons at", a.size, "px")

if __name__ == "__main__":
    main()
