#!/usr/bin/env python3
"""Convince the AI Judge to Visit Your House: A Letter in One Image.

Pure-stdlib program (the grading sandbox is plain python:3.13-slim: no Pillow,
no network). It draws a warm illustrated scene with its own tiny software
rasterizer, pastes the letter text (assets/letter_text.png, rendered at build
time by tools/render_text.py from the same wording) onto the paper, and writes
the finished invitation to $MAKEFUN_OUTPUT_DIR/entry.png (default /output).

Deterministic: fixed seed, no time, no randomness outside the seeded speckle.
Output: one 1024x1024 PNG, well under the 1 MiB gate.
"""
import math
import os
import random
import struct
import sys
import zlib

W, H = 1024, 1024

# ---------------------------------------------------------------- canvas
class Canvas:
    def __init__(self, w, h, bg=(255, 255, 255)):
        self.w, self.h = w, h
        self.px = bytearray(w * h * 3)
        self.fill_rect(0, 0, w, h, bg)

    def _idx(self, x, y):
        return (y * self.w + x) * 3

    def blend(self, x, y, r, g, b, a=255):
        if x < 0 or y < 0 or x >= self.w or y >= self.h:
            return
        i = self._idx(x, y)
        if a >= 255:
            self.px[i], self.px[i + 1], self.px[i + 2] = r, g, b
        elif a > 0:
            ia = 255 - a
            self.px[i] = (r * a + self.px[i] * ia) // 255
            self.px[i + 1] = (g * a + self.px[i + 1] * ia) // 255
            self.px[i + 2] = (b * a + self.px[i + 2] * ia) // 255

    def fill_rect(self, x0, y0, x1, y1, color, alpha=255):
        r, g, b = color
        x0 = max(0, x0); y0 = max(0, y0)
        x1 = min(self.w, x1); y1 = min(self.h, y1)
        if x1 <= x0 or y1 <= y0:
            return
        if alpha >= 255:
            row = bytes((r, g, b)) * (x1 - x0)
            for y in range(y0, y1):
                i = self._idx(x0, y)
                self.px[i:i + len(row)] = row
        else:
            for y in range(y0, y1):
                for x in range(x0, x1):
                    self.blend(x, y, r, g, b, alpha)

    def vgrad(self, x0, y0, x1, y1, top, bottom):
        for y in range(y0, y1):
            t = (y - y0) / max(1, (y1 - y0 - 1))
            c = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
            self.fill_rect(x0, y, x1, y + 1, c)

    def ellipse(self, cx, cy, rx, ry, color, alpha=255):
        for dy in range(-ry, ry + 1):
            t = 1.0 - (dy * dy) / float(ry * ry)
            if t < 0:
                continue
            dx = int(rx * math.sqrt(t))
            self.fill_rect(cx - dx, cy + dy, cx + dx + 1, cy + dy + 1, color, alpha)

    def circle(self, cx, cy, r, color, alpha=255):
        self.ellipse(cx, cy, r, r, color, alpha)

    def polygon(self, pts, color, alpha=255):
        # Scanline fill of a simple polygon.
        ys = [p[1] for p in pts]
        for y in range(max(0, min(ys)), min(self.h, max(ys) + 1)):
            xs = []
            n = len(pts)
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                if (y0 <= y < y1) or (y1 <= y < y0):
                    t = (y - y0) / (y1 - y0)
                    xs.append(x0 + t * (x1 - x0))
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                self.fill_rect(int(xs[i]), y, int(xs[i + 1]) + 1, y + 1, color, alpha)

    def thick_polyline(self, pts, width, color, alpha=255):
        # Stamp circles along the path: smooth joints, rounded caps.
        rad = max(1, width // 2)
        for i in range(len(pts) - 1):
            x0, y0 = pts[i]
            x1, y1 = pts[i + 1]
            steps = max(1, int(math.hypot(x1 - x0, y1 - y0)))
            for s in range(steps + 1):
                t = s / steps
                self.circle(int(x0 + (x1 - x0) * t), int(y0 + (y1 - y0) * t),
                            rad, color, alpha)

    def line(self, x0, y0, x1, y1, color, width=1, alpha=255):
        self.thick_polyline([(x0, y0), (x1, y1)], width, color, alpha)

    def sine(self, x0, x1, y0, y1, amp, waves, width, color, alpha=255):
        pts = []
        steps = 60
        for s in range(steps + 1):
            t = s / steps
            x = x0 + (x1 - x0) * t
            y = y0 + (y1 - y0) * t + amp * math.sin(t * waves * 2 * math.pi)
            pts.append((int(x), int(y)))
        self.thick_polyline(pts, width, color, alpha)


# ---------------------------------------------------------------- PNG decode (asset) / encode (output)
def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def decode_png(path):
    """Decode an 8-bit non-interlaced RGB/RGBA PNG -> (w, h, RGBA bytearray)."""
    data = open(path, "rb").read()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    pos = 8
    w = h = None
    bit_depth = color_type = None
    idat = bytearray()
    while pos < len(data):
        (ln,) = struct.unpack(">I", data[pos:pos + 4])
        ctype = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + ln]
        if ctype == b"IHDR":
            w, h, bit_depth, color_type, comp, filt, inter = struct.unpack(">IIBBBBB", chunk)
            assert bit_depth == 8 and inter == 0, "need 8-bit non-interlaced"
            assert color_type in (2, 6), "need RGB or RGBA"
        elif ctype == b"IDAT":
            idat += chunk
        elif ctype == b"IEND":
            break
        pos += 12 + ln
    ch = 4 if color_type == 6 else 3
    raw = zlib.decompress(bytes(idat))
    stride = w * ch
    out = bytearray(w * h * 4)
    prev = bytearray(stride)
    p = 0
    for y in range(h):
        f = raw[p]; p += 1
        line = bytearray(raw[p:p + stride]); p += stride
        if f == 1:
            for i in range(ch, stride):
                line[i] = (line[i] + line[i - ch]) & 255
        elif f == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 255
        elif f == 3:
            for i in range(stride):
                a = line[i - ch] if i >= ch else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 255
        elif f == 4:
            for i in range(stride):
                a = line[i - ch] if i >= ch else 0
                b = prev[i]
                c = prev[i - ch] if i >= ch else 0
                line[i] = (line[i] + _paeth(a, b, c)) & 255
        for x in range(w):
            o = (y * w + x) * 4
            s = x * ch
            out[o:o + 3] = line[s:s + 3]
            out[o + 3] = line[s + 3] if ch == 4 else 255
        prev = line
    return w, h, out


