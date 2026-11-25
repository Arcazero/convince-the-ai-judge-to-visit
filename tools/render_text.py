#!/usr/bin/env python3
"""Render the invitation letter text to assets/letter_text.png (transparent RGBA).

This is a build-time helper only: it runs here on this machine with Pillow.
The entry program (main.py) is pure stdlib and pastes the rendered text onto
the scene it draws itself. The wording below is the whole letter.
"""
from PIL import Image, ImageDraw, ImageFont

INK = (59, 47, 47, 255)          # dark warm brown ink
FAINT = (122, 90, 70, 255)       # softer brown for the header line

SERIF = "/usr/share/fonts/truetype/noto/NotoSerif-Regular.ttf"
ITALIC = "/usr/share/fonts/truetype/noto/NotoSerif-Italic.ttf"
BOLD_ITALIC = "/usr/share/fonts/truetype/noto/NotoSerif-BoldItalic.ttf"

WIDTH = 580                      # text column width (fits the paper in main.py)

HEADER = "· An Invitation ·"
PARAS = [
    ("Dear Judge,", "bold"),
    ("You spend all day reading other people's invitations \u2014 so this one is just for you.", "body"),
    ("Come over for tea. The kettle is already on, the apple pie is still warm from the oven, and the good armchair by the window is saved for you. At sunset the garden turns gold \u2014 and no one will ask you to judge a single thing.", "body"),
    ("No travel needed. Just say yes, and consider yourself already home.", "body"),
    ("Warmly,\nyour neighbour & biggest fan", "sign"),
    ("P.S. The Wi-Fi password is on the fridge.", "ps"),
]

FONTS = {
    "header": ImageFont.truetype(ITALIC, 24),
    "bold": ImageFont.truetype(BOLD_ITALIC, 36),
    "body": ImageFont.truetype(ITALIC, 30),
    "sign": ImageFont.truetype(ITALIC, 30),
    "ps": ImageFont.truetype(ITALIC, 26),
}
LEADING = {"header": 34, "bold": 48, "body": 42, "sign": 40, "ps": 36}
PARA_GAP = 16


def wrap(draw, text, font, width):
    words = text.split(" ")
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=font) <= width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def main():
    probe = Image.new("RGBA", (10, 10))
    d = ImageDraw.Draw(probe)
    # Lay out first to learn the height.
    laid = []  # (text, kind, y)
    y = 0
    hw = d.textlength(HEADER, font=FONTS["header"])
    laid.append(("header", HEADER, "header", y, (WIDTH - hw) / 2))
    y += LEADING["header"] + 10
    for text, kind in PARAS:
        font = FONTS[kind]
        for raw in text.split("\n"):
            for line in wrap(d, raw, font, WIDTH):
                laid.append((kind, line, kind, y, 0))
                y += LEADING[kind]
        y += PARA_GAP
    height = int(y - PARA_GAP + 8)

    img = Image.new("RGBA", (WIDTH, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for kind, line, _k, ly, lx in laid:
        color = FAINT if kind == "header" else INK
        d.text((lx, ly), line, font=FONTS[kind], fill=color)

    img.save("assets/letter_text.png")
    print(f"wrote assets/letter_text.png {WIDTH}x{height}")


if __name__ == "__main__":
    main()
