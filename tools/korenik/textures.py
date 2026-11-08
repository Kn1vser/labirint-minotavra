"""Бесшовные текстуры для «Корневика» (albedo + normal).
Запуск: python textures.py <папка_вывода>   (нужны numpy и pillow)"""
import os
import sys

import numpy as np
from PIL import Image

N = 1024
rng = np.random.default_rng(11)


def pnoise(sx, sy, seed_shift=0):
    """Периодический (бесшовный) шум. sx, sy — примерный размер деталей в пикселях по X и Y."""
    white = rng.normal(size=(N, N))
    f = np.fft.fftfreq(N)
    kx, ky = np.meshgrid(f, f)
    filt = np.exp(-((kx * sx) ** 2 + (ky * sy) ** 2))
    out = np.real(np.fft.ifft2(np.fft.fft2(white) * filt))
    out -= out.mean()
    return out / (out.std() + 1e-9)


def normal_map(h, strength):
    dx = (np.roll(h, -1, axis=1) - np.roll(h, 1, axis=1)) * strength
    dy = (np.roll(h, -1, axis=0) - np.roll(h, 1, axis=0)) * strength
    # строки изображения идут сверху вниз, а V в UV — снизу вверх
    n = np.stack([-dx, dy, np.ones_like(h)], axis=-1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return n * 0.5 + 0.5


def lerp(a, b, t):
    return a + (b - a) * t[..., None]


def save(arr, path):
    Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8)).save(path)


def bark(out):
    # продольные борозды: шум растянут вдоль ствола (ось Y картинки)
    ridges = np.clip(1 - np.abs(pnoise(22, 240)) * 0.9, 0, 1)
    ridges = ridges ** 2.2
    plates = pnoise(70, 160) * 0.5
    fine = pnoise(3, 9) * 0.25
    cracks = np.clip(1 - np.abs(pnoise(45, 7)) * 3.5, 0, 1)  # поперечные трещины
    h = ridges + plates * 0.4 + fine * 0.3 - cracks * 0.5
    h = (h - h.min()) / (h.max() - h.min())

    dark = np.array([0.055, 0.045, 0.035])
    mid = np.array([0.26, 0.22, 0.17])
    light = np.array([0.45, 0.42, 0.37])
    col = lerp(dark, mid, np.clip(h * 1.6, 0, 1))
    col = lerp(col, light, np.clip((h - 0.62) * 2.8, 0, 1))

    # пятна мха и серого лишайника
    moss_mask = np.clip(pnoise(180, 180) * 0.9 - 0.5, 0, 1) * np.clip(h * 1.5, 0, 1)
    col = lerp(col, np.array([0.15, 0.18, 0.08]), np.clip(moss_mask * 1.2, 0, 0.7))
    lich_mask = np.clip(pnoise(60, 60) - 1.6, 0, 1) * np.clip((h - 0.4) * 3, 0, 1)
    col = lerp(col, np.array([0.55, 0.58, 0.50]), np.clip(lich_mask * 2, 0, 0.8))
    col *= (1 + fine[..., None] * 0.12)

    save(col, os.path.join(out, "Korenik_Bark_Albedo.png"))
    save(normal_map(h, 9.0), os.path.join(out, "Korenik_Bark_Normal.png"))


def skin(out):
    mottling = pnoise(90, 90) * 0.5 + pnoise(14, 14) * 0.3
    veins = np.clip(1 - np.abs(pnoise(30, 30)) * 9, 0, 1) * np.clip(pnoise(160, 160) + 0.3, 0, 1)
    pores = pnoise(1.5, 1.5)

    base = np.array([0.58, 0.56, 0.50])
    col = base * (1 + mottling[..., None] * 0.05)
    col = lerp(col, np.array([0.55, 0.60, 0.66]), veins * 0.45)        # синеватые вены
    col = lerp(col, np.array([0.62, 0.52, 0.46]), np.clip(pnoise(170, 170) - 0.9, 0, 1) * 0.5)  # трупные пятна
    h = pores * 0.15 - veins * 0.4 + mottling * 0.2
    save(col, os.path.join(out, "Korenik_Skin_Albedo.png"))
    save(normal_map(h, 2.5), os.path.join(out, "Korenik_Skin_Normal.png"))


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    os.makedirs(out, exist_ok=True)
    bark(out)
    skin(out)
    print("Текстуры сохранены в", out)
