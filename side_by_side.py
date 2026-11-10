#!/usr/bin/env python3
"""Place two timeline images next to each other in one image.

The images are copied pixel for pixel, with no rescaling, so the result is as
sharp as the originals. If they differ in height they are aligned at the top.

An image can be given as a path, or relative to output/, so
click_timeline/P02.png finds output/click_timeline/P02.png.

Output: output/side_by_side/<left>__<right>.png, and for the default images and
title a copy in output/figures_in_article/  (needs matplotlib)

Usage:
    python3 side_by_side.py     # query_click_timeline/P04.png, click_timeline/P02.png
    python3 side_by_side.py click_timeline/P02.png click_timeline/P08.png
    python3 side_by_side.py LEFT RIGHT --out figures/comparison.png
    python3 side_by_side.py LEFT RIGHT --gap 120
    python3 side_by_side.py LEFT RIGHT --title "Figure 3: Another comparison"
    python3 side_by_side.py LEFT RIGHT --title ""     # no title
"""

import argparse
import os
import sys

from grouped_table import copy_to_article

OUTPUT_ROOT = "output"
DEFAULT_IMAGES = ["query_click_timeline/P04.png", "click_timeline/P02.png"]
DEFAULT_DPI = (300, 300)
DEFAULT_TITLE = "Figure 2: Comparison of two participants' navigation strategies"

# Title styling, in points, matching the titled tables from grouped_table.py.
TITLE_SIZE = 11
TITLE_MARGIN = 4  # above the title
TITLE_PAD = 6     # between the title and the images


def resolve(path):
    """Return the existing file ``path`` refers to, or None."""
    for candidate in (path, os.path.join(OUTPUT_ROOT, path)):
        if os.path.isfile(candidate):
            return candidate
    return None


def default_out(left, right):
    """Name the output after both inputs, including their timeline folders."""
    def label(path):
        folder = os.path.basename(os.path.dirname(path))
        stem = os.path.splitext(os.path.basename(path))[0]
        return f"{folder}_{stem}" if folder else stem

    return os.path.join(OUTPUT_ROOT, "side_by_side",
                        f"{label(left)}__{label(right)}.png")


def title_strip(title, width, dpi):
    """Return a white strip ``width`` pixels wide with ``title`` centred on it."""
    from matplotlib import font_manager
    from PIL import Image, ImageDraw, ImageFont

    def pixels(points):
        return round(points * dpi / 72)

    font_path = font_manager.findfont(
        font_manager.FontProperties(weight="bold"))
    font = ImageFont.truetype(font_path, pixels(TITLE_SIZE))
    _, top, _, bottom = font.getbbox(title, anchor="mt")
    margin = pixels(TITLE_MARGIN)

    strip = Image.new("RGB",
                      (width, margin + (bottom - top) + pixels(TITLE_PAD)),
                      "white")
    ImageDraw.Draw(strip).text((width // 2, margin - top), title, font=font,
                               fill="black", anchor="mt")
    return strip


def combine(left_path, right_path, out_path, gap, title):
    from PIL import Image

    def load(path):
        """Open an image flattened onto white; return (image, dpi or None)."""
        with Image.open(path) as source:
            rgba = source.convert("RGBA")
            dpi = source.info.get("dpi")
        flat = Image.new("RGB", rgba.size, "white")
        flat.paste(rgba, mask=rgba.getchannel("A"))
        return flat, dpi

    left, left_dpi = load(left_path)
    right, _ = load(right_path)

    dpi = left_dpi or DEFAULT_DPI
    width = left.width + gap + right.width
    strip = title_strip(title, width, dpi[0]) if title else None
    top = strip.height if strip else 0

    canvas = Image.new("RGB",
                       (width, top + max(left.height, right.height)),
                       "white")
    if strip:
        canvas.paste(strip, (0, 0))
    canvas.paste(left, (0, top))
    canvas.paste(right, (left.width + gap, top))

    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    canvas.save(out_path, dpi=dpi)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("images", nargs="*", default=DEFAULT_IMAGES,
                    metavar="IMAGE",
                    help="the left and right image (default: "
                         + " and ".join(DEFAULT_IMAGES) + ")")
    ap.add_argument("--out",
                    help="output file (default: "
                         "output/side_by_side/<left>__<right>.png)")
    ap.add_argument("--gap", type=int, default=60,
                    help="pixels between the images (default: 60)")
    ap.add_argument("--title", default=DEFAULT_TITLE,
                    help="title above the images; pass \"\" for none "
                         f"(default: {DEFAULT_TITLE})")
    args = ap.parse_args()

    if len(args.images) != 2:
        ap.error(f"expected 2 images, got {len(args.images)}")
    if args.gap < 0:
        ap.error("--gap cannot be negative")

    paths = []
    for image in args.images:
        path = resolve(image)
        if path is None:
            ap.error(f"image not found: {image}")
        paths.append(path)
    left, right = paths

    out_path = args.out or default_out(left, right)
    try:
        combine(left, right, out_path, args.gap, args.title)
    except ImportError:
        print("matplotlib is not installed (see README Setup)",
              file=sys.stderr)
        sys.exit(1)
    print(f"Wrote: {out_path}")

    # Only the article's own pair goes to the article folder, so comparing two
    # other timelines can never overwrite it.
    if (not args.out and args.images == DEFAULT_IMAGES
            and args.title == DEFAULT_TITLE):
        print(f"Wrote: {copy_to_article(out_path, DEFAULT_TITLE)}")


if __name__ == "__main__":
    main()
