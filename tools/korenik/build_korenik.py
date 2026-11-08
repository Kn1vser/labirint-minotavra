"""«Корневик» — таёжный монстр. Строит модель в Blender, рендерит превью, экспортирует FBX.

Запуск (нужен пакет bpy: pip install bpy numpy):
    python build_korenik.py <папка unity/Korenik> [--no-render]

Что это: сухостойная ель, вставшая на корни, как паук. Вместо головы — сломанная
верхушка. Посреди ствола — вертикальная пасть с зубами-щепками. Выше, в коре,
вросшее человеческое лицо с закрытыми глазами. Руки-ветви длиной до земли
заканчиваются бледными человеческими кистями. В коре моргают глаза-сучки.
С веток свисает лишайник-бородач.
"""
import math
import os
import sys

import bpy
import numpy as np

OUT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "unity/Korenik")
RENDER = "--no-render" not in sys.argv
TEX = os.path.join(OUT, "Textures")
rng = np.random.default_rng(1977)

BARK, SKIN, LICHEN, DARK, EYE = range(5)


# ======================= геометрия =======================

class MeshBuilder:
    def __init__(self):
        self.verts = []
        self.faces = []
        self.uvs = []      # по одному UV на угол грани
        self.mats = []

    def add_vert(self, p):
        self.verts.append(tuple(float(c) for c in p))
        return len(self.verts) - 1

    def add_face(self, idx, uv, mat):
        self.faces.append(tuple(idx))
        self.uvs.extend(uv)
        self.mats.append(mat)


