"""
Геометрия «Бабки» по фото-референсу: измождённая старуха в длинном грязном покрывале,
закрывает рот ладонями. Под ладонями рта нет — гладкая кожа.

Рост ~2.1 м (выше человека, это заметно не сразу), руки и пальцы длинные.
Перёд смотрит в +z. Платье пересчитывается на CPU: стоя — колокол до земли,
сидя — ложится на колени и стекает к земле (skirt_vertices).
"""
import math

import numpy as np

from .frost_mesh import MeshData, PartSpec, _finalize, ellipsoid, loft, vertex_normals
from .kochkar_mesh import merge, tube_path

PELVIS_Y = 1.02
THIGH = 0.47
SHIN = 0.46
NECK_MAX = 0.28
SEAT_H = 0.46              # высота ступеньки крыльца
SKIRT_L = 1.0
HC, HR = (0.0, 0.10, 0.015), (0.076, 0.108, 0.09)


def cut(mesh, drop):
    c = mesh.vertices[mesh.triangles].mean(axis=1)
    m = ~drop(c)
    return MeshData(mesh.vertices, mesh.triangles[m], mesh.uvs, mesh.normals)


def _g(x, y, cx, cy, sx, sy):
    return np.exp(-((x - cx) ** 2 / sx ** 2 + (y - cy) ** 2 / sy ** 2))


def gaunt_skull():
    """Череп-лицо: впалые щёки, глубокие глазницы, скулы, надбровье. uv.x = затенение (AO)."""
    m = ellipsoid(*HR, rings=40, seg=48, center=HC)
    v = m.vertices.copy()
    x, y, z = v[:, 0], v[:, 1], v[:, 2] - HC[2]
    front = np.clip(z / HR[2], 0, 1) ** 1.5
    sockets = sum(_g(x, y, sx * 0.03, 0.112, 0.019, 0.014) for sx in (1, -1))
    cheeks = sum(_g(x, y, sx * 0.05, 0.062, 0.02, 0.026) for sx in (1, -1))
    bones = sum(_g(x, y, sx * 0.053, 0.093, 0.016, 0.01) for sx in (1, -1))
    brow = _g(x, y, 0, 0.13, 0.06, 0.008)
    temples = sum(_g(x, y, sx * 0.072, 0.13, 0.015, 0.02) for sx in (1, -1))
    jaw = np.clip((0.045 - y) / 0.06, 0, 1)
    disp = (-0.017 * sockets - 0.013 * cheeks + 0.006 * bones + 0.006 * brow) * front - 0.008 * temples
    v += m.normals * disp[:, None]
    v[:, 0] *= 1 - 0.18 * jaw ** 1.5                     # узкий подбородок
    m.vertices = v
    ao = np.clip(1 - 0.85 * sockets * front - 0.45 * cheeks * front - 0.3 * temples, 0.05, 1)
    m.uvs = np.stack([ao, m.uvs[:, 1]], -1)
    m.normals = vertex_normals(m.vertices, m.triangles)
    if np.einsum('ij,ij->i', m.normals, m.vertices - m.vertices.mean(0)).mean() < 0:
        m.normals = -m.normals
    return m


def face_z(x, y):
    q = 1 - (x / HR[0]) ** 2 - ((y - HC[1]) / HR[1]) ** 2
    return HC[2] + HR[2] * math.sqrt(max(q, 0))


def _cloth_folds(k, amp=0.05):
    def f(S, TH, P):
        lo = np.clip((S.max() - S) / (S.max() - S.min() + 1e-6), 0, 1) ** 2
        return 1 + amp * lo * (np.sin(TH * k + np.sin(TH * 3.0) * 1.3) + 0.4 * np.sin(TH * (k * 2 + 1)))
    return f


# ---------------------------------------------------------------- платье

SK_RINGS, SK_SEG = 30, 56


