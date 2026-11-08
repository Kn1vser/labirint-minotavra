"""Три таёжных монстра-варианта: Муравейник, Берёзник, Кочкарник.
Строит модели в Blender, экспортирует FBX, рендерит превью.

Запуск (нужен bpy: pip install bpy numpy):
    python build_variants.py <папка unity> [имя ...] [--no-render]
Сначала сгенерируй текстуры: python textures_variants.py <папка unity>
"""
import math
import os
import sys

import bpy
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "korenik"))
import build_korenik as K  # noqa: E402
from build_korenik import MeshBuilder, catmull, ellipsoid, face_shape, gauss, hand, tube, wobble  # noqa: E402

MAIN, SKIN, STRAND, DARK, EYE = range(5)
UP = np.array([0.0, 0.0, 1.0])


def unit(v):
    v = np.asarray(v, float)
    return v / (np.linalg.norm(v) + 1e-12)


def dome(mb, center, radii, disp, mat, lat_range=(-math.pi / 2, math.pi / 2), nlat=60, nlon=120, tile=0.6):
    """Деформированная сфера: disp(direction) -> множитель радиуса."""
    center, radii = np.asarray(center, float), np.asarray(radii, float)
    lats = np.linspace(lat_range[0], lat_range[1], nlat + 1)
    lons = np.linspace(0, 2 * math.pi, nlon, endpoint=False)
    U = max(1, round(2 * math.pi * radii[:2].mean() / tile))
    V = max(1, round(math.pi * radii[2] / tile))
    grid = []
    for la in lats:
        row = []
        for lo in lons:
            d = np.array([math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la)])
            row.append(mb.add_vert(center + d * radii * disp(d)))
        grid.append(row)
    for i in range(nlat):
        for j in range(nlon):
            j2 = (j + 1) % nlon
            u0, u1 = j / nlon * U, (j + 1) / nlon * U
            v0, v1 = i / nlat * V, (i + 1) / nlat * V
            mb.add_face([grid[i][j], grid[i][j2], grid[i + 1][j2], grid[i + 1][j]], [(u0, v0), (u1, v0), (u1, v1), (u0, v1)], mat)


def lumpy(rng, count, amp, width, base_noise=0.03):
    lumps = [(unit(rng.normal(size=3)), rng.uniform(*amp), rng.uniform(*width)) for _ in range(count)]
    ph = rng.uniform(0, 6.28, 6)

    def f(d):
        v = 1.0
        for u, a, w in lumps:
            v += a * math.exp(-(1 - float(np.dot(d, u))) / w)
        v += base_noise * math.sin(d[0] * 7 + ph[0]) * math.sin(d[1] * 6 + ph[1]) * math.sin(d[2] * 8 + ph[2])
        v += base_noise * 0.5 * math.sin(d[0] * 17 + ph[3]) * math.sin(d[1] * 19 + ph[4])
        return v
    return f


def open_face(u, w):
    """Лицо с открытыми глазами: убираем веки из рельефа Корневика."""
    h = face_shape(u, w)
    for sx in (-1, 1):
        ex = u - sx * 0.34
        h -= 0.30 * gauss(math.hypot(ex * 1.1, (w - 0.12) * 1.8), 0.1)
        h += 0.07 * gauss(ex, 0.12) * gauss(w - 0.08, 0.018)
    return h


def head(mb, center, right, fwd, upv, radii, opened, eye_r=None, shape=None):
    """Голова с лицом. opened=True — с глазными яблоками в глазницах."""
    right, fwd, upv = unit(right), unit(fwd), unit(upv)
    shape = shape or (open_face if opened else face_shape)
    ellipsoid(mb, center, (right, fwd, upv), radii, SKIN, nlat=80, nlon=90, shape=shape)
    if not opened:
        return
    a, b, c = radii
    for sx in (-1, 1):
        u, w = sx * 0.34, 0.14
        la = math.asin(w)
        lo = math.asin(u / math.cos(la))
        y = b * math.cos(lo) * math.cos(la) + shape(u, w) * b * math.cos(lo)
        p = np.asarray(center) + right * a * u + upv * c * w + fwd * (y + 0.01 * a / 0.145)
        r = eye_r or a * 0.2
        ellipsoid(mb, p, (right, fwd, upv), (r, r * 0.9, r * 0.8), EYE, nlat=12, nlon=16)
        # маленький зрачок — взгляд в упор
        ellipsoid(mb, p + fwd * r * 0.78, (right, fwd, upv), (r * 0.3, r * 0.2, r * 0.3), DARK, nlat=8, nlon=12)


