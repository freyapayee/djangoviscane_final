from pathlib import Path
from PIL import Image, ImageDraw

OUT = Path('/Users/fayecuevas/djangoviscane/static/icons/tarpaulin')
SIZE = 512
BG = (216, 244, 214, 255)
PALE = (236, 250, 230, 255)
GREEN = (51, 121, 67, 255)
DARK = (28, 83, 48, 255)
MID = (126, 194, 116, 255)
MINT = (180, 226, 166, 255)
WHITE = (255, 255, 255, 255)
W = 28


def base():
    im = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((28, 28, 484, 484), radius=108, fill=BG, outline=GREEN, width=10)
    return im, d


def line(d, pts, fill=DARK, width=W, joint='curve'):
    d.line(pts, fill=fill, width=width, joint=joint)


def save(name, draw_icon):
    im, d = base()
    draw_icon(d)
    im.save(OUT / f'{name}.png', optimize=True)


def grading(d):
    d.rounded_rectangle((122, 116, 390, 394), radius=44, fill=WHITE, outline=DARK, width=W)
    d.rounded_rectangle((151, 150, 361, 195), radius=22, fill=MINT, outline=GREEN, width=12)
    line(d, [(169, 258), (196, 285), (252, 226)], GREEN, 30)
    line(d, [(271, 266), (342, 266)], MID, 26)
    line(d, [(169, 333), (196, 360), (252, 301)], GREEN, 30)
    line(d, [(271, 341), (342, 341)], MID, 26)


def assessment(d):
    d.ellipse((108, 122, 404, 418), fill=PALE, outline=DARK, width=W)
    d.ellipse((166, 177, 348, 359), fill=MINT, outline=GREEN, width=18)
    line(d, [(257, 116), (257, 80)], GREEN, 22)
    line(d, [(257, 432), (257, 396)], GREEN, 22)
    line(d, [(102, 270), (66, 270)], GREEN, 22)
    line(d, [(448, 270), (412, 270)], GREEN, 22)
    d.arc((166, 177, 348, 359), 215, 325, fill=DARK, width=16)
    d.ellipse((238, 246, 270, 278), fill=DARK)


def yield_estimation(d):
    d.line((105, 390, 409, 390), fill=DARK, width=24)
    bars = [(128, 292, 174, 390), (207, 236, 253, 390), (286, 179, 332, 390)]
    for i, box in enumerate(bars):
        d.rounded_rectangle(box, radius=16, fill=(164, 217 - i * 12, 146, 255), outline=GREEN, width=14)
    line(d, [(117, 196), (191, 258), (269, 207), (372, 111)], GREEN, 24)
    d.polygon([(372, 111), (332, 124), (361, 153)], fill=GREEN)


def recommendations(d):
    d.polygon([(256, 96), (294, 188), (394, 198), (318, 264), (342, 365), (256, 310), (170, 365), (194, 264), (118, 198), (218, 188)], fill=MINT, outline=DARK)
    d.ellipse((218, 191, 294, 267), fill=WHITE, outline=GREEN, width=14)
    line(d, [(237, 314), (275, 314)], GREEN, 18)
    line(d, [(243, 345), (269, 345)], GREEN, 18)


def dashboard(d):
    d.rounded_rectangle((98, 116, 414, 378), radius=28, fill=WHITE, outline=DARK, width=W)
    d.rounded_rectangle((120, 141, 392, 183), radius=14, fill=MINT)
    d.rounded_rectangle((134, 222, 206, 334), radius=16, fill=(157, 213, 137, 255), outline=GREEN, width=12)
    d.rounded_rectangle((220, 274, 292, 334), radius=16, fill=(132, 193, 113, 255), outline=GREEN, width=12)
    d.rounded_rectangle((306, 245, 378, 334), radius=16, fill=(104, 174, 98, 255), outline=GREEN, width=12)
    line(d, [(134, 398), (378, 398)], DARK, 22)


def reports(d):
    d.rounded_rectangle((134, 92, 378, 416), radius=28, fill=WHITE, outline=DARK, width=W)
    d.polygon([(302, 92), (378, 168), (302, 168)], fill=MINT, outline=DARK)
    line(d, [(176, 212), (336, 212)], MID, 20)
    line(d, [(176, 260), (336, 260)], MID, 20)
    line(d, [(176, 308), (284, 308)], MID, 20)
    line(d, [(178, 364), (207, 391), (256, 337), (281, 357), (338, 296)], GREEN, 20)