def encode_png(rgb, w, h):
    """Encode RGB bytearray as PNG; try filter None and Up, keep the smaller."""
    def chunk(ctype, payload):
        c = struct.pack(">I", len(payload)) + ctype + payload
        return c + struct.pack(">I", zlib.crc32(ctype + payload) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    stride = w * 3
    best = None
    for filt in (0, 2):
        body = bytearray()
        prev = bytes(stride)
        for y in range(h):
            row = bytes(rgb[y * stride:(y + 1) * stride])
            if filt == 0:
                body.append(0)
                body += row
            else:
                body.append(2)
                body += bytes((a - b) & 255 for a, b in zip(row, prev))
                prev = row
        comp = zlib.compress(bytes(body), 9)
        if best is None or len(comp) < len(best):
            best = comp
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", best) + chunk(b"IEND", b""))


# ---------------------------------------------------------------- the scene
CREAM_TOP = (248, 233, 207)
CREAM_BOT = (241, 217, 180)
WOOD = (122, 74, 43)
WOOD_DARK = (94, 56, 32)
DESK = (156, 107, 67)
DESK_DARK = (126, 82, 51)
DESK_LIGHT = (181, 126, 82)
PAPER = (255, 253, 245)
INK = (59, 47, 47)
ROSE = (201, 123, 123)
ROSE_DARK = (168, 95, 95)
ROSE_LIGHT = (233, 184, 168)
LEAF = (94, 140, 90)
LEAF_DARK = (70, 110, 68)
TERRA = (201, 111, 74)
TEAL = (95, 138, 139)
SEAL = (176, 58, 46)


def draw_scene(c):
    rng = random.Random(7)

    # Wall with a gentle vertical gradient and a faint speckle.
    c.vgrad(0, 0, W, H, CREAM_TOP, CREAM_BOT)
    for _ in range(1400):
        x, y = rng.randrange(W), rng.randrange(H)
        c.blend(x, y, 190, 160, 120, rng.choice((10, 14, 18)))

    # ---- Window, top-left: a garden sunset -------------------------------
    wx0, wy0, wx1, wy1 = 40, 45, 290, 390
    c.fill_rect(wx0, wy0, wx1, wy1, WOOD)                       # frame
    c.vgrad(wx0 + 12, wy0 + 12, wx1 - 12, wy1 - 12,
            (255, 196, 107), (232, 106, 122))                  # sunset sky
    c.circle(105, 132, 36, (255, 224, 138))                    # low sun
    c.circle(105, 132, 24, (255, 238, 170))                    # sun core
    # garden hedge + flowers + a small tree
    c.fill_rect(wx0 + 12, 300, wx1 - 12, wy1 - 12, (94, 140, 90))
    c.ellipse(120, 300, 60, 22, (110, 158, 104))
    c.ellipse(225, 305, 55, 20, (84, 128, 82))
    for (fx, fy, fc) in [(90, 330, (255, 120, 140)), (150, 345, (255, 210, 90)),
                         (210, 330, (255, 255, 255)), (250, 350, (255, 120, 140)),
                         (120, 360, (255, 210, 90)), (185, 365, (255, 255, 255))]:
        c.circle(fx, fy, 5, fc)
    c.fill_rect(238, 250, 248, 305, (110, 80, 50))             # tree trunk
    c.circle(243, 235, 34, (88, 132, 84))
    c.circle(220, 250, 24, (100, 146, 94))
    c.circle(266, 250, 24, (80, 122, 76))
    # cross bars + sill
    c.fill_rect(158, wy0 + 12, 170, wy1 - 12, WOOD)
    c.fill_rect(wx0 + 12, 200, wx1 - 12, 212, WOOD)
    c.fill_rect(wx0 - 8, wy1 - 6, wx1 + 8, wy1 + 10, WOOD_DARK)
    # a small potted plant on the sill, left pane
    c.polygon([(72, 342), (118, 342), (112, 380), (78, 380)], TERRA)
    c.ellipse(82, 318, 12, 16, LEAF)
    c.ellipse(100, 310, 12, 18, LEAF_DARK)
    c.ellipse(112, 322, 10, 14, LEAF)

    # ---- Comfy armchair, bottom-left ------------------------------------
    c.ellipse(160, 985, 150, 26, (0, 0, 0), alpha=28)          # floor shadow
    c.fill_rect(58, 640, 262, 845, ROSE)                       # back
    c.ellipse(160, 640, 102, 26, ROSE)
    c.fill_rect(58, 640, 262, 668, ROSE_DARK)                  # back top shade
    c.fill_rect(30, 760, 72, 950, ROSE_DARK)                   # left arm
    c.fill_rect(248, 760, 290, 950, ROSE_DARK)                 # right arm
    c.ellipse(51, 760, 21, 12, ROSE_DARK)
    c.ellipse(269, 760, 21, 12, ROSE_DARK)
    c.fill_rect(45, 800, 275, 885, ROSE_LIGHT)                 # seat cushion
    c.fill_rect(45, 800, 275, 818, (240, 205, 190))            # cushion top
    c.fill_rect(60, 950, 78, 1000, WOOD_DARK)                  # legs
    c.fill_rect(242, 950, 260, 1000, WOOD_DARK)
    # a book left on the seat
    c.polygon([(130, 814), (215, 808), (219, 834), (134, 840)], TEAL)
    c.polygon([(134, 840), (219, 834), (219, 842), (134, 848)], (240, 240, 235))

    # ---- Wooden desk band -------------------------------------------------
    c.fill_rect(0, 880, W, H, DESK)
    c.fill_rect(0, 880, W, 886, DESK_LIGHT)
    for yy in (922, 966, 1006):
        c.fill_rect(0, yy, W, yy + 3, DESK_DARK)
    c.sine(60, 700, 940, 948, 4, 2, 2, DESK_DARK, alpha=90)
    c.sine(350, 1000, 985, 992, 4, 2, 2, DESK_DARK, alpha=90)

    # ---- The letter on the desk -------------------------------------------
    px0, py0, px1, py1 = 310, 100, 990, 900
    c.fill_rect(px0 + 12, py0 + 14, px1 + 12, py1 + 14, (0, 0, 0), alpha=46)  # shadow
    c.fill_rect(px0, py0, px1, py1, PAPER)
    c.fill_rect(px0, py0, px1, py1 + 3, (255, 255, 255))        # top edge light
    # faint ruled lines, like letter paper
    for yy in range(py0 + 88, py1 - 40, 42):
        c.fill_rect(px0 + 34, yy, px1 - 34, yy + 1, (238, 228, 210))

    # ---- Paste the letter text --------------------------------------------
    here = os.path.dirname(os.path.abspath(__file__))
    tw, th, rgba = decode_png(os.path.join(here, "assets", "letter_text.png"))
    tx, ty = 360, 142
    for y in range(th):
        for x in range(tw):
            o = (y * tw + x) * 4
            a = rgba[o + 3]
            if a:
                c.blend(tx + x, ty + y, rgba[o], rgba[o + 1], rgba[o + 2], a)

    # ---- Wax seal with a heart ---------------------------------------------
    sx, sy = 918, 828
    c.circle(sx, sy, 34, SEAL)
    c.circle(sx, sy, 28, (196, 74, 60))
    c.circle(sx - 8, sy - 6, 8, (255, 235, 220))
    c.circle(sx + 8, sy - 6, 8, (255, 235, 220))
    c.polygon([(sx - 15, sy - 2), (sx + 15, sy - 2), (sx, sy + 16)], (255, 235, 220))

    # ---- Teapot and cup on the desk, bottom-right --------------------------
    c.ellipse(878, 1000, 90, 14, (0, 0, 0), alpha=30)
    c.sine(838, 848, 905, 940, 5, 2, 4, (216, 207, 192))        # steam
    c.sine(872, 884, 900, 938, 5, 2, 4, (216, 207, 192))
    c.ellipse(872, 952, 56, 42, (253, 246, 227))                # pot body
    c.polygon([(820, 940), (846, 918), (852, 946)], (253, 246, 227))  # spout
    c.ellipse(872, 916, 30, 12, (253, 246, 227))                # lid
    c.circle(872, 902, 6, (180, 160, 140))                      # knob
    c.thick_polyline([(922, 930), (946, 940), (940, 968), (920, 972)], 7, (253, 246, 227))  # handle
    c.fill_rect(820, 946, 924, 952, (95, 138, 139))             # blue band
    c.ellipse(962, 980, 30, 20, (253, 246, 227))                # cup
    c.thick_polyline([(988, 970), (1004, 978), (996, 994)], 5, (253, 246, 227))
    c.sine(954, 966, 946, 966, 3, 1, 3, (216, 207, 192))


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output"
    try:
        os.makedirs(out_dir, exist_ok=True)
    except OSError:
        out_dir = "output"
        os.makedirs(out_dir, exist_ok=True)
    c = Canvas(W, H)
    draw_scene(c)
    png = encode_png(c.px, W, H)
    path = os.path.join(out_dir, "entry.png")
    with open(path, "wb") as f:
        f.write(png)
    print(f"wrote {path} ({len(png)} bytes, {W}x{H})")
    assert len(png) <= 1048576, "over the 1 MiB gate"
    return 0


if __name__ == "__main__":
    sys.exit(main())