def arm(mb, joints, radii=(0.05, 0.036, 0.03), segs=12, n=60):
    """Рука через суставы joints (плечо, локти..., запястье). На каждом суставе — костлявое утолщение."""
    J = [np.asarray(j, float) for j in joints]
    ctrl = [J[0]]
    for a, b in zip(J[:-1], J[1:]):
        ctrl += [a * 0.55 + b * 0.45, b]
    P = catmull(ctrl, n)
    t = np.linspace(0, 1, n)
    seg = np.concatenate([[0], np.cumsum([np.linalg.norm(b - a) for a, b in zip(J[:-1], J[1:])])])
    seg /= seg[-1]
    r = np.interp(t, np.linspace(0, 1, len(radii)), radii)
    for jt in seg[1:-1]:
        r = r + 0.011 * np.exp(-((t - jt) / 0.03) ** 2)
    tube(mb, P, r, segs, SKIN, end_tip=0.0)
    return unit(P[-1] - P[-4])


def hair(mb, start, out, length, rng, r0=0.0035, ground=0.06):
    """Стебель осоки: поднимается дугой и ложится на землю."""
    n = 12
    out = unit(out)
    side = unit(np.cross(out, UP)) * rng.normal(0, 0.12)
    rise = rng.uniform(0.18, 0.32)
    pts = [start,
           start + out * length * 0.12 + UP * length * rise,
           start + (out + side * 0.5) * length * 0.42 + UP * length * rise * 0.85,
           start + (out + side) * length * 0.72 + UP * length * rise * 0.25,
           start + (out + side * 1.2) * length]
    for p in pts[2:]:
        p[2] = max(ground, p[2])
    pts[-1][2] = ground
    tube(mb, catmull(pts, n), np.linspace(r0, r0 * 0.25, n), 3, STRAND, end_tip=r0)


# ======================= МУРАВЕЙНИК =======================