def language(d):
    d.rounded_rectangle((92, 142, 326, 324), radius=36, fill=WHITE, outline=DARK, width=W)
    d.polygon([(146, 324), (124, 382), (204, 324)], fill=WHITE, outline=DARK)
    d.rounded_rectangle((236, 202, 420, 354), radius=34, fill=MINT, outline=GREEN, width=W)
    d.polygon([(360, 354), (389, 398), (310, 354)], fill=MINT, outline=GREEN)
    d.text((154, 194), 'A', fill=DARK, anchor='mm', stroke_width=1)
    d.text((275, 278), '文', fill=GREEN, anchor='mm', stroke_width=1)


def offline_mobile(d):
    d.rounded_rectangle((153, 88, 359, 420), radius=38, fill=WHITE, outline=DARK, width=W)
    d.rounded_rectangle((186, 133, 326, 356), radius=18, fill=PALE, outline=GREEN, width=14)
    line(d, [(222, 391), (290, 391)], GREEN, 18)
    d.arc((105, 144, 254, 293), 220, 318, fill=GREEN, width=20)
    d.arc((70, 124, 289, 343), 220, 318, fill=GREEN, width=20)
    line(d, [(92, 106), (380, 394)], DARK, 26)


def compact_workflow():
    width, height = 1100, 430
    im = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    boxes = [
        ('CAPTURE', 'Upload or capture\nsugarcane image'),
        ('AI SCAN', 'YOLOv8 + ResNet-18\nvariety and maturity'),
        ('INPUTS', 'Add agronomic\ninformation'),
        ('RESULTS', 'Yield estimate +\nrecommendations'),
        ('RECORDS', 'Save scan history\nand admin reports'),
    ]
    x_positions = [18, 235, 452, 669, 886]
    for index, (title, subtitle) in enumerate(boxes):
        x = x_positions[index]
        d.rounded_rectangle((x, 32, x + 190, 326), radius=28, fill=(239, 250, 235, 245), outline=GREEN, width=8)
        d.ellipse((x + 52, 54, x + 138, 140), fill=MINT, outline=DARK, width=8)
        cx, cy = x + 95, 97
        if index == 0:
            d.rounded_rectangle((x + 70, 73, x + 120, 111), radius=8, outline=DARK, width=8)
            d.ellipse((x + 84, 82, x + 106, 104), outline=GREEN, width=6)
        elif index == 1:
            line(d, [(cx - 26, cy), (cx - 10, cy + 16), (cx + 28, cy - 22)], DARK, 12)
            for px, py in [(cx - 27, cy - 26), (cx + 31, cy - 28), (cx + 34, cy + 27), (cx - 31, cy + 28)]:
                d.ellipse((px - 7, py - 7, px + 7, py + 7), fill=GREEN)
        elif index == 2:
            d.rounded_rectangle((x + 72, 72, x + 118, 116), radius=7, fill=WHITE, outline=DARK, width=7)
            line(d, [(x + 82, 86), (x + 108, 86)], GREEN, 6)
            line(d, [(x + 82, 101), (x + 108, 101)], GREEN, 6)
        elif index == 3:
            line(d, [(x + 71, 113), (x + 89, 95), (x + 103, 106), (x + 124, 76)], DARK, 9)
            d.polygon([(x + 124, 76), (x + 111, 80), (x + 120, 90)], fill=DARK)
        else:
            d.rounded_rectangle((x + 69, 72, x + 121, 115), radius=7, outline=DARK, width=7)
            for by, bh in [(103, 10), (91, 22), (78, 35)]:
                d.rounded_rectangle((x + 78, by, x + 88, 113), radius=3, fill=GREEN)
                d.rounded_rectangle((x + 96, by, x + 106, 113), radius=3, fill=MID)
                d.rounded_rectangle((x + 114, by, x + 124, 113), radius=3, fill=MINT)
        d.text((cx, 174), title, fill=DARK, anchor='mm', font=None)
        d.multiline_text((cx, 217), subtitle, fill=GREEN, anchor='ma', align='center', spacing=7)
        if index < len(boxes) - 1:
            line(d, [(x + 198, 179), (x + 226, 179)], GREEN, 9)
            d.polygon([(x + 226, 179), (x + 211, 169), (x + 211, 189)], fill=GREEN)
    d.rounded_rectangle((20, 355, 1080, 412), radius=26, fill=(213, 240, 221, 220), outline=GREEN, width=6)
    d.text((550, 383), 'OFFLINE MOBILE: prediction • detection • assessment', fill=DARK, anchor='mm')
    im.save(OUT / 'system-workflow-compact.png', optimize=True)


