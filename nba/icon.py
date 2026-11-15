"""Draws the home-screen icon (a basketball on a dark tile) as PNG, no extra libraries."""
import math
import struct
import zlib
from pathlib import Path

BG = (10, 14, 22)
BALL = (255, 122, 26)
SEAM = (24, 16, 10)


def _inside(x, y, s):
    """Color at point (x, y) in a unit square."""
    cx = cy = 0.5
    r = 0.36
    dx, dy = x - cx, y - cy
    d = math.hypot(dx, dy)
    if d > r:
        return BG
    w = 0.018
    seams = [
        abs(dx),                                   # vertical seam
        abs(dy),                                   # horizontal seam
        abs(math.hypot(x - (cx - 0.47), y - cy) - 0.34),   # left curve
        abs(math.hypot(x - (cx + 0.47), y - cy) - 0.34),   # right curve
    ]
    if min(seams) < w or d > r - w * 0.9:
        return SEAM
    shade = 1 - 0.28 * max(0.0, (dx + dy) / (r * 1.4))
    return tuple(min(255, int(c * shade)) for c in BALL)


def make_png(size: int, path: Path, ss: int = 3):
    rows = []
    for py in range(size):
        row = bytearray([0])
        for px in range(size):
            acc = [0, 0, 0]
            for sy in range(ss):
                for sx in range(ss):
                    c = _inside((px + (sx + .5) / ss) / size, (py + (sy + .5) / ss) / size, size)
                    acc[0] += c[0]; acc[1] += c[1]; acc[2] += c[2]
            n = ss * ss
            row += bytes((acc[0] // n, acc[1] // n, acc[2] // n))
        rows.append(bytes(row))
    raw = zlib.compress(b"".join(rows), 9)

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", raw) + chunk(b"IEND", b""))
    path.write_bytes(png)


def ensure_icons(static_dir: Path):
    for size in (180, 192, 512):
        p = static_dir / f"icon-{size}.png"
        if not p.exists():
            make_png(size, p)