def build_muravejnik():
    rng = np.random.default_rng(5)
    K.rng = rng
    mb = MeshBuilder()
    R = np.array([1.35, 1.25, 1.9])
    base_disp = lumpy(rng, 22, (0.04, 0.16), (0.02, 0.1), base_noise=0.05)

    def disp(d):
        return base_disp(d) * (1 - 0.18 * max(0.0, d[2]) ** 0.7 + 0.2 * max(0.0, d[2]) ** 6)
    dome(mb, (0, 0, 0), R, disp, MAIN, lat_range=(-0.08, math.pi / 2), nlat=70, nlon=140, tile=0.5)

    def surf(d):
        d = unit(d)
        p = d * R * disp(d)
        n = unit(d / (R * R))
        return p, n

    def rand_dir(zmin=0.05, zmax=1.0):
        while True:
            d = unit(rng.normal(size=3))
            if zmin < d[2] < zmax:
                return d

    # хвоинки торчат из купола
    for _ in range(2200):
        p, n = surf(rand_dir(0.0))
        t = unit(np.cross(n, rng.normal(size=3)))
        dirv = unit(n * rng.uniform(0.1, 0.6) + t)
        L = rng.uniform(0.04, 0.09)
        tube(mb, [p - n * 0.01, p + dirv * L], [0.0028, 0.0016], 3, MAIN, end_tip=0.004)
    # веточки
    for _ in range(45):
        p, n = surf(rand_dir(0.05))
        t = unit(np.cross(n, rng.normal(size=3)))
        L = rng.uniform(0.15, 0.4)
        tube(mb, catmull([p - n * 0.01, p + t * L * 0.5 + n * 0.02, p + t * L], 8), np.linspace(0.01, 0.004, 8), 5, MAIN, end_tip=0.01)
    # входы муравьёв
    for _ in range(9):
        p, n = surf(rand_dir(0.1, 0.8))
        rgt = unit(np.cross(UP, n))
        ellipsoid(mb, p, (rgt, n, unit(np.cross(n, rgt))), (0.06, 0.02, 0.045), DARK, nlat=8, nlon=12)

    # лицо выглядывает из-под муравейника у самой земли: виден лоб, глаза и нос
    p, n = surf(unit([0, -1, 0.15]))
    fwd = unit(np.array([0, -1.0, 0.18]))
    rgt = unit(np.cross(fwd, UP))
    upv = unit(np.cross(rgt, fwd))
    hc = np.array([p[0], p[1] + 0.03, 0.1])
    head(mb, hc, rgt, fwd, upv, (0.2, 0.19, 0.28), opened=True)
    for _ in range(140):   # хвоя осыпается на лицо
        a = rng.uniform(-1.2, 1.2)
        q = hc + rgt * math.sin(a) * 0.2 + upv * rng.uniform(0.15, 0.3) + fwd * math.cos(a) * 0.12
        dirv = unit(rng.normal(size=3))
        tube(mb, [q, q + dirv * rng.uniform(0.04, 0.08)], [0.0028, 0.0016], 3, MAIN, end_tip=0.004)

    # руки: большинство упираются в землю, как паучьи лапы (по два локтя), несколько тянутся вверх
    for k in range(22):
        az = k / 22 * 2 * math.pi + rng.uniform(-0.12, 0.12)
        if abs(math.atan2(math.sin(az + math.pi / 2), math.cos(az + math.pi / 2))) < 0.3:
            continue   # не закрываем лицо спереди
        up_arm = k % 5 == 2
        el = rng.uniform(0.45, 0.85) if up_arm else rng.uniform(0.05, 0.4)
        d = unit([math.cos(az) * math.cos(el), math.sin(az) * math.cos(el), math.sin(el)])
        p, n = surf(d)
        S = p - n * 0.1
        horiz = unit([n[0], n[1], 0])
        side = unit(np.cross(UP, horiz))
        sgn = 1 if rng.random() < 0.5 else -1
        s_ = rng.uniform(0.85, 1.2)
        if up_arm:
            E = S + n * 0.45 * s_ + UP * 0.35 * s_
            W = E + horiz * 0.35 * s_ + UP * 0.12 + side * rng.normal(0, 0.1)
            fdir = arm(mb, [S, E, W], radii=(0.042, 0.032, 0.026))
            hand(mb, W, unit(fdir * 0.3 + np.array([0, 0, -1.0])), side, sgn, k=1.15)
        else:
            E1 = S + horiz * 0.3 * s_ + UP * (0.5 + el * 0.4) * s_ + side * rng.normal(0, 0.06)
            E2 = S + horiz * 0.75 * s_ + UP * 0.32 * s_ + side * rng.normal(0, 0.08)
            W = S + horiz * 1.05 * s_ + side * rng.normal(0, 0.1)
            W[2] = 0.13
            fdir = arm(mb, [S, E1, E2, W], radii=(0.04, 0.032, 0.03, 0.025), n=70)
            hand(mb, W, unit(horiz * 0.9 + np.array([0, 0, -0.8])), side, sgn, k=1.15)
    return mb


# ======================= БЕРЁЗНИК =======================

