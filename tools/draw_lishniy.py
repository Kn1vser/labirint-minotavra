"""Концепт-арт «Лишнего»: тёмный коридор, одна лампа, и он стоит спиной,
повернув голову к тебе. Запуск: python tools/draw_lishniy.py (нужны pillow и numpy)."""
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

W, H = 768, 1024
S = 2
VX, VY = W / 2, 470          # точка схода
F = 520                       # фокус
EYE = 1.7                     # высота глаз
HALF_W, CEIL = 1.5, 2.85       # полуширина коридора и высота потолка
LAMP = np.array([0.0, CEIL - 0.1, 4.0])
FIG_Z = 4.9


def proj(x, y, z):
    return ((VX + x * F / z) * S, (VY - (y - EYE) * F / z) * S)


def light_at(p, normal):
    d = LAMP - p
    dist = np.linalg.norm(d)
    lam = max(0.0, float(np.dot(d / dist, normal)))
    return 0.02 + 7.5 * lam / (dist * dist + 0.8)


def shade(base, k, z):
    fog = math.exp(-max(0, z - 2) * 0.09)
    return tuple(int(min(255, c * k * fog)) for c in base)


def corridor(draw):
    zs = np.geomspace(1.2, 18, 140)
    wall = (150, 150, 138)
    floor = (110, 104, 92)
    ceil = (120, 120, 112)
    for z0, z1 in zip(zs[::-1][1:], zs[::-1][:-1]):  # от дальнего к ближнему
        zm = (z0 + z1) / 2
        # пол
        k = light_at(np.array([0, 0, zm]), np.array([0, 1, 0]))
        tile = 0.85 if int(zm * 1.6) % 2 else 1.0
        draw.polygon([proj(-HALF_W, 0, z0), proj(HALF_W, 0, z0), proj(HALF_W, 0, z1), proj(-HALF_W, 0, z1)],
                     fill=shade(floor, k * tile, zm))
        # потолок
        k = light_at(np.array([0, CEIL, zm]), np.array([0, -1, 0])) * 0.8
        draw.polygon([proj(-HALF_W, CEIL, z0), proj(HALF_W, CEIL, z0), proj(HALF_W, CEIL, z1), proj(-HALF_W, CEIL, z1)],
                     fill=shade(ceil, k, zm))
        # стены
        for side in (-1, 1):
            k = light_at(np.array([side * HALF_W, 1.3, zm]), np.array([-side, 0, 0]))
            draw.polygon([proj(side * HALF_W, 0, z0), proj(side * HALF_W, 0, z1),
                          proj(side * HALF_W, CEIL, z1), proj(side * HALF_W, CEIL, z0)],
                         fill=shade(wall, k, zm))
            # тёмная панель внизу стены
            draw.polygon([proj(side * HALF_W, 0, z0), proj(side * HALF_W, 0, z1),
                          proj(side * HALF_W, 0.9, z1), proj(side * HALF_W, 0.9, z0)],
                         fill=shade(wall, k * 0.5, zm))
    # дальний конец — темнота
    draw.polygon([proj(-HALF_W, 0, 18), proj(HALF_W, 0, 18), proj(HALF_W, CEIL, 18), proj(-HALF_W, CEIL, 18)],
                 fill=(4, 4, 4))
    # дверные проёмы: открытая чёрная дверь справа, закрытая слева
    for side, z, col in ((1, 3.2, (6, 6, 6)), (-1, 8.5, None), (1, 11, (5, 5, 5))):
        za, zb = z, z + 0.9
        if col is None:
            k = light_at(np.array([side * HALF_W, 1, z]), np.array([-side, 0, 0]))
            col = shade((90, 70, 52), k, z)
        draw.polygon([proj(side * HALF_W, 0, za), proj(side * HALF_W, 0, zb),
                      proj(side * HALF_W, 2.05, zb), proj(side * HALF_W, 2.05, za)], fill=col)
    # лампа
    lx, ly = proj(0, CEIL - 0.02, LAMP[2])
    draw.rectangle((lx - 26 * S, ly, lx + 26 * S, ly + 6 * S), fill=(255, 246, 215))


def lamp_glow(img):
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(glow)
    lx, ly = proj(0, CEIL - 0.1, LAMP[2])
    for r, a in ((150, 22), (90, 38), (45, 70)):
        d.ellipse((lx - r * S, ly - r * 0.6 * S, lx + r * S, ly + r * 0.6 * S), fill=(255, 238, 200, a))
    glow = glow.filter(ImageFilter.GaussianBlur(40 * S))
    img.paste(glow, (0, 0), glow)


