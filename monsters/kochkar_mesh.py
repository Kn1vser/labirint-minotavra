"""
Геометрия «Кочкаря» — ходячей таёжной кочки на ногах-корнях.

Всё в метрах, перёд смотрит в +z. Общие инструменты (loft, ellipsoid, MeshData)
берём из frost_mesh, здесь добавляем трубки по произвольной кривой (корни,
ветки, пальцы) и ель.
"""
import math

import numpy as np

from .frost_mesh import MeshData, PartSpec, ellipsoid, fbm, loft, vertex_normals


# ---------------------------------------------------------------- трубка по кривой

def tube_path(points, radii, seg=10):
    """Трубка вдоль ломаной points с радиусами radii (кадры — параллельный перенос)."""
    P = np.asarray(points, float)
    R = np.asarray(radii, float)
    n = len(P)
    T = np.gradient(P, axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True) + 1e-9
    a = np.array([0, 0, 1.0]) if abs(T[0][2]) < 0.9 else np.array([1.0, 0, 0])
    N = np.cross(T[0], a)
    N /= np.linalg.norm(N)
    frames = []
    for i in range(n):
        N = N - np.dot(N, T[i]) * T[i]
        N /= np.linalg.norm(N) + 1e-9
        frames.append((N.copy(), np.cross(T[i], N)))
    th = np.linspace(0, 2 * math.pi, seg + 1)
    verts, uvs = [], []
    for i in range(n):
        Ni, Bi = frames[i]
        for t in th:
            verts.append(P[i] + R[i] * (math.cos(t) * Ni + math.sin(t) * Bi))
            uvs.append((t / (2 * math.pi), i / (n - 1)))
    cols = seg + 1
    tris = []
    for i in range(n - 1):
        for j in range(seg):
            a0 = i * cols + j
            tris += [(a0, a0 + cols, a0 + 1), (a0 + 1, a0 + cols, a0 + cols + 1)]
    # крышки
    for ring, end in ((0, P[0] - T[0] * R[0] * 0.6), (n - 1, P[-1] + T[-1] * R[-1] * 0.6)):
        ci = len(verts)
        verts.append(end)
        uvs.append((0.5, 0.0 if ring == 0 else 1.0))
        b = ring * cols
        for j in range(seg):
            tris.append((ci, b + j, b + j + 1) if ring == 0 else (ci, b + j + 1, b + j))
    V = np.array(verts)
    Tr = np.array(tris)
    Nn = vertex_normals(V, Tr)
    centers = np.repeat(P, cols, axis=0)
    if np.einsum('ij,ij->i', Nn[:n * cols], V[:n * cols] - centers).mean() < 0:
        Tr = Tr[:, ::-1].copy()
        Nn = -Nn
    return MeshData(V, Tr, np.array(uvs), Nn)


def merge(meshes):
    V, T, U, N, off = [], [], [], [], 0
    for m in meshes:
        V.append(m.vertices)
        T.append(m.triangles + off)
        U.append(m.uvs)
        N.append(m.normals)
        off += len(m.vertices)
    return MeshData(np.vstack(V), np.vstack(T), np.vstack(U), np.vstack(N))


def wobble_path(start, direction, length, steps, rng, wob=0.15, gravity=0.0):
    """Кривая «как корень»: идёт в направлении direction, слегка виляя."""
    p = np.array(start, float)
    d = np.array(direction, float)
    d /= np.linalg.norm(d)
    pts = [p.copy()]
    for _ in range(steps):
        d = d + rng.normal(0, wob, 3) + np.array([0, -gravity, 0])
        d /= np.linalg.norm(d)
        p = p + d * length / steps
        pts.append(p.copy())
    return pts


def branch(start, direction, length, radius, depth, rng, out, spread=0.6):
    """Рекурсивная веточка-рожка. out — список мешей."""
    pts = wobble_path(start, direction, length, 6, rng, wob=0.12)
    out.append(tube_path(pts, np.linspace(radius, radius * 0.45, len(pts)), seg=7))
    if depth > 0:
        for k in range(2):
            i = rng.integers(2, 6)
            d = np.array(pts[i]) - np.array(pts[i - 1])
            d /= np.linalg.norm(d)
            side = np.cross(d, rng.normal(0, 1, 3))
            side /= np.linalg.norm(side)
            nd = d * 0.6 + side * spread + np.array([0, 0.25, 0])
            branch(pts[i], nd, length * rng.uniform(0.4, 0.6), radius * 0.6, depth - 1, rng, out, spread)
    return pts