def build_bereznik():
    rng = np.random.default_rng(8)
    K.rng = rng
    mb = MeshBuilder()
    surfaces = []   # (P, T, N, B, radii, flat) — куда сажать глаза и ленты бересты

    def limb(points, radii, segs=14, flat=1.0, n=60, disp=None):
        P = catmull(points, n)
        r = np.interp(np.linspace(0, 1, n), np.linspace(0, 1, len(radii)), radii)
        res = tube(mb, P, r, segs, MAIN, disp=disp, end_tip=0.0, flat=flat, tile=0.35)
        surfaces.append((*res, r, flat))
        return res

    # ноги
    for s in (-1, 1):
        hip = np.array([s * 0.12, 0.0, 1.78])
        limb([hip, [s * 0.15, -0.04, 1.35], [s * 0.15, -0.09, 0.92], [s * 0.17, -0.02, 0.5], [s * 0.18, 0.03, 0.1]],
             [0.095, 0.08, 0.065, 0.075, 0.055, 0.048, 0.042], n=70)
        ank = np.array([s * 0.18, 0.03, 0.1])
        for t in range(4):   # длинные пальцы-корни
            a = -math.pi / 2 + (t - 1.5) * 0.35 + s * 0.15
            dd = np.array([math.cos(a), math.sin(a), 0])
            L = rng.uniform(0.28, 0.4)
            tube(mb, catmull([ank, ank + dd * L * 0.4 + UP * 0.02, ank + dd * L - UP * 0.09], 12),
                 np.linspace(0.02, 0.006, 12), 6, MAIN, end_tip=0.02)
    # таз и туловище (видны рёбра)
    ellipsoid(mb, (0, 0.0, 1.8), (np.array([1.0, 0, 0]), np.array([0, -1.0, 0]), UP), (0.19, 0.13, 0.14), MAIN, nlat=14, nlon=24)

    def ribs(i, a):
        chest = 25 < i < 62
        return 1.0 + (0.07 * max(0.0, math.sin(i * 0.9)) if chest else 0.0) + 0.02 * math.sin(a * 5 + i * 0.3)
    limb([[0, 0, 1.8], [0, 0.01, 2.15], [0, -0.03, 2.5], [0, -0.06, 2.8], [0, -0.05, 2.92]],
         [0.13, 0.11, 0.15, 0.17, 0.13, 0.08], segs=28, flat=0.62, n=80, disp=ribs)
    limb([[-0.32, -0.04, 2.76], [0, -0.06, 2.83], [0.32, -0.04, 2.76]], [0.04, 0.055, 0.04], n=24)
    # руки до колен
    for s in (-1, 1):
        sh = np.array([s * 0.32, -0.04, 2.76])
        res = limb([sh, [s * 0.37, -0.02, 2.3], [s * 0.4, 0.0, 1.92], [s * 0.39, -0.06, 1.5], [s * 0.37, -0.1, 1.12]],
                   [0.058, 0.045, 0.05, 0.04, 0.034], n=70)
        hand(mb, res[0][-1], unit(res[1][-1]), np.array([0, -1.0, 0]) * s, s, k=1.35)
    # шея ломается набок, голова висит горизонтально
    neck = limb([[0, -0.05, 2.9], [0.0, -0.06, 3.15], [0.08, -0.06, 3.3], [0.3, -0.05, 3.34]], [0.045, 0.04, 0.038, 0.04], n=50)
    hc = np.array([0.5, -0.06, 3.3])
    hup, hfwd = np.array([1.0, 0, -0.18]), np.array([0, -1.0, 0])
    hright = unit(np.cross(hfwd, hup))
    hup = unit(hup)
    ellipsoid(mb, hc, (hright, hfwd, hup), (0.11, 0.12, 0.21), MAIN, nlat=24, nlon=32)
    head_surface_eyes = []
    for j in range(5):   # вертикальный ряд глаз на гладком лице
        w = 0.55 - j * 0.27
        p = hc + hup * 0.21 * w + hfwd * 0.12 * math.sqrt(max(0.05, 1 - w * w)) * 0.98
        head_surface_eyes.append((p, hfwd, hup))

    def eye(p, nrm, along, size):
        nrm, along = unit(nrm), unit(along)
        wide = unit(np.cross(along, nrm))
        ellipsoid(mb, p - nrm * size * 0.15, (wide, nrm, along), (size, size * 0.45, size * 0.38), EYE, nlat=10, nlon=16)
        lid = [p + wide * math.cos(a) * size * 1.25 + along * math.sin(a) * size * 0.6 for a in np.linspace(0, 2 * math.pi, 24)]
        tube(mb, catmull(lid, 40), np.full(40, size * 0.22), 6, DARK, end_tip=0.0)

    for p, nrm, along in head_surface_eyes:
        eye(p, nrm, along, 0.024)
    # глаза-чечевички по всему телу
    for _ in range(60):
        P, T, Ns, Bs, r, flat = surfaces[rng.integers(len(surfaces))]
        i = rng.integers(4, len(P) - 4)
        a = rng.uniform(0, 2 * math.pi)
        dirv = math.cos(a) * Ns[i] + math.sin(a) * Bs[i] * flat
        nrm = unit(math.cos(a) * Ns[i] * flat + math.sin(a) * Bs[i])
        eye(P[i] + dirv * r[i] * 1.02, nrm, T[i], rng.uniform(0.016, 0.03) * (1.4 if r[i] > 0.1 else 1.0))
    # отслоившиеся ленты бересты
    for _ in range(40):
        P, T, Ns, Bs, r, flat = surfaces[rng.integers(len(surfaces))]
        i = rng.integers(4, len(P) - 8)
        a = rng.uniform(0, 2 * math.pi)
        nrm = unit(math.cos(a) * Ns[i] + math.sin(a) * Bs[i])
        start = P[i] + nrm * r[i] * flat
        L = rng.uniform(0.08, 0.22)
        pts = [start + nrm * 0.03 * math.sin(t * 2.6) - T[i] * L * t + nrm * L * 0.25 * t * t for t in np.linspace(0, 1, 7)]
        tube(mb, catmull(pts, 14), np.linspace(0.025, 0.012, 14), 8, MAIN, flat=0.12, end_tip=0.0)
    # плакучие ветки с головы и плеч
    for _ in range(80):
        if rng.random() < 0.75:
            a = rng.uniform(0, 2 * math.pi)
            start = hc + hup * rng.uniform(-0.1, 0.2) + (hright * math.cos(a) * 0.1 + hfwd * math.sin(a) * 0.11)
            if np.dot(start - hc, hfwd) > 0.06:
                continue
        else:
            start = np.array([rng.uniform(-0.3, 0.3), 0.0, 2.8])
        L = rng.uniform(0.3, 1.1)
        sway = rng.normal(0, 0.05, 3)
        sway[2] = 0
        pts = [start + np.array([0, 0, -L * t]) + sway * t * t + UP * 0.08 * math.sin(t * math.pi) for t in np.linspace(0, 1, 9)]
        tube(mb, pts, np.linspace(0.006, 0.002, 9), 5, STRAND, end_tip=0.004)
    return mb