def skirt_topology():
    tris = []
    cols = SK_SEG + 1
    for i in range(SK_RINGS - 1):
        for j in range(SK_SEG):
            a = i * cols + j
            tris += [(a, a + cols, a + 1), (a + 1, a + cols, a + cols + 1)]
    uvs = [(j / SK_SEG, 1 - i / (SK_RINGS - 1)) for i in range(SK_RINGS) for j in range(cols)]  # v: 1 пояс, 0 подол
    return np.array(tris), np.array(uvs)


def skirt_vertices(sit):
    """Вершины платья (в системе таза). sit: 0 стоит, 1 сидит на ступеньке."""
    t = np.linspace(0, 1, SK_RINGS)[:, None]          # 0 пояс -> 1 подол
    th = np.linspace(0, 2 * math.pi, SK_SEG + 1)[None, :]
    s = t * SKIRT_L
    folds = 1 + 0.07 * t * (np.sin(th * 7 + np.sin(th * 2) * 1.4) + 0.5 * np.sin(th * 15 + 1))
    r_stand = 0.17 + 0.17 * t ** 0.8
    x0 = np.cos(th) * r_stand * 1.05 * folds
    z0 = np.sin(th) * r_stand * 0.92 * folds + 0.01
    y0 = 0.08 - s
    # сидя: перед лежит на бёдрах до колен и стекает вниз; бока и зад — на ступеньке
    lap = 0.50
    front = np.clip(np.sin(th), 0, 1) ** 0.6
    back = np.clip(-np.sin(th), 0, 1)
    side = 1 - front
    along = np.minimum(s, lap)
    drop = np.maximum(s - lap, 0)
    rest = np.maximum(s - 0.14, 0)
    r_sit = 0.19 + 0.2 * t ** 0.7
    xs = np.cos(th) * r_sit * 1.15 * folds * (1 + side * rest * 0.5)
    zs = np.sin(th) * r_sit * 0.7 * folds + front * (along * 0.95 + drop * 0.15) - back * rest * 0.35
    ys = 0.08 - side * (np.minimum(s, 0.14) + rest * 0.15) - front * (drop + along * 0.15)
    k = sit * sit * (3 - 2 * sit)
    return np.stack([x0 * (1 - k) + xs * k, y0 * (1 - k) + ys * k, z0 * (1 - k) + zs * k], -1).reshape(-1, 3)


def skirt_mesh(sit=0.0):
    tris, uvs = skirt_topology()
    v = skirt_vertices(sit)
    return MeshData(v, tris, uvs, vertex_normals(v, tris))


# ---------------------------------------------------------------- вся фигура