# ---------------------------------------------------------------- ель

def spruce(height=1.5, radius=0.55, tiers=8, seed=1, crown_start=0.12):
    rng = np.random.default_rng(seed)
    trunk = tube_path([(0, -0.1, 0), (0, height * 0.5, 0), (0, height, 0)], [radius * 0.09, radius * 0.06, 0.01], seg=8)
    parts = [trunk]
    for k in range(tiers):
        t = k / (tiers - 1)                 # 0 — нижний ярус
        yb = height * (crown_start + (0.9 - crown_start) * t)
        h = height * (0.30 - 0.12 * t)
        r = radius * (1.0 - 0.82 * t) * rng.uniform(0.9, 1.1)
        ph = rng.uniform(0, 6.28)
        star = int(rng.integers(7, 11))

        def shape(S, TH, P, ph=ph, star=star, yb=yb):
            edge = np.clip(1 - np.abs(S - yb) / 0.12, 0, 1)
            return 1 + edge * (0.22 * np.sin(TH * star + ph) + 0.12 * np.sin(TH * 23 + ph * 2))

        parts.append(loft([(yb - 0.06, r * 0.18, r * 0.18, 0, 0), (yb, r, r, 0, 0), (yb + h * 0.45, r * 0.5, r * 0.5, 0, 0),
                           (yb + h, r * 0.04, r * 0.04, 0, 0)], rings=10, seg=28, shape=shape,
                          noise=0.12, noise_scale=9, seed=seed + k))
    return merge(parts)


# ---------------------------------------------------------------- сам Кочкарь

LEG_L1 = 1.05     # бедро
LEG_L2 = 1.15     # голень
NECK_SEG = 0.42
HIPS = {'FR': (0.60, -0.30, 0.82), 'FL': (-0.60, -0.30, 0.82), 'HR': (0.62, -0.30, -0.86), 'HL': (-0.62, -0.30, -0.86)}


def _hummock_shape(S, TH, P):
    # бугры и проседания, как у настоящей кочки
    lump = fbm(P.reshape(-1, 3) * 1.6, 3, 5).reshape(S.shape) - 0.5
    return 1 + 0.30 * lump


def _neck_shape(S, TH, P):
    return 1 + 0.10 * np.sin(TH * 4 + S * 14)       # витые волокна, как у старого корня