# ======================= КОЧКАРНИК =======================

def build_kochkarnik():
    rng = np.random.default_rng(12)
    K.rng = rng
    mb = MeshBuilder()
    # болотная лепёшка
    rings, segs, Rmax = 36, 96, 2.7
    edge = [1 + 0.12 * math.sin(a * 3 + 1) + 0.07 * math.sin(a * 7) for a in np.linspace(0, 2 * math.pi, segs, endpoint=False)]
    grid = []
    for i in range(rings + 1):
        rr = i / rings
        row = []
        for j in range(segs):
            a = j / segs * 2 * math.pi
            x, y = math.cos(a) * rr * Rmax * edge[j], math.sin(a) * rr * Rmax * edge[j]
            z = 0.05 + 0.03 * math.sin(x * 3.1) * math.sin(y * 2.7) + 0.02 * math.sin(x * 9 + y * 7)
            z -= 0.09 * max(0.0, rr - 0.8) / 0.2
            row.append(mb.add_vert((x, y, z)))
        grid.append(row)
    # пологий край уходит под снег
    skirt = []
    for j in range(segs):
        a = j / segs * 2 * math.pi
        skirt.append(mb.add_vert((math.cos(a) * Rmax * edge[j] * 1.06, math.sin(a) * Rmax * edge[j] * 1.06, -0.06)))
    grid.append(skirt)
    for i in range(rings + 1):
        for j in range(segs):
            j2 = (j + 1) % segs
            q = [grid[i][j], grid[i + 1][j], grid[i + 1][j2], grid[i][j2]]
            mb.add_face(q, [(np.array(mb.verts[v][:2]) / 0.8).tolist() for v in q], MAIN)
    # лужи
    for _ in range(6):
        c = np.append(rng.uniform(-1.8, 1.8, 2), 0.05)
        ellipsoid(mb, c, (np.array([1.0, 0, 0]), np.array([0, 1.0, 0]), UP), (rng.uniform(0.25, 0.55), rng.uniform(0.2, 0.45), 0.012), DARK, nlat=6, nlon=24)

    # головы-кочки: закопаны по нос
    heads = [(np.array([0.0, 0.0]), 1.55, 0.0, True)]
    for k in range(12):
        a = k / 12 * 2 * math.pi + rng.uniform(-0.2, 0.2)
        d = rng.uniform(0.95, 2.0) if k % 2 else rng.uniform(0.75, 1.3)
        yaw = rng.uniform(-0.9, 0.9)
        heads.append((np.array([math.cos(a) * d, math.sin(a) * d]), rng.uniform(0.75, 1.05), yaw, k in (3, 8)))
    for pos, s, yaw, opened in heads:
        radii = np.array([0.11, 0.13, 0.17]) * s
        fwd = np.array([math.sin(yaw), -math.cos(yaw), 0.0])
        fwd = unit(fwd + UP * rng.uniform(0.0, 0.25))   # чуть запрокинута
        rgt = unit(np.cross(fwd, UP))
        upv = unit(np.cross(rgt, fwd))
        center = np.array([pos[0], pos[1], 0.05 + 0.18 * radii[2]])
        head(mb, center, rgt, fwd, upv, radii, opened)
        # осока-волосы: со всей макушки и затылка, свисают на болото
        placed = 0
        while placed < int(70 * s):
            d = unit(rng.normal(size=3))
            if d[2] < 0.2 or np.dot(d, fwd) > -0.15:
                continue
            placed += 1
            start = center + d * radii * 0.96
            out = unit(np.array([d[0], d[1], 0]) + rng.normal(0, 0.25, 3) * np.array([1, 1, 0]))
            hair(mb, start, out, rng.uniform(0.3, 0.6) * s, rng, r0=0.004)

    # длинная рука выползает из грязи и ложится на кочку
    S = np.array([0.9, -0.55, -0.1])
    E = np.array([1.15, -0.95, 0.62])
    W = np.array([0.55, -1.15, 0.2])
    fdir = arm(mb, [S, E, W], radii=(0.055, 0.04, 0.032))
    hand(mb, W, unit(fdir + np.array([0, 0, -0.5])), np.array([0, -1.0, 0]), 1, k=1.35)
    # кисть тянется вверх из лужи
    W2 = np.array([-1.3, -0.6, 0.32])
    tube(mb, catmull([W2 - UP * 0.4, W2 - UP * 0.15, W2], 12), np.linspace(0.036, 0.03, 12), 12, SKIN, end_tip=0.0)
    hand(mb, W2, unit(np.array([0.1, -0.1, 1.0])), np.array([1.0, 0, 0]), 1, k=1.3)
    # кончики пальцев из грязи
    for _ in range(6):
        a, rr = rng.uniform(0, 2 * math.pi), rng.uniform(0.5, 1.6)
        c = np.array([math.cos(a) * rr, math.sin(a) * rr, 0.04])
        base_dir = unit(np.append(rng.normal(size=2), 0))
        for f in range(4):
            b = c + base_dir * (f - 1.5) * 0.03
            curl = unit(UP + base_dir * 0.4 + rng.normal(0, 0.15, 3))
            tip = b + curl * rng.uniform(0.05, 0.11)
            tube(mb, [b - UP * 0.03, (b + tip) / 2 + base_dir * 0.01, tip], [0.011, 0.01, 0.008], 8, SKIN, end_tip=0.007)
    return mb