def build_babka(seed=4):
    rng = np.random.default_rng(seed)
    parts = []
    P = parts.append
    P(PartSpec('pelvis', '', (0, PELVIS_Y, 0), kind='none'))
    P(PartSpec('skirt', 'pelvis', (0, 0, 0), mesh=skirt_mesh(0.0), kind='linen'))

    P(PartSpec('spine1', 'pelvis', (0, 0.06, 0), kind='none'))
    P(PartSpec('torso_low', 'spine1', (0, 0, 0), kind='linen',
               mesh=loft([(-0.08, 0.17, 0.14, 0, 0), (0.0, 0.165, 0.135, 0, 0), (0.25, 0.165, 0.13, 0, 0.0),
                          (0.44, 0.18, 0.135, 0, -0.01)], rings=18, seg=32, noise=0.05, noise_scale=7, seed=seed)))
    P(PartSpec('spine2', 'spine1', (0, 0.42, 0), kind='none'))
    P(PartSpec('torso_up', 'spine2', (0, 0, 0), kind='linen',
               mesh=loft([(-0.04, 0.18, 0.135, 0, -0.01), (0.12, 0.19, 0.15, 0, -0.03), (0.24, 0.18, 0.15, 0, -0.045),
                          (0.32, 0.14, 0.12, 0, -0.03), (0.37, 0.07, 0.07, 0, -0.01)], rings=18, seg=32,
                         noise=0.05, noise_scale=7, seed=seed + 1)))
    # накидка на плечах: спереди разрез, край рваный (в шейдере)
    shawl = loft([(-0.62, 0.30, 0.27, 0, 0.0), (-0.35, 0.29, 0.25, 0, -0.01), (0.0, 0.28, 0.24, 0, -0.02),
                  (0.18, 0.28, 0.24, 0, -0.03), (0.30, 0.23, 0.20, 0, -0.03), (0.38, 0.12, 0.11, 0, -0.02),
                  (0.42, 0.06, 0.06, 0, -0.01)], rings=34, seg=56, shape=_cloth_folds(6, 0.09), noise=0.06,
                 noise_scale=5, seed=seed + 2)
    shawl = cut(shawl, lambda c: (c[:, 2] > 0.02) & (np.abs(c[:, 0]) < 0.07 + np.clip(0.3 - c[:, 1], 0, 1) * 0.35))
    P(PartSpec('shawl', 'spine2', (0, 0, 0), mesh=shawl, kind='wool'))

    # тонкая морщинистая шея (вытягивается, когда заметила) и голова
    P(PartSpec('neck', 'spine2', (0, 0.32, 0.0), kind='none'))
    P(PartSpec('neck_slide', 'neck', (0, 0, 0), kind='none'))
    P(PartSpec('neck_skin', 'neck_slide', (0, 0, 0), kind='skin',
               mesh=loft([(-0.36, 0.045, 0.045, 0, 0), (0.0, 0.04, 0.042, 0, 0.004), (0.08, 0.042, 0.044, 0, 0.008)],
                         rings=30, seg=18, shape=lambda S, TH, Pp: 1 + 0.06 * np.abs(np.sin(S * 55)) ** 3, seed=seed)))
    P(PartSpec('head', 'neck_slide', (0, 0.05, 0.01), kind='none'))
    P(PartSpec('skull', 'head', (0, 0, 0), mesh=gaunt_skull(), kind='face'))
    fz = HC[2] + HR[2]
    P(PartSpec('nose', 'head', (0, 0.083, fz - 0.003), rot=(-12, 0, 0),
               mesh=loft([(-0.022, 0.006, 0.006, 0, 0.0), (-0.012, 0.009, 0.01, 0, 0.004), (0.0, 0.011, 0.013, 0, 0.003),
                          (0.01, 0.007, 0.007, 0, -0.003)], rings=10, seg=14, round_start=0.008, round_end=0.006), kind='skin'))
    for sx in (1, -1):
        ex, ey = sx * 0.03, 0.111
        ez = face_z(ex, ey) - 0.021
        P(PartSpec(f'eye_{sx}', 'head', (ex, ey, ez), mesh=ellipsoid(0.0102, 0.0102, 0.0102, rings=14, seg=18), kind='eye'))
        P(PartSpec(f'lid_{sx}', 'head', (ex, ey + 0.004, ez + 0.002), rot=(-18, 0, 0),
                   mesh=ellipsoid(0.0122, 0.0072, 0.0108, rings=10, seg=16), kind='skin'))
    # седые пряди из-под капюшона
    strands = []
    for i in range(16):
        sx = 1 if i % 2 else -1
        x0 = sx * rng.uniform(0.03, 0.07)
        p = np.array((x0, 0.2, face_z(x0 * 0.8, 0.17) - 0.012))
        pts = [p.copy()]
        for _ in range(7):
            p = p + np.array([sx * rng.uniform(0.0, 0.01), -0.035, rng.uniform(-0.006, 0.004)])
            pts.append(p.copy())
        strands.append(tube_path(pts, np.linspace(0.003, 0.0012, len(pts)), seg=5))
    P(PartSpec('hair', 'head', (0, 0, 0), mesh=merge(strands), kind='hair'))

    # капюшон-покрывало: свободно лежит вокруг головы, спереди открыт ниже подбородка
    hood = loft([(-0.26, 0.24, 0.21, 0, -0.06), (-0.13, 0.17, 0.16, 0, -0.035), (-0.03, 0.125, 0.13, 0, -0.012),
                 (0.07, 0.112, 0.125, 0, 0.0), (0.15, 0.104, 0.116, 0, -0.008), (0.2, 0.088, 0.098, 0, -0.014),
                 (0.24, 0.05, 0.058, 0, -0.016), (0.258, 0.012, 0.012, 0, -0.016)], rings=36, seg=48,
                shape=_cloth_folds(5, 0.12), noise=0.03,
                noise_scale=8, seed=seed + 3)
    hood = cut(hood, lambda c: (c[:, 2] > 0.0) & (((c[:, 0] / 0.066) ** 2 + ((c[:, 1] - 0.085) / 0.1) ** 2 < 1)
                                                   | ((c[:, 1] < 0.02) & (np.abs(c[:, 0]) < 0.055 + (0.02 - c[:, 1]) * 0.6))))
    P(PartSpec('hood', 'head', (0, 0, 0), mesh=hood, kind='wool'))
    ky = np.array([-0.26, -0.13, -0.03, 0.07, 0.15, 0.2, 0.24])
    krx = np.array([0.24, 0.17, 0.125, 0.112, 0.104, 0.088, 0.05])
    krz = np.array([0.21, 0.16, 0.13, 0.125, 0.116, 0.098, 0.058])
    kcz = np.array([-0.06, -0.035, -0.012, 0.0, -0.008, -0.014, -0.016])
    rim = []
    for t in np.linspace(-0.55, math.pi + 0.55, 40):
        x, y = 0.066 * math.cos(t), 0.085 + 0.1 * math.sin(t)
        rx, rz, cz = np.interp(y, ky, krx), np.interp(y, ky, krz), np.interp(y, ky, kcz)
        z = cz + rz * math.sqrt(max(1 - (x / rx) ** 2, 0.0))
        rim.append((x * 1.04, y, z + 0.003))
    P(PartSpec('hood_rim', 'head', (0, 0, 0), mesh=tube_path(rim, [0.009] * len(rim), seg=8), kind='wool'))

    # руки: длинные, в широких рукавах; кисть на отдельном узле для наведения ладоней на лицо
    for side, sx in (('R', 1), ('L', -1)):
        P(PartSpec(f'shoulder_{side}', 'spine2', (sx * 0.18, 0.26, -0.02), kind='none'))
        P(PartSpec(f'abduct_{side}', f'shoulder_{side}', (0, 0, 0), kind='none'))
        P(PartSpec(f'upper_{side}', f'abduct_{side}', (0, 0, 0), kind='none'))
        P(PartSpec(f'upperarm_{side}', f'upper_{side}', (0, 0, 0), kind='linen',
                   mesh=loft([(0.05, 0.06, 0.06, 0, 0), (0.0, 0.066, 0.066, 0, 0), (-0.43, 0.056, 0.058, 0, 0),
                              (-0.46, 0.054, 0.054, 0, 0)], rings=18, seg=20, round_start=0.05, noise=0.08, noise_scale=12,
                             seed=seed + 5)))
        P(PartSpec(f'elbow_{side}', f'upper_{side}', (0, -0.43, 0), kind='none'))
        P(PartSpec(f'forearm_{side}', f'elbow_{side}', (0, 0, 0), kind='linen',
                   mesh=loft([(0.04, 0.056, 0.056, 0, 0), (0.0, 0.058, 0.058, 0, 0), (-0.25, 0.062, 0.062, 0, 0),
                              (-0.38, 0.08, 0.078, 0, 0.0), (-0.40, 0.082, 0.08, 0, 0.0)], rings=20, seg=24,
                             round_start=0.04, shape=_cloth_folds(5, 0.1), noise=0.08, noise_scale=12, seed=seed + 6)))
        P(PartSpec(f'wristskin_{side}', f'elbow_{side}', (0, 0, 0), kind='skin',
                   mesh=loft([(-0.30, 0.026, 0.024, 0, 0), (-0.43, 0.022, 0.02, 0, 0)], rings=6, seg=14)))
        P(PartSpec(f'wrist_{side}', f'elbow_{side}', (0, -0.43, 0), kind='none'))
        P(PartSpec(f'hand_aim_{side}', f'wrist_{side}', (0, 0, 0), kind='none'))
        palm = loft([(0.015, 0.024, 0.014, 0, 0), (0.0, 0.028, 0.015, 0, 0), (-0.085, 0.037, 0.012, 0, 0.002),
                     (-0.1, 0.034, 0.011, 0, 0.002)], rings=12, seg=16, round_start=0.015, round_end=0.01, noise=0.05,
                    noise_scale=60, seed=seed)
        thumb = tube_path([(0.03, -0.02, 0.012), (0.04, -0.06, 0.03), (0.035, -0.1, 0.038)], [0.009, 0.008, 0.006], seg=8)
        hand = merge([palm, thumb])
        hand.vertices *= 0.85
        if sx < 0:                                    # левая — зеркальная
            hand.vertices[:, 0] *= -1
            hand.normals[:, 0] *= -1
            hand.triangles = hand.triangles[:, ::-1].copy()
        P(PartSpec(f'hand_{side}', f'hand_aim_{side}', (0, 0, 0), mesh=hand, kind='skin'))
        # пальцы: две фаланги на шарнирах (сгибаются, подрагивают), с ногтями
        for k, (fx, L) in enumerate(((0.026, 0.13), (0.009, 0.15), (-0.009, 0.145), (-0.025, 0.118))):
            L *= 0.85
            fx *= 0.85 * sx
            r0 = 0.0062
            P(PartSpec(f'f{k}a_{side}', f'hand_aim_{side}', (fx, -0.082, 0.004), kind='none'))
            ts = np.linspace(0, 1, 7)
            prox = tube_path([(0, -0.55 * L * t, 0) for t in ts],
                             r0 * (1 - 0.15 * ts) * (1 + 0.25 * np.exp(-((ts - 0.05) ** 2) / 0.01) + 0.22 * np.exp(-((ts - 1.0) ** 2) / 0.01)), seg=8)
            P(PartSpec(f'f{k}prox_{side}', f'f{k}a_{side}', (0, 0, 0), mesh=prox, kind='skin'))
            P(PartSpec(f'f{k}b_{side}', f'f{k}a_{side}', (0, -0.55 * L, 0), kind='none'))
            dist = tube_path([(0, -0.45 * L * t, 0.002 * t) for t in ts], r0 * 0.88 * (1 - 0.3 * ts ** 2), seg=8)
            P(PartSpec(f'f{k}dist_{side}', f'f{k}b_{side}', (0, 0, 0), mesh=dist, kind='skin'))
            P(PartSpec(f'f{k}nail_{side}', f'f{k}b_{side}', (0, -0.45 * L + 0.009, -r0 * 0.62),
                       mesh=ellipsoid(r0 * 0.78, 0.0085, 0.0018, rings=8, seg=12), kind='nail'))

    # ноги под платьем + стоптанные ботинки
    for side, sx in (('R', 1), ('L', -1)):
        P(PartSpec(f'hip_{side}', 'pelvis', (sx * 0.085, -0.05, 0), kind='none'))
        P(PartSpec(f'thigh_{side}', f'hip_{side}', (0, 0, 0), kind='linen',
                   mesh=loft([(0.04, 0.07, 0.07, 0, 0), (0.0, 0.075, 0.077, 0, 0), (-0.47, 0.05, 0.052, 0, 0)],
                             rings=12, seg=16, round_start=0.04, seed=seed)))
        P(PartSpec(f'knee_{side}', f'hip_{side}', (0, -THIGH, 0), kind='none'))
        P(PartSpec(f'shin_{side}', f'knee_{side}', (0, 0, 0), kind='wool',          # шерстяные чулки
                   mesh=loft([(0.03, 0.047, 0.049, 0, 0), (0.0, 0.048, 0.05, 0, 0), (-0.30, 0.036, 0.038, 0, 0)],
                             rings=12, seg=16, round_start=0.03, seed=seed)))
        P(PartSpec(f'valenok_{side}', f'knee_{side}', (0, 0, 0), kind='felt',          # голенище валенка
                   mesh=loft([(-0.47, 0.056, 0.058, 0, 0), (-0.32, 0.058, 0.06, 0, 0), (-0.2, 0.064, 0.066, 0, 0),
                              (-0.17, 0.068, 0.07, 0, 0), (-0.16, 0.05, 0.05, 0, 0)], rings=16, seg=20, noise=0.05,
                             noise_scale=14, seed=seed + 7)))
        P(PartSpec(f'ankle_{side}', f'knee_{side}', (0, -SHIN, 0), kind='none'))
        P(PartSpec(f'shoe_{side}', f'ankle_{side}', (0, 0, 0), kind='felt',
                   mesh=loft([(-0.07, 0.052, 0.058, 0, -0.012), (0.0, 0.058, 0.058, 0, -0.022), (0.12, 0.056, 0.046, 0, -0.04),
                              (0.2, 0.042, 0.036, 0, -0.045)], axis='z', rings=14, seg=18, round_start=0.035, round_end=0.035,
                             noise=0.06, noise_scale=16, seed=seed)))
    # ---- снег и лёд прямо на ней
    def snowcap(rx, ry, rz, seed_, flat=0.35):
        m = ellipsoid(rx, ry, rz, rings=14, seg=22, noise=0.35, seed=seed_)
        v = m.vertices
        v[:, 1] = np.maximum(v[:, 1], -ry * flat)            # плоское дно, ложится на ткань
        m.vertices = v
        m.normals = vertex_normals(m.vertices, m.triangles)
        if np.einsum('ij,ij->i', m.normals, m.vertices - m.vertices.mean(0)).mean() < 0:
            m.normals = -m.normals
        return m

    P(PartSpec('snow_head', 'head', (0, 0.222, -0.03), rot=(-10, 0, 0), mesh=snowcap(0.058, 0.016, 0.07, 31), kind='snowpack'))
    for side, sx in (('R', 1), ('L', -1)):
        P(PartSpec(f'snow_shoulder_{side}', 'spine2', (sx * 0.17, 0.315, -0.04), rot=(0, 0, sx * -22),
                   mesh=snowcap(0.075, 0.02, 0.095, 40 + sx), kind='snowpack'))
    P(PartSpec('snow_back', 'spine2', (0, 0.22, -0.235), rot=(-62, 0, 0), mesh=snowcap(0.14, 0.022, 0.1, 52), kind='snowpack'))
    P(PartSpec('snow_back2', 'spine2', (0, 0.02, -0.29), rot=(-78, 0, 0), mesh=snowcap(0.16, 0.02, 0.08, 53), kind='snowpack'))

    def icicle(L, r, seed_):
        return loft([(-L, 0.0015, 0.0015, 0, 0), (-L * 0.55, r * 0.45, r * 0.45, 0, 0), (-0.01, r, r, 0, 0), (0.0, r * 1.2, r * 1.2, 0, 0)],
                     rings=8, seg=8, noise=0.3, noise_scale=60, seed=seed_)
    # по краю платка (сзади и с боков)
    for i, a in enumerate(np.linspace(math.radians(195), math.radians(345), 13)):
        L = rng.uniform(0.04, 0.14)
        P(PartSpec(f'icicle_shawl_{i}', 'spine2', (0.29 * math.cos(a), -0.58, 0.26 * math.sin(a) - 0.01),
                   mesh=icicle(L, rng.uniform(0.005, 0.009), 60 + i), kind='ice'))
    # под подбородком, с края капюшона
    for i, x in enumerate((-0.05, -0.02, 0.025, 0.055)):
        P(PartSpec(f'icicle_hood_{i}', 'head', (x, -0.06 - abs(x) * 0.6, 0.06 - abs(x) * 0.5),
                   mesh=icicle(rng.uniform(0.025, 0.06), 0.004, 70 + i), kind='ice'))
    return _finalize(parts)
