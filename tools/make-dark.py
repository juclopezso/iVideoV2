#!/usr/bin/env python3
"""Generate the dark-mode bitmap twins for the iCamVideo theme.

Reads the light-mode 24-bit BMPs under wps/iCamVideo/ and writes recolored
copies under wps/iCamVideo-Dark/ (and the standalone menu backdrop under
backdrops/), using the *same filenames* — Rockbox resolves %xl/%X paths
relative to the skin file's own basename (wps/<skin>/), so iCamVideo-Dark.wps
picks these up automatically with no path edits in the layout files.

Transform: convert each pixel RGB -> HLS, invert lightness (L' = 1 - L),
convert back. This keeps hue and saturation, so white plaques go near-black,
black glyphs go white, and colored elements (e.g. the blue battery icon)
darken without shifting hue. Rockbox's FF00FF transparency key is passed
through untouched. A few bitmaps are already legible on a dark background
(blue progress-bar/volumebar gradients, the yellow radio icon) and are
copied verbatim instead of transformed.

Re-run this any time a light-mode bitmap in wps/iCamVideo/ changes.
"""
import colorsys
import shutil
import struct
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC_DIR = REPO / "wps" / "iCamVideo"
DST_DIR = REPO / "wps" / "iCamVideo-Dark"

TRANSPARENT_KEY = (255, 0, 255)

# Bitmaps that read fine on a dark background as-is (colored gradients /
# already-bright icons) — copied byte-for-byte, no transform.
PASSTHROUGH = {
    "Progress Bar.bmp",
    "Volumebar.bmp",
    "Radio Icon.bmp",
}


def invert_lightness(r, g, b):
    if (r, g, b) == TRANSPARENT_KEY:
        return r, g, b
    h, l, s = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)
    r2, g2, b2 = colorsys.hls_to_rgb(h, 1.0 - l, s)
    return (
        max(0, min(255, round(r2 * 255))),
        max(0, min(255, round(g2 * 255))),
        max(0, min(255, round(b2 * 255))),
    )


def transform_bmp(data: bytes) -> bytes:
    data = bytearray(data)
    pixel_offset = struct.unpack_from("<I", data, 10)[0]
    width, height = struct.unpack_from("<ii", data, 18)
    bpp = struct.unpack_from("<H", data, 28)[0]
    if bpp != 24:
        raise ValueError(f"expected 24-bit BMP, got {bpp}-bit")
    abs_height = abs(height)
    stride = ((width * 3) + 3) // 4 * 4
    for y in range(abs_height):
        row_start = pixel_offset + y * stride
        for x in range(width):
            i = row_start + x * 3
            b, g, r = data[i], data[i + 1], data[i + 2]
            r2, g2, b2 = invert_lightness(r, g, b)
            data[i], data[i + 1], data[i + 2] = b2, g2, r2
    return bytes(data)


def process(src: Path, dst: Path):
    raw = src.read_bytes()
    if src.name in PASSTHROUGH:
        dst.write_bytes(raw)
        print(f"  copy      {src.name}")
    else:
        dst.write_bytes(transform_bmp(raw))
        print(f"  transform {src.name}")


def main():
    DST_DIR.mkdir(parents=True, exist_ok=True)
    print(f"{SRC_DIR} -> {DST_DIR}")
    for src in sorted(SRC_DIR.glob("*.bmp")):
        process(src, DST_DIR / src.name)

    menu_backdrop = REPO / "backdrops" / "iCamVideo_Backdrop.bmp"
    menu_backdrop_dark = REPO / "backdrops" / "iCamVideo_Backdrop_Dark.bmp"
    print(f"{menu_backdrop} -> {menu_backdrop_dark}")
    menu_backdrop_dark.write_bytes(transform_bmp(menu_backdrop.read_bytes()))
    print("  transform iCamVideo_Backdrop.bmp")


if __name__ == "__main__":
    main()