# ======================= материалы, экспорт, рендер =======================

def materials(name, tex):
    K.TEX = tex
    P = K.principled
    skin = P(f"{name}_Skin", albedo=f"{name}_Skin_Albedo.png", normal=f"{name}_Skin_Normal.png", rough=0.55, sss=0.25)
    if name == "Muravejnik":
        return [P("Muravejnik_Needles", albedo="Muravejnik_Needles_Albedo.png", normal="Muravejnik_Needles_Normal.png", rough=0.85),
                skin, P("Muravejnik_Strand", color=(0.3, 0.2, 0.1), rough=0.9),
                P("Muravejnik_Hole", color=(0.01, 0.006, 0.004), rough=0.9),
                P("Muravejnik_Eye", color=(0.62, 0.6, 0.52), rough=0.05, coat=1.0)]
    if name == "Bereznik":
        return [P("Bereznik_Birch", albedo="Bereznik_Birch_Albedo.png", normal="Bereznik_Birch_Normal.png", rough=0.7),
                skin, P("Bereznik_Twigs", color=(0.05, 0.025, 0.018), rough=0.8),
                P("Bereznik_Lid", color=(0.02, 0.018, 0.016), rough=0.6),
                P("Bereznik_Eye", color=(0.01, 0.01, 0.012), rough=0.02, coat=1.0)]
    return [P("Kochkarnik_Mud", albedo="Kochkarnik_Mud_Albedo.png", normal="Kochkarnik_Mud_Normal.png", rough=0.45),
            skin, P("Kochkarnik_Sedge", color=(0.42, 0.35, 0.17), rough=0.85),
            P("Kochkarnik_Water", color=(0.012, 0.016, 0.012), rough=0.5),
            P("Kochkarnik_Eye", color=(0.5, 0.53, 0.47), rough=0.05, coat=1.0)]


