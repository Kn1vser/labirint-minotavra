"""Рисует портрет монстра «Таёжный Двойник» и сохраняет в assets/monsters/.

Запуск: python tools/draw_monster.py  (нужен Pillow: pip install pillow)
"""
import math
import os
import random

from PIL import Image, ImageDraw, ImageFilter

W, H = 768, 1024
S = 2  # рисуем в 2 раза крупнее, потом уменьшаем — так края получаются гладкими
random.seed(7)


def sc(*pts):
    return [p * S for p in pts]


def poly(draw, pts, fill):
    draw.polygon([(x * S, y * S) for x, y in pts], fill=fill)


def sky():
    img = Image.new("RGB", (W * S, H * S))
    d = ImageDraw.Draw(img)
    for y in range(H * S):
        t = y / (H * S)
        r = int(8 + 18 * t)
        g = int(14 + 26 * t)
        b = int(26 + 22 * t)
        d.line([(0, y), (W * S, y)], fill=(r, g, b))
    return img


def moon(img):
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(glow)
    cx, cy = 560, 170
    for rad, a in ((150, 18), (110, 30), (80, 50)):
        d.ellipse(sc(cx - rad, cy - rad, cx + rad, cy + rad), fill=(190, 210, 200, a))
    glow = glow.filter(ImageFilter.GaussianBlur(30 * S))
    img.paste(glow, (0, 0), glow)
    d = ImageDraw.Draw(img)
    d.ellipse(sc(cx - 58, cy - 58, cx + 58, cy + 58), fill=(222, 228, 210))
    for ox, oy, rr in ((-18, -10, 12), (20, 15, 9), (5, 28, 6)):
        d.ellipse(sc(cx + ox - rr, cy + oy - rr, cx + ox + rr, cy + oy + rr), fill=(200, 206, 190))


def spruce(draw, x, base, h, col):
    w = h * 0.32
    tiers = 9
    for i in range(tiers):
        t = i / tiers
        y_top = base - h + h * t * 0.92
        y_bot = y_top + h * 0.22
        half = w * (0.15 + 0.85 * t) / 2
        jag = random.uniform(-4, 4)
        poly(draw, [(x, y_top), (x - half + jag, y_bot), (x + half + jag, y_bot)], col)
    draw.rectangle(sc(x - h * 0.012, base - h * 0.08, x + h * 0.012, base), fill=col)


def forest_layer(img, count, y_base, h_range, col, blur, xs=None):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for i in range(count):
        x = xs[i] if xs else random.uniform(-40, W + 40)
        h = random.uniform(*h_range)
        spruce(d, x, y_base + random.uniform(-10, 10), h, col)
    if y_base < H:
        d.rectangle(sc(0, y_base, W, H), fill=col)
    if blur:
        layer = layer.filter(ImageFilter.GaussianBlur(blur * S))
    img.paste(layer, (0, 0), layer)


def fog(img, y, strength):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for _ in range(14):
        cx = random.uniform(0, W)
        cy = y + random.uniform(-30, 30)
        rw, rh = random.uniform(120, 260), random.uniform(20, 45)
        d.ellipse(sc(cx - rw, cy - rh, cx + rw, cy + rh), fill=(150, 170, 165, strength))
    layer = layer.filter(ImageFilter.GaussianBlur(25 * S))
    img.paste(layer, (0, 0), layer)


def limb(draw, pts, width, col):
    """Ломаная «кость» с суставами."""
    p = [(x * S, y * S) for x, y in pts]
    draw.line(p, fill=col, width=int(width * S), joint="curve")
    for x, y in p:
        r = width * S * 0.55
        draw.ellipse((x - r, y - r, x + r, y + r), fill=col)


def fingers(draw, x, y, direction, col):
    for i in range(4):
        ang = math.radians(90 + direction * (8 + i * 9))
        length = 70 + i * 6
        mx = x + math.cos(ang) * length * 0.55
        my = y + math.sin(ang) * length * 0.55
        ex = x + math.cos(ang + direction * 0.25) * length
        ey = y + math.sin(ang + direction * 0.25) * length
        limb(draw, [(x, y), (mx, my), (ex, ey)], 4.5, col)