def build_kochkar(seed=3):
    rng = np.random.default_rng(seed)
    parts = []
    parts.append(PartSpec('body', '', (0, 2.30, 0), kind='none'))

    hummock = loft([(-0.40, 0.45, 0.55, 0, 0), (-0.34, 0.86, 1.08, 0, 0), (-0.20, 1.02, 1.30, 0, 0),
                    (0.00, 1.06, 1.36, 0, 0), (0.20, 0.98, 1.24, 0, -0.02), (0.38, 0.76, 0.98, 0, -0.05),
                    (0.50, 0.46, 0.60, 0, -0.08), (0.57, 0.12, 0.16, 0, -0.1)],
                   rings=48, seg=64, round_end=0.08, shape=_hummock_shape, noise=0.06, noise_scale=7, seed=seed)
    parts.append(PartSpec('hummock', 'body', (0, 0, 0), mesh=hummock, kind='moss'))

    # ёлка и грибы на спине
    parts.append(PartSpec('spruce', 'body', (0.22, 0.42, -0.30), rot=(4, 0, -3), mesh=spruce(1.55, 0.52, seed=seed),
                          kind='needles'))
    parts.append(PartSpec('spruce_small', 'body', (-0.45, 0.30, 0.25), rot=(0, 40, 8), mesh=spruce(0.55, 0.22, tiers=5, seed=seed + 4),
                          kind='needles'))
    for i, (x, y, z, s) in enumerate(((0.62, 0.18, 0.55, 1.0), (0.70, 0.08, 0.72, 0.7), (-0.75, 0.05, -0.55, 0.85))):
        stem = tube_path([(0, -0.03, 0), (0.0, 0.06 * s, 0.005), (0.004, 0.12 * s, 0)], [0.022 * s, 0.02 * s, 0.018 * s], seg=10)
        parts.append(PartSpec(f'mush_stem_{i}', 'body', (x, y, z), mesh=stem, kind='stem'))
        cap = ellipsoid(0.065 * s, 0.035 * s, 0.065 * s, rings=10, seg=18, center=(0, 0.125 * s, 0))
        cap.vertices[:, 1] = np.maximum(cap.vertices[:, 1], 0.11 * s)
        parts.append(PartSpec(f'mush_cap_{i}', 'body', (x, y, z), mesh=cap, kind='cap'))

    # корешки, свисающие снизу
    for i in range(16):
        a = rng.uniform(0, 2 * math.pi)
        r = rng.uniform(0.25, 0.85)
        x, z = math.cos(a) * r * 0.9, math.sin(a) * r * 1.15
        pts = wobble_path((0, 0.04, 0), (rng.normal(0, 0.3), -1, rng.normal(0, 0.3)), rng.uniform(0.25, 0.65), 7, rng, wob=0.25)
        m = tube_path(pts, np.linspace(0.022, 0.004, len(pts)), seg=6)
        parts.append(PartSpec(f'tendril_{i}', 'body', (x, -0.34, z), mesh=m, kind='roots'))

    # ноги
    for name, (hx, hy, hz) in HIPS.items():
        sx = 1 if hx > 0 else -1
        parts.append(PartSpec(f'hip_{name}', 'body', (hx, hy, hz), kind='none'))
        parts.append(PartSpec(f'abduct_{name}', f'hip_{name}', (0, 0, 0), kind='none'))
        parts.append(PartSpec(f'thigh_{name}', f'abduct_{name}', (0, 0, 0), kind='none'))
        thigh = tube_path(wobble_path((0, 0.08, 0), (0, -1, 0), LEG_L1 + 0.08, 10, rng, wob=0.03),
                          np.interp(np.linspace(0, 1, 11), [0, 0.15, 0.5, 1], [0.09, 0.085, 0.062, 0.055]), seg=12)
        # узлы-наплывы
        thigh.vertices += thigh.normals * 0.012 * np.sin(thigh.vertices[:, 1:2] * 31) ** 8
        parts.append(PartSpec(f'thighmesh_{name}', f'thigh_{name}', (0, 0, 0), mesh=thigh, kind='wood'))
        parts.append(PartSpec(f'knee_{name}', f'thigh_{name}', (0, -LEG_L1, 0), kind='none'))
        parts.append(PartSpec(f'kneecap_{name}', f'knee_{name}', (0, 0, 0),
                              mesh=ellipsoid(0.075, 0.085, 0.075, rings=10, seg=14, noise=0.2, seed=seed), kind='wood'))
        shin = tube_path(wobble_path((0, 0, 0), (0, -1, 0), LEG_L2, 10, rng, wob=0.035),
                         np.interp(np.linspace(0, 1, 11), [0, 0.2, 1], [0.06, 0.05, 0.036]), seg=10)
        parts.append(PartSpec(f'shinmesh_{name}', f'knee_{name}', (0, 0, 0), mesh=shin, kind='wood'))
        parts.append(PartSpec(f'ankle_{name}', f'knee_{name}', (0, -LEG_L2, 0), kind='none'))
        toes = []
        for k in range(4):
            a = math.radians(-60 + k * 40 + rng.uniform(-8, 8)) + (0 if hz > 0 else math.pi)
            d = (math.sin(a), -0.35, math.cos(a))
            pts = wobble_path((0, 0, 0), d, rng.uniform(0.2, 0.3), 6, rng, wob=0.1, gravity=0.06)
            toes.append(tube_path(pts, np.linspace(0.03, 0.007, len(pts)), seg=6))
        parts.append(PartSpec(f'toes_{name}', f'ankle_{name}', (0, 0, 0), mesh=merge(toes), kind='wood'))

    # шея: три витых сегмента
    parent = 'body'
    pos = (0, 0.02, 1.12)
    radii = [(0.13, 0.11), (0.11, 0.095), (0.095, 0.08)]
    for i in range(3):
        parts.append(PartSpec(f'neck{i}', parent, pos, kind='none'))
        r0, r1 = radii[i]
        m = loft([(-0.05, r0 * 1.05, r0, 0, 0), (0, r0, r0, 0, 0), (NECK_SEG, r1, r1, 0, 0), (NECK_SEG + 0.05, r1 * 0.9, r1 * 0.9, 0, 0)],
                 rings=14, seg=18, round_start=0.04, round_end=0.04, shape=_neck_shape, noise=0.05, noise_scale=12, seed=seed + i)
        parts.append(PartSpec(f'neckmesh{i}', f'neck{i}', (0, 0, 0), mesh=m, kind='wood'))
        parent = f'neck{i}'
        pos = (0, NECK_SEG, 0)

    # голова: длинный череп-коряга, смотрит в +z
    parts.append(PartSpec('head', 'neck2', (0, NECK_SEG + 0.02, 0), kind='none'))

    def skull_shape(S, TH, P):
        return 1 + 0.06 * np.sin(TH * 3 + S * 9)

    skull = loft([(-0.14, 0.07, 0.08, 0, 0.01), (-0.06, 0.12, 0.13, 0, 0.02), (0.06, 0.125, 0.13, 0, 0.02),
                  (0.22, 0.10, 0.10, 0, 0.0), (0.40, 0.065, 0.07, 0, -0.025), (0.56, 0.045, 0.05, 0, -0.04),
                  (0.63, 0.03, 0.035, 0, -0.045)],
                 axis='z', rings=30, seg=24, round_start=0.06, round_end=0.03, shape=skull_shape, noise=0.06, noise_scale=14, seed=seed)
    parts.append(PartSpec('skull', 'head', (0, 0, 0), mesh=skull, kind='wood'))
    for sx in (1, -1):
        parts.append(PartSpec(f'eye_{sx}', 'head', (sx * 0.105, 0.045, 0.07), rot=(0, sx * 25, 0),
                              mesh=ellipsoid(0.042, 0.036, 0.04, rings=14, seg=20), kind='eye'))
        parts.append(PartSpec(f'brow_{sx}', 'head', (sx * 0.1, 0.085, 0.065), rot=(0, sx * 25, sx * -10),
                              mesh=ellipsoid(0.055, 0.02, 0.04, rings=8, seg=14, noise=0.2, seed=seed + 2), kind='wood'))
        # рожки-веточки
        twigs = []
        pts = branch((0, 0, 0), (sx * 0.55, 1.0, -0.35), 0.48, 0.03, 2, rng, twigs, spread=0.7)
        parts.append(PartSpec(f'antler_{sx}', 'head', (sx * 0.07, 0.11, -0.04), mesh=merge(twigs), kind='wood'))
        # бородатый лишайник свисает с веточек
        strands = []
        for m in twigs[:5]:
            for _ in range(3):
                base = m.vertices[rng.integers(0, len(m.vertices) - 1)]
                sp = wobble_path(base, (rng.normal(0, 0.2), -1, rng.normal(0, 0.2)), rng.uniform(0.08, 0.22), 6, rng, wob=0.3)
                strands.append(tube_path(sp, np.linspace(0.006, 0.002, len(sp)), seg=5))
        parts.append(PartSpec(f'lichen_{sx}', 'head', (sx * 0.07, 0.11, -0.04), mesh=merge(strands), kind='lichen'))
    # лишайник под «подбородком»
    beard = []
    for _ in range(14):
        base = (rng.uniform(-0.06, 0.06), -0.08, rng.uniform(0.0, 0.3))
        sp = wobble_path(base, (rng.normal(0, 0.2), -1, rng.normal(0, 0.15)), rng.uniform(0.08, 0.2), 6, rng, wob=0.3)
        beard.append(tube_path(sp, np.linspace(0.007, 0.002, len(sp)), seg=5))
    parts.append(PartSpec('beard', 'head', (0, 0, 0), mesh=merge(beard), kind='lichen'))

    from .frost_mesh import _finalize
    return _finalize(parts)


def birch(height=7.0, seed=0):
    """Берёза для окружения: ствол + золотые осенние кроны."""
    rng = np.random.default_rng(seed)
    trunk = tube_path(wobble_path((0, -0.2, 0), (0, 1, 0), height, 14, rng, wob=0.04),
                      np.linspace(0.16, 0.04, 15), seg=12)
    crowns = []
    for _ in range(9):
        c = (rng.uniform(-0.9, 0.9), height * rng.uniform(0.5, 0.95), rng.uniform(-0.9, 0.9))
        crowns.append(ellipsoid(rng.uniform(0.6, 1.1), rng.uniform(0.5, 0.9), rng.uniform(0.6, 1.1), rings=10, seg=14,
                                center=c, noise=0.5, seed=int(rng.integers(0, 999))))
    return trunk, merge(crowns)
