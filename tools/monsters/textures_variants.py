"""Бесшовные текстуры для монстров-вариантов: хвоя, береста, болотная грязь.
Запуск: python textures_variants.py <папка unity>   (нужны numpy и pillow)"""
import os
import shutil
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "korenik"))
import textures as T  # noqa: E402  (pnoise, normal_map, save)

N = T.N
rng = np.random.default_rng(23)


def wrap_draw(draw, fn):
    """Рисует фигуру 9 раз со сдвигом на размер картинки — так края стыкуются."""
    for dx in (-N, 0, N):
        for dy in (-N, 0, N):
            fn(draw, dx, dy)


def needles(out):
    col = Image.new("RGB", (N, N), (38, 24, 14))
    hgt = Image.new("L", (N, N), 0)
    dc, dh = ImageDraw.Draw(col), ImageDraw.Draw(hgt)
    palette = [(120, 72, 36), (150, 96, 50), (96, 60, 34), (170, 120, 70), (84, 70, 52), (110, 100, 80)]
    for k in range(7000):
        x, y = rng.uniform(0, N, 2)
        a = rng.uniform(0, np.pi)
        L = rng.uniform(18, 55)
        x2, y2 = x + np.cos(a) * L, y + np.sin(a) * L
        w = int(rng.integers(2, 5))
        c = palette[rng.integers(len(palette))]
        c = tuple(int(v * rng.uniform(0.75, 1.1)) for v in c)
        level = int(60 + 195 * k / 7000)
        wrap_draw(dc, lambda d, dx, dy: d.line((x + dx, y + dy, x2 + dx, y2 + dy), fill=c, width=w))
        wrap_draw(dh, lambda d, dx, dy: d.line((x + dx, y + dy, x2 + dx, y2 + dy), fill=level, width=w))
    a = np.asarray(col).astype(np.float32) / 255
    a *= (1 + T.pnoise(120, 120)[..., None] * 0.12)
    h = np.asarray(hgt).astype(np.float32) / 255
    T.save(a, os.path.join(out, "Muravejnik_Needles_Albedo.png"))
    T.save(T.normal_map(h, 3.0), os.path.join(out, "Muravejnik_Needles_Normal.png"))


def birch(out):
    base = np.ones((N, N, 3)) * np.array([0.84, 0.83, 0.79])
    base *= (1 + T.pnoise(90, 160)[..., None] * 0.05 + T.pnoise(8, 30)[..., None] * 0.03)
    img = Image.fromarray((np.clip(base, 0, 1) * 255).astype(np.uint8))
    hgt = Image.new("L", (N, N), 200)
    d, dh = ImageDraw.Draw(img), ImageDraw.Draw(hgt)
    # тонкие рыжие линии отслоившейся бересты
    for _ in range(160):
        x, y = rng.uniform(0, N, 2)
        L = rng.uniform(40, 220)
        wrap_draw(d, lambda dr, dx, dy: dr.line((x + dx, y + dy, x + L + dx, y + dy), fill=(196, 150, 110), width=1))
        wrap_draw(dh, lambda dr, dx, dy: dr.line((x + dx, y + dy + 1, x + L + dx, y + dy + 1), fill=150, width=1))
    # чечевички — горизонтальные чёрные чёрточки
    for _ in range(420):
        x, y = rng.uniform(0, N, 2)
        w = rng.uniform(8, 55)
        h = rng.uniform(2, 7)
        c = int(rng.uniform(12, 40))
        wrap_draw(d, lambda dr, dx, dy: dr.ellipse((x + dx, y + dy, x + w + dx, y + h + dy), fill=(c, c - 2 if c > 2 else 0, c - 4 if c > 4 else 0)))
        wrap_draw(dh, lambda dr, dx, dy: dr.ellipse((x + dx, y + dy, x + w + dx, y + h + dy), fill=90))
    # крупные чёрные наплывы
    for _ in range(14):
        x, y = rng.uniform(0, N, 2)
        w, h = rng.uniform(80, 200), rng.uniform(25, 60)
        wrap_draw(d, lambda dr, dx, dy: dr.chord((x + dx, y + dy, x + w + dx, y + h + dy), 0, 180, fill=(22, 20, 18)))
        wrap_draw(dh, lambda dr, dx, dy: dr.chord((x + dx, y + dy, x + w + dx, y + h + dy), 0, 180, fill=60))
    a = np.asarray(img).astype(np.float32) / 255
    hh = np.asarray(hgt).astype(np.float32) / 255 + T.pnoise(3, 12) * 0.03
    T.save(a, os.path.join(out, "Bereznik_Birch_Albedo.png"))
    T.save(T.normal_map(hh, 4.0), os.path.join(out, "Bereznik_Birch_Normal.png"))


def mud(out):
    n1, n2, n3 = T.pnoise(160, 160), T.pnoise(30, 30), T.pnoise(4, 4)
    col = T.lerp(np.array([0.07, 0.06, 0.04]), np.array([0.17, 0.15, 0.09]), np.clip(n1 * 0.3 + 0.5 + n2 * 0.15, 0, 1))
    algae = np.clip(T.pnoise(110, 110) - 0.6, 0, 1)
    col = T.lerp(col, np.array([0.12, 0.14, 0.06]), np.clip(algae * 1.2, 0, 0.6))
    col *= (1 + n3[..., None] * 0.06)
    h = n1 * 0.4 + n2 * 0.4 + n3 * 0.15
    T.save(col, os.path.join(out, "Kochkarnik_Mud_Albedo.png"))
    T.save(T.normal_map(h, 2.0), os.path.join(out, "Kochkarnik_Mud_Normal.png"))


def copy_skin(korenik_tex, out, prefix, dirty=False):
    for kind in ("Albedo", "Normal"):
        shutil.copy(os.path.join(korenik_tex, f"Korenik_Skin_{kind}.png"), os.path.join(out, f"{prefix}_Skin_{kind}.png"))
    if dirty:   # кожа утопленника: серее, в разводах болотной грязи
        path = os.path.join(out, f"{prefix}_Skin_Albedo.png")
        a = np.asarray(Image.open(path).convert("RGB")).astype(np.float32) / 255
        a *= np.array([0.8, 0.8, 0.72])
        stains = np.clip(T.pnoise(70, 70) * 0.8 + T.pnoise(15, 15) * 0.3 - 0.7, 0, 1)
        a = T.lerp(a, np.array([0.16, 0.14, 0.08]), np.clip(stains * 1.1, 0, 0.6))
        T.save(a, path)


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else "unity"
    korenik_tex = os.path.join(root, "Korenik", "Textures")
    for name, fn in (("Muravejnik", needles), ("Bereznik", birch), ("Kochkarnik", mud)):
        out = os.path.join(root, name, "Textures")
        os.makedirs(out, exist_ok=True)
        fn(out)
        copy_skin(korenik_tex, out, name, dirty=(name != "Bereznik"))
        print("Текстуры:", out)