def catmull(points, n):
    """Гладкая кривая через контрольные точки, n точек, равномерно по длине."""
    P = np.asarray(points, dtype=float)
    P = np.vstack([2 * P[0] - P[1], P, 2 * P[-1] - P[-2]])
    dense = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for t in np.linspace(0, 1, 24, endpoint=False):
            t2, t3 = t * t, t * t * t
            dense.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    dense.append(P[-2])
    dense = np.array(dense)
    seg = np.linalg.norm(np.diff(dense, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    target = np.linspace(0, s[-1], n)
    return np.stack([np.interp(target, s, dense[:, k]) for k in range(3)], axis=1)


def frames(P, up_hint=None):
    T = np.gradient(P, axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True) + 1e-12
    hint = np.array(up_hint if up_hint is not None else [0.0, 0.0, 1.0])
    if abs(np.dot(hint, T[0])) > 0.9:
        hint = np.array([1.0, 0.0, 0.0])
    Nv = np.cross(T[0], hint)
    Nv /= np.linalg.norm(Nv)
    Ns, Bs = [], []
    for t in T:
        Nv = Nv - np.dot(Nv, t) * t
        Nv /= np.linalg.norm(Nv) + 1e-12
        Ns.append(Nv.copy())
        Bs.append(np.cross(t, Nv))
    return T, np.array(Ns), np.array(Bs)


def tube(mb, P, radii, segs, mat, disp=None, start_cap=False, end_tip=None, tile=0.5, flat=1.0, up_hint=None):
    """Труба вдоль кривой P. disp(i, angle) -> множитель радиуса. end_tip — длина острого кончика."""
    P = np.asarray(P, float)
    radii = np.asarray(radii, float)
    T, Ns, Bs = frames(P, up_hint)
    n = len(P)
    seg_len = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    r_avg = max(float(radii.mean()), 1e-3)
    U = max(1, round(2 * math.pi * r_avg / tile))
    angles = np.linspace(0, 2 * math.pi, segs, endpoint=False)

    rings = []
    for i in range(n):
        ring = []
        for a in angles:
            k = disp(i, a) if disp else 1.0
            r = radii[i] * k
            p = P[i] + r * (math.cos(a) * Ns[i] + math.sin(a) * Bs[i] * flat)
            ring.append(mb.add_vert(p))
        rings.append(ring)

    for i in range(n - 1):
        v0, v1 = seg_len[i] / tile, seg_len[i + 1] / tile
        for k in range(segs):
            k2 = (k + 1) % segs
            u0, u1 = k / segs * U, (k + 1) / segs * U
            mb.add_face([rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k]],
                        [(u0, v0), (u1, v0), (u1, v1), (u0, v1)], mat)

    if start_cap:
        c = mb.add_vert(P[0] - T[0] * radii[0] * 0.3)
        for k in range(segs):
            k2 = (k + 1) % segs
            mb.add_face([rings[0][k2], rings[0][k], c], [(0.5 + 0.5 * math.cos(angles[k2]), 0.5 + 0.5 * math.sin(angles[k2])),
                                                         (0.5 + 0.5 * math.cos(angles[k]), 0.5 + 0.5 * math.sin(angles[k])), (0.5, 0.5)], mat)
    tip_len = end_tip if end_tip is not None else radii[-1] * 0.6
    c = mb.add_vert(P[-1] + T[-1] * tip_len)
    vtip = seg_len[-1] / tile + tip_len / tile
    for k in range(segs):
        k2 = (k + 1) % segs
        mb.add_face([rings[-1][k], rings[-1][k2], c],
                    [(k / segs * U, seg_len[-1] / tile), ((k + 1) / segs * U, seg_len[-1] / tile), ((k + 0.5) / segs * U, vtip)], mat)
    return P, T, Ns, Bs


def ellipsoid(mb, center, axes, radii, mat, nlat=16, nlon=24, shape=None, lon_range=(-math.pi, math.pi), closed=True):
    """Эллипсоид в локальном базисе axes=(right, forward, up). shape(u, w) -> добавка вдоль forward."""
    ex, ef, ez = (np.asarray(a, float) for a in axes)
    a, b, c = radii
    grid = []
    lats = np.linspace(-math.pi / 2, math.pi / 2, nlat + 1)
    lons = np.linspace(lon_range[0], lon_range[1], nlon + (0 if closed else 1), endpoint=not closed)
    for la in lats:
        row = []
        for lo in lons:
            x = a * math.sin(lo) * math.cos(la)
            y = b * math.cos(lo) * math.cos(la)
            z = c * math.sin(la)
            if shape:
                y += shape(x / a, z / c) * b * max(0.0, math.cos(lo))
            row.append(mb.add_vert(np.asarray(center) + ex * x + ef * y + ez * z))
        grid.append(row)
    cols = len(lons)
    for i in range(nlat):
        for j in range(cols if closed else cols - 1):
            j2 = (j + 1) % cols
            uv = [(j / cols, i / nlat), (j2 / cols if j2 else 1.0, i / nlat), (j2 / cols if j2 else 1.0, (i + 1) / nlat), (j / cols, (i + 1) / nlat)]
            mb.add_face([grid[i][j], grid[i][j2], grid[i + 1][j2], grid[i + 1][j]], uv, mat)


def gauss(x, s):
    return math.exp(-(x * x) / (2 * s * s))


def wobble(points, amount):
    pts = np.asarray(points, float).copy()
    pts[1:] += rng.normal(0, amount, pts[1:].shape)
    return pts


def bark_disp(ridges, depth, seed):
    ph = rng.uniform(0, 6.28, 4)
    knots = rng.uniform(0, 1, 3)

    def f(i, a):
        r = 1.0
        r += depth * (abs(math.sin(a * ridges * 0.5 + ph[0] + i * 0.02)) - 0.5)
        r += depth * 0.5 * math.sin(a * 3 + ph[1] + i * 0.11) * math.sin(i * 0.17 + ph[2])
        r += 0.03 * math.sin(a * 11 + i * 0.7 + ph[3])
        return r
    return f


# ======================= монстр =======================

def build():
    mb = MeshBuilder()
    up = np.array([0.0, 0.0, 1.0])

    # --- Ствол-туловище: сутулится вперёд (фронт = -Y) ---
    trunk_ctrl = [(0, 0.05, 0.55), (0, 0.04, 1.2), (0.02, -0.04, 1.9), (0.0, -0.18, 2.5), (-0.03, -0.34, 2.95), (-0.04, -0.4, 3.12)]
    TP = catmull(trunk_ctrl, 150)
    t = np.linspace(0, 1, 150)
    trunk_r = 0.34 - 0.16 * t + 0.05 * np.exp(-((t - 0.05) / 0.08) ** 2) + 0.025 * np.exp(-((t - 0.45) / 0.05) ** 2)
    TP, TT, TN, TB = tube(mb, TP, trunk_r, 56, BARK, disp=bark_disp(14, 0.16, 0), start_cap=True, end_tip=0.02)

    def trunk_surface(frac, angle, push=1.0):
        """Точка на поверхности ствола. angle=0 — вперёд (-Y)."""
        i = int(frac * (len(TP) - 1))
        fwd = np.array([0, -1.0, 0])
        side = np.cross(TT[i], fwd)
        side /= np.linalg.norm(side)
        front = np.cross(side, TT[i])
        d = math.cos(angle) * front + math.sin(angle) * side
        return TP[i] + d * trunk_r[i] * push, d, TT[i], i

    # --- Сломанная верхушка: щепки торчат вверх ---
    top = TP[-1]
    for k in range(9):
        a = k / 9 * 2 * math.pi + rng.uniform(-0.2, 0.2)
        base = top + np.array([math.cos(a), math.sin(a), 0]) * trunk_r[-1] * 0.85 - TT[-1] * 0.05
        h = rng.uniform(0.12, 0.42)
        tipp = base + TT[-1] * h + np.array([math.cos(a), math.sin(a), 0]) * h * 0.25
        tube(mb, catmull([base, (base + tipp) / 2, tipp], 6), np.linspace(0.045, 0.012, 6), 6, BARK, end_tip=0.03)

    # --- Корни-ноги: 9 штук, как у паука ---
    n_roots = 9
    for k in range(n_roots):
        a = k / n_roots * 2 * math.pi + rng.uniform(-0.15, 0.15)
        d = np.array([math.cos(a), math.sin(a), 0])
        reach = rng.uniform(1.5, 2.1)
        knee_h = rng.uniform(1.05, 1.45)
        ctrl = [np.array([0, 0.04, 0.75]) + d * 0.12,
                np.array([0, 0.04, 0.85]) + d * 0.45 + up * 0.15,
                d * (reach * 0.5) + up * knee_h,
                d * (reach * 0.82) + up * (knee_h * 0.55),
                d * reach + up * 0.0]
        P = catmull(wobble(ctrl, 0.04), 70)
        tt = np.linspace(0, 1, 70)
        r = 0.13 * (1 - tt) ** 0.9 + 0.022 + 0.018 * np.exp(-((tt - 0.42) / 0.04) ** 2)  # «колено»-сучок
        tube(mb, P, r, 14, BARK, disp=bark_disp(6, 0.12, k), end_tip=0.05)
        # тонкие корешки у «стопы»
        foot = P[-6]
        for j in range(3):
            b = a + rng.uniform(-0.9, 0.9)
            dd = np.array([math.cos(b), math.sin(b), 0])
            L = rng.uniform(0.25, 0.5)
            pts = [foot, foot + dd * L * 0.5 + up * 0.02, foot + dd * L - up * 0.03]
            tube(mb, catmull(wobble(pts, 0.015), 10), np.linspace(0.022, 0.006, 10), 6, BARK, end_tip=0.02)

    # --- Руки-ветви до земли с человеческими кистями ---
    lichen_sources = []
    for side in (-1, 1):
        sh, sd, _, _ = trunk_surface(0.8, side * 1.45, 0.8)
        elbow = sh + np.array([side * 0.55, -0.25, -0.35])
        wrist = np.array([side * 0.78, -0.75, 0.78])
        ctrl = [sh, sh + np.array([side * 0.25, -0.05, 0.08]), elbow, (elbow + wrist) / 2 + np.array([side * 0.08, 0, 0]), wrist]
        P = catmull(wobble(ctrl, 0.03), 80)
        tt = np.linspace(0, 1, 80)
        r = 0.1 * (1 - tt) + 0.02 + 0.02 * np.exp(-((tt - 0.38) / 0.04) ** 2)
        AP, AT, _, _ = tube(mb, P, r, 14, BARK, disp=bark_disp(6, 0.14, side), end_tip=0.0)
        lichen_sources.append((AP[:55], r[:55]))

        # Предплечье переходит в бледную кожу
        fstart = AP[50]
        fdir = AT[-1]
        fend = wrist + fdir * 0.06
        sk = catmull([fstart, (fstart + fend) / 2, fend], 20)
        tube(mb, sk, np.linspace(0.045, 0.034, 20), 16, SKIN, end_tip=0.0)
        # рваный край коры вокруг кожи
        for j in range(7):
            a = j / 7 * 2 * math.pi
            _, Nn, Bb = frames(sk)
            base = sk[3] + (math.cos(a) * Nn[3] + math.sin(a) * Bb[3]) * 0.05
            tipp = base + fdir * rng.uniform(0.06, 0.14) + (math.cos(a) * Nn[3] + math.sin(a) * Bb[3]) * 0.015
            tube(mb, [base, (base + tipp) / 2, tipp], [0.016, 0.01, 0.004], 5, BARK, end_tip=0.01)

        hand(mb, fend, fdir, np.array([side * 1.0, 0.25 * side, 0.0]), side)

    # --- Сухие сучья на стволе ---
    for k in range(7):
        frac = rng.uniform(0.35, 0.92)
        ang = rng.uniform(0.9, 5.4)
        base, d, T, _ = trunk_surface(frac, ang, 0.85)
        L = rng.uniform(0.35, 0.8)
        dirv = d * 0.8 + T * 0.55 + rng.normal(0, 0.15, 3)
        dirv /= np.linalg.norm(dirv)
        ctrl = [base, base + dirv * L * 0.5 + rng.normal(0, 0.04, 3), base + dirv * L + up * 0.05]
        P = catmull(ctrl, 18)
        rr = np.linspace(0.05, 0.012, 18)
        tube(mb, P, rr, 8, BARK, end_tip=0.03)
        lichen_sources.append((P, rr))
        for j in range(2):
            m = P[rng.integers(6, 14)]
            dd = dirv + rng.normal(0, 0.6, 3)
            dd /= np.linalg.norm(dd)
            l2 = rng.uniform(0.12, 0.3)
            tube(mb, catmull([m, m + dd * l2 * 0.5, m + dd * l2 + up * 0.03], 8), np.linspace(0.018, 0.005, 8), 5, BARK, end_tip=0.015)

    # --- Вросшее лицо ---
    fc, fd, fT, fi = trunk_surface(0.85, 0.0, 0.72)
    right = np.cross(fT, fd)
    right /= np.linalg.norm(right)
    fwd = fd * 0.92 - fT * 0.25   # чуть смотрит вниз
    fwd /= np.linalg.norm(fwd)
    upf = np.cross(fwd, right)
    upf = -upf if upf[2] < 0 else upf
    ellipsoid(mb, fc, (right, fwd, upf), (0.145, 0.13, 0.205), SKIN, nlat=110, nlon=100, shape=face_shape,
              lon_range=(-1.75, 1.75), closed=False)
    # кора наползает на края лица
    rim = []
    for j in range(40):
        a = j / 40 * 2 * math.pi
        rim.append(fc + right * math.cos(a) * 0.17 + upf * math.sin(a) * 0.235 + fwd * 0.035)
    rim.append(rim[0])
    rimP = catmull(rim, 90)
    tube(mb, rimP, 0.03 + 0.012 * np.sin(np.linspace(0, 23, 90)) ** 2, 10, BARK, disp=bark_disp(4, 0.2, 9), end_tip=0.0)

    # --- Вертикальная пасть в груди ---
    mc, md, mT, _ = trunk_surface(0.52, 0.0, 0.93)
    mr = np.cross(mT, md)
    mr /= np.linalg.norm(mr)
    ellipsoid(mb, mc, (mr, md, mT), (0.085, 0.055, 0.27), DARK, nlat=16, nlon=20)
    lip = []
    for j in range(36):
        a = j / 36 * 2 * math.pi
        lip.append(mc + mr * math.cos(a) * 0.1 + mT * math.sin(a) * 0.29 + md * 0.015)
    lip.append(lip[0])
    lipP = catmull(lip, 80)
    tube(mb, lipP, 0.035 + 0.01 * np.sin(np.linspace(0, 17, 80)), 10, BARK, disp=bark_disp(4, 0.25, 7), end_tip=0.0)
    for j in range(34):
        a = j / 34 * 2 * math.pi + rng.uniform(-0.05, 0.05)
        edge = mc + mr * math.cos(a) * 0.095 + mT * math.sin(a) * 0.27 + md * 0.01
        inward = (mc - edge)
        inward /= np.linalg.norm(inward)
        L = rng.uniform(0.06, 0.14) * (1.3 if abs(math.cos(a)) > 0.5 else 1.0)
        tipp = edge + inward * L + md * 0.02
        tube(mb, [edge - inward * 0.01, edge + inward * L * 0.5, tipp], [0.02, 0.012, 0.003], 6, SKIN, end_tip=0.008)

    # --- Глаза-сучки в коре ---
    for frac, ang in ((0.62, 0.9), (0.7, -1.1), (0.4, 2.3), (0.78, 2.9), (0.33, -2.1), (0.57, -0.55), (0.9, 1.6)):
        c, d, T, _ = trunk_surface(frac, ang, 1.0)
        rr = np.cross(T, d)
        rr /= np.linalg.norm(rr)
        ellipsoid(mb, c, (rr, d, T), (0.03, 0.025, 0.022), EYE, nlat=10, nlon=14)
        lid = [c + rr * math.cos(a) * 0.036 + T * math.sin(a) * 0.026 + d * 0.006 for a in np.linspace(0, 2 * math.pi, 20)]
        tube(mb, catmull(lid, 40), np.full(40, 0.012), 6, BARK, end_tip=0.0)

    # --- Лишайник-бородач ---
    lichen_sources.append((TP[125:], trunk_r[125:]))
    for _ in range(340):
        P, R = lichen_sources[rng.integers(len(lichen_sources))]
        i = rng.integers(0, len(P))
        start = P[i] + rng.normal(0, 1, 3) * R[i] * 0.6
        start[2] -= R[i] * 0.5
        L = rng.uniform(0.08, 0.55)
        n = 10
        sway = rng.normal(0, 0.05, 3)
        sway[2] = 0
        pts = [start + np.array([0, 0, -L * j / (n - 1)]) + sway * (j / (n - 1)) ** 1.5
               + np.array([math.sin(j * 1.3 + i), math.cos(j * 1.7 + i), 0]) * 0.008 for j in range(n)]
        tube(mb, pts, np.linspace(0.0035, 0.001, n), 4, LICHEN, end_tip=0.004)

    return mb


def face_shape(u, w):
    """Рельеф лица на передней половине эллипсоида. u — вправо, w — вверх, в диапазоне -1..1."""
    h = 0.0
    for sx in (-1, 1):
        ex = u - sx * 0.34
        h -= 0.55 * gauss(math.hypot(ex, (w - 0.14) * 1.25), 0.17)         # глубокие глазницы
        h += 0.30 * gauss(math.hypot(ex * 1.1, (w - 0.12) * 1.8), 0.1)     # выпуклые закрытые веки
        h -= 0.07 * gauss(ex, 0.12) * gauss(w - 0.08, 0.018)               # линия смыкания век
        h += 0.10 * gauss(math.hypot(u - sx * 0.55, w + 0.18), 0.17)       # скулы
        h -= 0.18 * gauss(math.hypot(u - sx * 0.5, w + 0.42), 0.15)        # впалые щёки
        h -= 0.09 * gauss(math.hypot(u - sx * 0.12, w + 0.27), 0.04)       # ноздри
        h -= 0.05 * gauss(u - sx * 0.3, 0.05) * gauss(w + 0.48, 0.05)      # уголки рта
    h += 0.16 * gauss(w - 0.36, 0.07) * gauss(u, 0.5)                       # надбровье
    nose = gauss(u, 0.08) * (1 / (1 + math.exp(-(w + 0.2) * 25))) * (1 / (1 + math.exp((w - 0.3) * 25)))
    h += 0.5 * nose * (0.5 + 0.5 * (0.3 - w) / 0.5)                         # спинка носа
    h += 0.16 * gauss(math.hypot(u, w + 0.2), 0.09)                         # кончик носа
    h -= 0.06 * gauss(u, 0.05) * gauss(w + 0.37, 0.04)                      # желобок над губой
    h += 0.10 * gauss(u, 0.28) * gauss(w + 0.44, 0.04)                      # верхняя губа
    h -= 0.14 * gauss(u, 0.26) * gauss(w + 0.5, 0.02)                       # щель рта
    h += 0.12 * gauss(u, 0.24) * gauss(w + 0.57, 0.04)                      # нижняя губа
    h -= 0.08 * gauss(u, 0.2) * gauss(w + 0.67, 0.04)
    h += 0.14 * gauss(u, 0.28) * gauss(w + 0.82, 0.08)                      # подбородок
    return h


def hand(mb, wrist, d, w, side, k=1.6):
    """Бледная человеческая кисть, свисает вниз. Крупнее человеческой (k),
    и в каждом пальце на одну фалангу больше, чем надо."""
    d = d / np.linalg.norm(d)
    w = w - np.dot(w, d) * d
    w /= np.linalg.norm(w)
    nrm = np.cross(d, w) * side            # сторона ладони
    palm_end = wrist + d * 0.12 * k
    palm_r = np.array([0.034, 0.04, 0.046, 0.05, 0.052, 0.053, 0.053, 0.052, 0.05, 0.046]) * k
    tube(mb, catmull([wrist - d * 0.02, wrist + d * 0.06 * k, palm_end], 10), palm_r,
         16, SKIN, flat=0.42, end_tip=0.012 * k, up_hint=nrm)
    for f in range(4):
        off = (f - 1.5) * 0.026 * k
        base = palm_end + w * off - d * 0.012 * k
        L = [0.075, 0.065, 0.06, 0.05][f] * 1.25 * k
        pts = [base]
        dirv = d + w * off * 1.5 / k
        dirv /= np.linalg.norm(dirv)
        curl = rng.uniform(0.2, 0.42)
        for j in range(4):   # четыре фаланги вместо трёх
            dirv = dirv * math.cos(curl) + nrm * math.sin(curl)
            dirv /= np.linalg.norm(dirv)
            pts.append(pts[-1] + dirv * L)
        P = catmull(pts, 22)
        tt = np.linspace(0, 1, 22)
        r = (0.011 - 0.004 * tt + 0.0022 * np.sin(tt * math.pi * 4) ** 8) * k   # костяшки
        tube(mb, P, r, 8, SKIN, end_tip=0.008 * k)
        # длинный тёмный ноготь
        tip = P[-1]
        tdir = P[-1] - P[-2]
        tdir /= np.linalg.norm(tdir)
        tube(mb, [tip - tdir * 0.01 * k, tip + tdir * 0.015 * k, tip + tdir * 0.035 * k], np.array([0.006, 0.005, 0.002]) * k,
             6, DARK, end_tip=0.006 * k)
    # большой палец
    base = wrist + d * 0.05 * k + w * (-0.04 * k) + nrm * 0.015 * k
    tdir = d * 0.6 - w * 0.6 + nrm * 0.4
    tdir /= np.linalg.norm(tdir)
    pts = [base, base + tdir * 0.06 * k, base + tdir * 0.11 * k + d * 0.03 * k, base + tdir * 0.14 * k + d * 0.08 * k]
    tube(mb, catmull(pts, 14), np.linspace(0.014, 0.009, 14) * k, 8, SKIN, end_tip=0.006 * k)


# ======================= Blender: меш, материалы =======================

def make_object(mb):
    mesh = bpy.data.meshes.new("Korenik")
    mesh.from_pydata(mb.verts, [], mb.faces)
    uv = mesh.uv_layers.new(name="UVMap")
    uv.data.foreach_set("uv", np.asarray(mb.uvs, dtype=np.float32).ravel())
    mesh.polygons.foreach_set("material_index", np.asarray(mb.mats, dtype=np.int32))
    mesh.polygons.foreach_set("use_smooth", np.ones(len(mb.faces), dtype=bool))
    mesh.validate()
    mesh.update()
    obj = bpy.data.objects.new("Korenik", mesh)
    bpy.context.scene.collection.objects.link(obj)
    for m in materials():
        mesh.materials.append(m)
    return obj


def img(name, non_color=False):
    im = bpy.data.images.load(os.path.join(TEX, name))
    if non_color:
        im.colorspace_settings.name = "Non-Color"
    return im


def principled(name, color=None, albedo=None, normal=None, rough=0.8, normal_strength=1.0, coat=0.0, sss=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = rough
    if color:
        bsdf.inputs["Base Color"].default_value = (*color, 1)
    if albedo:
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = img(albedo)
        nt.links.new(t.outputs["Color"], bsdf.inputs["Base Color"])
    if normal:
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = img(normal, True)
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nm.inputs["Strength"].default_value = normal_strength
        nt.links.new(t.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    if coat:
        bsdf.inputs["Coat Weight"].default_value = coat
    if sss:
        bsdf.inputs["Subsurface Weight"].default_value = sss
        bsdf.inputs["Subsurface Radius"].default_value = (0.4, 0.2, 0.15)
        bsdf.inputs["Subsurface Scale"].default_value = 0.02
    return mat


def materials():
    return [
        principled("Korenik_Bark", albedo="Korenik_Bark_Albedo.png", normal="Korenik_Bark_Normal.png", rough=0.9, normal_strength=1.4),
        principled("Korenik_Skin", albedo="Korenik_Skin_Albedo.png", normal="Korenik_Skin_Normal.png", rough=0.55, sss=0.25),
        principled("Korenik_Lichen", color=(0.30, 0.34, 0.25), rough=0.95),
        principled("Korenik_Maw", color=(0.008, 0.003, 0.003), rough=0.15, coat=1.0),
        principled("Korenik_Eye", color=(0.32, 0.17, 0.03), rough=0.05, coat=1.0),
    ]


# ======================= рендер превью =======================

def setup_scene():
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 64
    sc.cycles.use_denoising = True
    sc.render.film_transparent = False
    sc.view_settings.view_transform = "AgX"
    for look in ("AgX - Medium High Contrast", "Medium High Contrast"):
        try:
            sc.view_settings.look = look
            break
        except TypeError:
            pass

    world = bpy.data.worlds.new("Taiga")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.045, 0.055, 0.07, 1)
    bg.inputs["Strength"].default_value = 1.6
    sc.world = world

    # снег
    bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, 0))
    ground = bpy.context.active_object
    gm = principled("Snow", color=(0.62, 0.66, 0.70), rough=0.7)
    ground.data.materials.append(gm)

    # ели на фоне — по кругу, чтобы было видно с любой стороны
    tree_mat = principled("Spruce", color=(0.02, 0.035, 0.03), rough=0.9)
    for k in range(26):
        a = k / 26 * 2 * math.pi + rng.uniform(-0.1, 0.1)
        dist = rng.uniform(9, 15)
        h = rng.uniform(7, 12)
        x, y = math.cos(a) * dist, math.sin(a) * dist
        for tier in range(5):
            bpy.ops.mesh.primitive_cone_add(vertices=10, radius1=h * 0.2 * (1 - tier * 0.16), depth=h * 0.35,
                                            location=(x, y, h * 0.2 + tier * h * 0.16))
            bpy.context.active_object.data.materials.append(tree_mat)

    # лунный свет + холодный контровой + слабый тёплый снизу (как от фонаря)
    def light(kind, loc, energy, color, rot=None, size=None):
        bpy.ops.object.light_add(type=kind, location=loc)
        L = bpy.context.active_object
        L.data.energy = energy
        L.data.color = color
        if size:
            L.data.size = size
        if rot:
            L.rotation_euler = rot
        return L

    from mathutils import Vector

    def aim(L, target=(0, 0, 1.5)):
        L.rotation_euler = (Vector(target) - L.location).to_track_quat("-Z", "Y").to_euler()

    light("SUN", (0, 0, 10), 1.2, (0.7, 0.8, 1.0), rot=(math.radians(50), 0, math.radians(30)))
    aim(light("AREA", (3.5, -4.5, 4.0), 900, (0.85, 0.9, 1.0), size=3))      # ключевой спереди-справа
    aim(light("AREA", (-3.0, 4.0, 3.5), 1100, (0.6, 0.75, 1.0), size=3))     # сзади-слева
    aim(light("AREA", (4.0, 3.0, 2.0), 500, (0.75, 0.85, 1.0), size=2))      # сзади-справа
    aim(light("AREA", (0, 0.5, 6.5), 300, (0.7, 0.8, 1.0), size=2))          # сверху
    light("POINT", (-0.8, -2.0, 0.6), 60, (1.0, 0.7, 0.45))                  # тёплый снизу, как от фонаря

    cam_data = bpy.data.cameras.new("Cam")
    cam_data.lens = 45
    cam = bpy.data.objects.new("Cam", cam_data)
    sc.collection.objects.link(cam)
    sc.camera = cam
    return cam