def panel_workflow():
    width, height = 760, 700
    im = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    try:
        from PIL import ImageFont
        bold = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Bold.ttf', 25)
        regular = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 20)
        small = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 17)
    except OSError:
        bold = regular = small = None
    cards = [
        (35, 35, '1  CAPTURE', 'Upload or capture\nsugarcane image', 0),
        (395, 35, '2  AI SCAN', 'YOLOv8 + ResNet-18\nvariety and maturity', 1),
        (35, 285, '3  INPUTS', 'Add agronomic\ninformation', 2),
        (395, 285, '4  RESULTS', 'Yield estimate +\nrecommendations', 3),
    ]
    for x, y, title, subtitle, kind in cards:
        d.rounded_rectangle((x, y, x + 330, y + 190), radius=28, fill=(239, 250, 235, 250), outline=GREEN, width=8)
        d.ellipse((x + 22, y + 43, x + 112, y + 133), fill=MINT, outline=DARK, width=8)
        cx, cy = x + 67, y + 88
        if kind == 0:
            d.rounded_rectangle((x + 43, y + 67, x + 91, y + 106), radius=8, outline=DARK, width=7)
            d.ellipse((x + 58, y + 77, x + 78, y + 97), outline=GREEN, width=5)
        elif kind == 1:
            line(d, [(cx - 23, cy), (cx - 8, cy + 15), (cx + 25, cy - 21)], DARK, 11)
            for px, py in [(cx - 25, cy - 25), (cx + 28, cy - 25), (cx + 30, cy + 25), (cx - 28, cy + 26)]:
                d.ellipse((px - 6, py - 6, px + 6, py + 6), fill=GREEN)
        elif kind == 2:
            d.rounded_rectangle((x + 43, y + 65, x + 91, y + 111), radius=7, fill=WHITE, outline=DARK, width=7)
            line(d, [(x + 53, y + 80), (x + 81, y + 80)], GREEN, 6)
            line(d, [(x + 53, y + 97), (x + 81, y + 97)], GREEN, 6)
        else:
            line(d, [(x + 42, y + 105), (x + 58, y + 88), (x + 70, y + 98), (x + 93, y + 67)], DARK, 9)
            d.polygon([(x + 93, y + 67), (x + 80, y + 72), (x + 90, y + 82)], fill=DARK)
        d.text((x + 133, y + 62), title, fill=DARK, font=bold)
        d.multiline_text((x + 133, y + 102), subtitle, fill=GREEN, font=small, spacing=5)
    # flow arrows
    line(d, [(365, 130), (390, 130)], GREEN, 9)
    d.polygon([(390, 130), (375, 120), (375, 140)], fill=GREEN)
    line(d, [(560, 235), (560, 275)], GREEN, 9)
    d.polygon([(560, 275), (550, 260), (570, 260)], fill=GREEN)
    line(d, [(395, 380), (370, 380)], GREEN, 9)
    d.polygon([(370, 380), (385, 370), (385, 390)], fill=GREEN)
    d.rounded_rectangle((35, 535, 725, 655), radius=28, fill=(213, 240, 221, 250), outline=GREEN, width=8)
    d.text((65, 557), '5  RECORDS & OFFLINE MOBILE', fill=DARK, font=bold)
    d.multiline_text((65, 598), 'Save scan history and reports  •  prediction, detection,\nand assessment remain available offline', fill=GREEN, font=small, spacing=4)
    im.save(OUT / 'system-workflow-panel.png', optimize=True)


OUT.mkdir(parents=True, exist_ok=True)
for name, fn in [
    ('ai-quality-grading', grading),
    ('variety-maturity-assessment', assessment),
    ('yield-estimation', yield_estimation),
    ('agronomic-recommendations', recommendations),
    ('admin-monitoring-dashboard', dashboard),
    ('reports-analytics', reports),
    ('multilingual-support', language),
    ('offline-mobile-ai', offline_mobile),
]:
    save(name, fn)

compact_workflow()
panel_workflow()