def creature(img):
    skin = (196, 192, 176)
    skin_dark = (150, 146, 132)
    coat = (58, 52, 44)
    coat_light = (78, 70, 58)
    d = ImageDraw.Draw(img)
    cx = 360

    # тень на снегу
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).ellipse(sc(cx - 170, 925, cx + 170, 965), fill=(0, 0, 0, 120))
    shadow = shadow.filter(ImageFilter.GaussianBlur(12 * S))
    img.paste(shadow, (0, 0), shadow)

    # ноги — слишком длинные, колени выгнуты назад
    limb(d, [(cx - 30, 640), (cx - 70, 780), (cx - 45, 935)], 15, skin_dark)
    limb(d, [(cx + 30, 640), (cx + 75, 785), (cx + 55, 935)], 15, skin_dark)
    poly(d, [(cx - 45, 930), (cx - 95, 945), (cx - 30, 945)], skin_dark)
    poly(d, [(cx + 55, 930), (cx + 105, 945), (cx + 40, 945)], skin_dark)

    # руки — свисают ниже колен
    limb(d, [(cx - 70, 400), (cx - 150, 560), (cx - 165, 760)], 13, skin)
    limb(d, [(cx + 70, 400), (cx + 140, 570), (cx + 170, 770)], 13, skin)
    fingers(d, cx - 165, 760, 1, skin)
    fingers(d, cx + 170, 770, -1, skin)

    # краденая куртка охотника, слишком короткая
    poly(d, [(cx - 85, 385), (cx + 85, 385), (cx + 70, 660), (cx + 10, 690),
             (cx - 15, 650), (cx - 75, 670)], coat)
    poly(d, [(cx - 85, 385), (cx - 40, 380), (cx - 20, 560), (cx - 60, 600)], coat_light)
    d.line(sc(cx, 395, cx + 2, 660), fill=(40, 36, 30), width=3 * S)
    for i, by in enumerate((440, 500, 560)):
        d.ellipse(sc(cx + 8 - 5, by - 5, cx + 8 + 5, by + 5), fill=(120, 110, 80))
    # рукава оборваны — видна голая рука
    poly(d, [(cx - 85, 385), (cx - 115, 470), (cx - 92, 480), (cx - 70, 410)], coat)
    poly(d, [(cx + 85, 385), (cx + 112, 475), (cx + 90, 485), (cx + 70, 410)], coat)

    # шея — длинная и тонкая
    limb(d, [(cx, 390), (cx + 6, 330), (cx + 14, 285)], 14, skin)

    # голова чуть набок — «изучает» человека
    head = Image.new("RGBA", img.size, (0, 0, 0, 0))
    hd = ImageDraw.Draw(head)
    hx, hy = cx + 18, 225
    hd.ellipse(sc(hx - 52, hy - 72, hx + 52, hy + 72), fill=skin + (255,))
    # шапка-ушанка
    hd.pieslice(sc(hx - 60, hy - 95, hx + 60, hy + 5), 180, 360, fill=(70, 60, 48, 255))
    hd.rectangle(sc(hx - 62, hy - 48, hx + 62, hy - 30), fill=(92, 80, 62, 255))
    hd.rounded_rectangle(sc(hx - 70, hy - 40, hx - 48, hy + 25), radius=8 * S, fill=(70, 60, 48, 255))
    hd.rounded_rectangle(sc(hx + 48, hy - 40, hx + 70, hy + 25), radius=8 * S, fill=(70, 60, 48, 255))
    # пустые глаза-впадины
    for ex in (hx - 22, hx + 22):
        hd.ellipse(sc(ex - 15, hy - 14, ex + 15, hy + 10), fill=(18, 16, 14, 255))
    # слишком широкая «человеческая» улыбка
    hd.chord(sc(hx - 42, hy + 2, hx + 42, hy + 52), 10, 170, fill=(30, 18, 18, 255))
    for i in range(12):
        tx = hx - 34 + i * 6.2
        ty = hy + 30 + math.sin(i / 11 * math.pi) * 8
        hd.polygon([(tx * S, ty * S), ((tx + 5) * S, ty * S), ((tx + 2.5) * S, (ty + 9) * S)],
                   fill=(225, 222, 200, 255))
    head = head.rotate(-9, center=(hx * S, hy * S), resample=Image.BICUBIC)
    img.paste(head, (0, 0), head)

    # светящиеся точки-зрачки
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for ex, ey in ((hx - 20, hy - 6), (hx + 25, hy - 1)):
        gd.ellipse(sc(ex - 14, ey - 14, ex + 14, ey + 14), fill=(255, 220, 120, 130))
    glow = glow.filter(ImageFilter.GaussianBlur(8 * S))
    img.paste(glow, (0, 0), glow)
    d = ImageDraw.Draw(img)
    for ex, ey in ((hx - 20, hy - 6), (hx + 25, hy - 1)):
        d.ellipse(sc(ex - 4, ey - 4, ex + 4, ey + 4), fill=(255, 240, 190))


def snow(img):
    d = ImageDraw.Draw(img)
    for _ in range(260):
        x, y = random.uniform(0, W), random.uniform(0, H)
        r = random.choice((0.8, 1.2, 1.8))
        c = random.randint(170, 230)
        d.ellipse(sc(x - r, y - r, x + r, y + r), fill=(c, c, c))


def vignette(img):
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).ellipse(sc(-120, -80, W + 120, H + 80), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(90 * S))
    dark = Image.new("RGB", img.size, (4, 6, 8))
    return Image.composite(img, dark, mask)


def main():
    img = sky()
    moon(img)
    forest_layer(img, 26, 720, (300, 460), (24, 36, 40, 255), 3)
    fog(img, 700, 60)
    forest_layer(img, 18, 800, (420, 620), (14, 22, 24, 255), 1)
    fog(img, 820, 70)
    ImageDraw.Draw(img).rectangle(sc(0, 880, W, H), fill=(120, 132, 134))
    fog(img, 900, 90)
    creature(img)
    forest_layer(img, 3, 1040, (850, 1000), (6, 10, 11, 255), 0, xs=[-30, 40, W + 20])
    snow(img)
    img = vignette(img)
    img = img.resize((W, H), Image.LANCZOS)

    out = os.path.join(os.path.dirname(__file__), "..", "assets", "monsters")
    os.makedirs(out, exist_ok=True)
    path = os.path.normpath(os.path.join(out, "taezhny_dvoynik.png"))
    img.save(path)
    print("Сохранено:", path)


if __name__ == "__main__":
    main()