def look_at(cam, target, angle_deg, dist=7.0, height=1.8):
    a = math.radians(angle_deg)
    cam.location = (target[0] + math.sin(a) * dist, target[1] - math.cos(a) * dist, height)
    d = np.array(target) - np.array(cam.location)
    from mathutils import Vector
    cam.rotation_euler = Vector(d).to_track_quat("-Z", "Y").to_euler()


def render_views(cam):
    sc = bpy.context.scene
    prev = os.path.join(OUT, "Previews")
    os.makedirs(prev, exist_ok=True)
    target = (0, -0.1, 1.55)
    views = [("front", 0), ("three_quarter", 40), ("side", 90), ("back", 180), ("left", 270)]
    sc.render.resolution_x, sc.render.resolution_y = 720, 960
    for name, ang in views:
        look_at(cam, target, ang)
        sc.render.filepath = os.path.join(prev, f"Korenik_{name}.png")
        bpy.ops.render.render(write_still=True)

    # крупный план лица и пасти
    look_at(cam, (0, -0.35, 2.3), 15, dist=2.2, height=2.45)
    sc.render.filepath = os.path.join(prev, "Korenik_face.png")
    bpy.ops.render.render(write_still=True)

    # круговой облёт для GIF
    turn = os.environ.get("KORENIK_TURNTABLE", os.path.join(OUT, "_turntable"))
    os.makedirs(turn, exist_ok=True)
    sc.cycles.samples = 24
    sc.render.resolution_x, sc.render.resolution_y = 360, 480
    for k in range(24):
        look_at(cam, target, k * 15)
        sc.render.filepath = os.path.join(turn, f"t_{k:02d}.png")
        bpy.ops.render.render(write_still=True)


def export(obj):
    model_dir = os.path.join(OUT, "Model")
    os.makedirs(model_dir, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.fbx(
        filepath=os.path.join(model_dir, "Korenik.fbx"),
        use_selection=True,
        apply_scale_options="FBX_SCALE_ALL",
        axis_forward="-Z", axis_up="Y",
        bake_space_transform=True,
        mesh_smooth_type="FACE",
        use_tspace=True,
        path_mode="RELATIVE",
        embed_textures=False,
        add_leaf_bones=False,
    )


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    mb = build()
    obj = make_object(mb)
    tris = sum(len(f) - 2 for f in mb.faces)
    print(f"Корневик: {len(mb.verts)} вершин, {tris} треугольников")
    export(obj)
    if RENDER:
        cam = setup_scene()
        render_views(cam)


if __name__ == "__main__":
    main()