def figure(img):
    z = FIG_Z
    sc = F / z * S              # пикселей на метр
    fx, fy = proj(0.15, 0, z)   # точка между ступнями
    m = lambda x, y: (fx + x * sc, fy - y * sc)

    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    lit = (196, 190, 176, 255)
    mid = (138, 132, 120, 255)
    darkc = (70, 66, 60, 255)

    # тень от лампы — уходит от зрителя в темноту
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    pts = [proj(0.0, 0, z), proj(0.35, 0, z), proj(0.55, 0, z + 3.5), proj(-0.2, 0, z + 3.5)]
    sd.polygon(pts, fill=(0, 0, 0, 150))
    shadow = shadow.filter(ImageFilter.GaussianBlur(6 * S))
    img.paste(shadow, (0, 0), shadow)

    def bone(a, b, w, col):
        d.line([m(*a), m(*b)], fill=col, width=max(1, int(w * sc)))
        r = w * sc * 0.5
        for p in (a, b):
            x, y = m(*p)
            d.ellipse((x - r, y - r, x + r, y + r), fill=col)

    # ноги
    bone((-0.13, 0.0), (-0.1, 1.1), 0.12, mid)
    bone((0.13, 0.0), (0.11, 1.1), 0.12, mid)
    # туловище (вид со спины, свет сверху)
    d.polygon([m(-0.2, 1.05), m(0.2, 1.05), m(0.27, 2.0), m(-0.27, 2.0)], fill=mid)
    d.polygon([m(-0.27, 2.0), m(0.27, 2.0), m(0.24, 1.75), m(-0.24, 1.75)], fill=lit)
    # позвоночник проступает
    for i in range(9):
        x, y = m(0.0, 1.2 + i * 0.09)
        r = 0.02 * sc
        d.ellipse((x - r, y - r, x + r, y + r), fill=darkc)
    # лопатки
    for sx in (-1, 1):
        d.polygon([m(sx * 0.05, 1.9), m(sx * 0.22, 1.88), m(sx * 0.17, 1.62)], fill=(160, 154, 140, 255))
    # руки — до середины голени
    bone((-0.29, 1.98), (-0.36, 0.45), 0.075, mid)
    bone((0.29, 1.98), (0.37, 0.42), 0.075, mid)
    for sx, base in ((-1, (-0.36, 0.45)), (1, (0.37, 0.42))):
        for f in range(4):
            ex = base[0] + sx * (0.01 + f * 0.018)
            bone(base, (ex, base[1] - 0.17 - f * 0.012), 0.016, mid)
    # шея — слишком длинная, перекручена
    bone((0.0, 2.0), (0.02, 2.36), 0.07, mid)
    for i in range(4):
        y = 2.08 + i * 0.07
        d.line([m(-0.035, y), m(0.045, y + 0.03)], fill=darkc, width=max(1, int(0.008 * sc)))

    # голова повёрнута к нам: гладкое лицо, два провала, вертикальный рот
    hx, hy = m(0.02, 2.56)
    hw, hh = 0.13 * sc, 0.2 * sc
    d.ellipse((hx - hw, hy - hh, hx + hw, hy + hh), fill=lit)
    d.ellipse((hx - hw, hy - hh * 0.2, hx + hw, hy + hh), fill=(176, 170, 156, 255))
    for ex in (-0.05, 0.05):
        x, y = hx + ex * sc, hy - 0.035 * sc
        d.ellipse((x - 0.03 * sc, y - 0.018 * sc, x + 0.03 * sc, y + 0.022 * sc), fill=(8, 6, 6, 255))
    d.rounded_rectangle((hx - 0.008 * sc, hy + 0.03 * sc, hx + 0.008 * sc, hy + 0.15 * sc),
                        radius=0.008 * sc, fill=(12, 6, 6, 255))

    # свет сверху: ноги тонут в темноте
    arr = np.asarray(layer).astype(np.float32)
    top, bottom = m(0, 2.8)[1], fy
    ys = np.arange(arr.shape[0], dtype=np.float32)
    k = np.clip(1.05 - 0.7 * (ys - top) / (bottom - top), 0.3, 1.05)
    arr[..., :3] *= k[:, None, None]
    layer = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

    contact = Image.new("RGBA", img.size, (0, 0, 0, 0))
    cx, cy = m(0, 0)
    ImageDraw.Draw(contact).ellipse((cx - 0.4 * sc, cy - 0.06 * sc, cx + 0.4 * sc, cy + 0.06 * sc), fill=(0, 0, 0, 200))
    contact = contact.filter(ImageFilter.GaussianBlur(4 * S))
    img.paste(contact, (0, 0), contact)
    img.paste(layer, (0, 0), layer)


def finish(img):
    img = img.resize((W, H), Image.LANCZOS)
    a = np.asarray(img).astype(np.float32)
    # виньетка
    yy, xx = np.mgrid[0:H, 0:W]
    r = np.sqrt(((xx - W / 2) / (W * 0.62)) ** 2 + ((yy - H * 0.47) / (H * 0.6)) ** 2)
    a *= np.clip(1.15 - r ** 2 * 0.9, 0.08, 1)[..., None]
    # холодный оттенок в тенях
    a[..., 2] += 6 * (1 - a.mean(axis=2) / 255)
    # плёночное зерно
    rng = np.random.default_rng(4)
    a += rng.normal(0, 7, (H, W, 1))
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def main():
    img = Image.new("RGB", (W * S, H * S), (0, 0, 0))
    corridor(ImageDraw.Draw(img))
    lamp_glow(img)
    figure(img)
    img = finish(img)
    out = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "unity", "Lishniy", "Art"))
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, "lishniy_concept.png")
    img.save(path)
    print("Сохранено:", path)


if __name__ == "__main__":
    main()