MONSTERS = {
    # имя: (строитель, цель камеры, дистанция, высота камеры, крупный план (цель, угол, дистанция, высота))
    "Muravejnik": (build_muravejnik, (0, 0, 0.85), 7.0, 2.6, ((0, -1.3, 0.3), 12, 1.5, 0.75)),
    "Bereznik": (build_bereznik, (0, 0, 1.8), 6.4, 2.2, ((0.3, -0.1, 3.05), 25, 2.0, 3.1)),
    "Kochkarnik": (build_kochkarnik, (0, -0.2, 0.15), 6.5, 3.4, ((0, -0.3, 0.25), 10, 1.8, 0.9)),
}


def make_object(name, mb, mats):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(mb.verts, [], mb.faces)
    uv = mesh.uv_layers.new(name="UVMap")
    uv.data.foreach_set("uv", np.asarray(mb.uvs, dtype=np.float32).ravel())
    mesh.polygons.foreach_set("material_index", np.asarray(mb.mats, dtype=np.int32))
    mesh.polygons.foreach_set("use_smooth", np.ones(len(mb.faces), dtype=bool))
    mesh.validate()
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    for m in mats:
        mesh.materials.append(m)
    return obj


def export(obj, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, apply_scale_options="FBX_SCALE_ALL",
                             axis_forward="-Z", axis_up="Y", bake_space_transform=True, mesh_smooth_type="FACE",
                             use_tspace=True, path_mode="RELATIVE", embed_textures=False, add_leaf_bones=False)


def run(root, name, render, quick=False):
    builder, target, dist, height, close = MONSTERS[name]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    folder = os.path.join(root, name)
    mb = builder()
    obj = make_object(name, mb, materials(name, os.path.join(folder, "Textures")))
    print(f"{name}: {len(mb.verts)} вершин, {sum(len(f) - 2 for f in mb.faces)} треугольников")
    export(obj, os.path.join(folder, "Model", f"{name}.fbx"))
    if not render:
        return
    cam = K.setup_scene()
    sc = bpy.context.scene
    prev = os.path.join(folder, "Previews")
    os.makedirs(prev, exist_ok=True)
    sc.cycles.samples = 16 if quick else 64
    sc.render.resolution_x, sc.render.resolution_y = (480, 640) if quick else (720, 960)
    for view, ang in (("front", 0), ("three_quarter", 40), ("side", 90), ("back", 180), ("left", 270)):
        K.look_at(cam, target, ang, dist=dist, height=height)
        sc.render.filepath = os.path.join(prev, f"{name}_{view}.png")
        bpy.ops.render.render(write_still=True)
    ct, ca, cd, ch = close
    K.look_at(cam, ct, ca, dist=cd, height=ch)
    sc.render.filepath = os.path.join(prev, f"{name}_closeup.png")
    bpy.ops.render.render(write_still=True)
    if quick:
        return
    turn = os.path.join(os.environ.get("MONSTER_TURNTABLE", prev), name)
    os.makedirs(turn, exist_ok=True)
    sc.cycles.samples = 20
    sc.render.resolution_x, sc.render.resolution_y = 360, 480
    for k in range(18):
        K.look_at(cam, target, k * 20, dist=dist, height=height)
        sc.render.filepath = os.path.join(turn, f"t_{k:02d}.png")
        bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    root = os.path.abspath(args[0] if args else "unity")
    names = args[1:] or list(MONSTERS)
    for nm in names:
        run(root, nm, "--no-render" not in sys.argv, quick="--quick" in sys.argv)
