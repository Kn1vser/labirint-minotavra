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
DETAIL = 3.9               # плотность сетки (больше — больше полигонов)


def Q(n):
    return max(3, int(round(n * DETAIL)))


def cut(mesh, drop):
    c = mesh.vertices[mesh.triangles].mean(axis=1)
    m = ~drop(c)
    return MeshData(mesh.vertices, mesh.triangles[m], mesh.uvs, mesh.normals)


def _g(x, y, cx, cy, sx, sy):
    return np.exp(-((x - cx) ** 2 / sx ** 2 + (y - cy) ** 2 / sy ** 2))


def gaunt_skull():
    """
    Лицо-скульптура на плотной сетке. Всё — смещения вдоль нормали:
    глазницы, надбровье, мешки под глазами, скулы, впалые щёки, носогубные складки, брыли,
    подбородок, морщины на лбу, «гусиные лапки», межбровные складки и сросшийся рот.
    uv.x — затенение (AO) складок и глазниц.
    """
    m = ellipsoid(*HR, rings=Q(56), seg=Q(64), center=HC)
    v = m.vertices.copy()
    x, y, z = v[:, 0], v[:, 1], v[:, 2] - HC[2]
    ax = np.abs(x)
    front = np.clip(z / HR[2], 0, 1) ** 1.3

    def band(val, c, w):
        return np.exp(-((val - c) ** 2) / (w * w))

    sockets = sum(_g(x, y, sx * 0.03, 0.111, 0.02, 0.0135) for sx in (1, -1))
    inner = sum(_g(x, y, sx * 0.016, 0.106, 0.007, 0.008) for sx in (1, -1))        # внутренний угол глаза глубже
    brow = sum(_g(x, y, sx * 0.03, 0.131, 0.026, 0.0075) for sx in (1, -1))
    glabella = sum(_g(x, y, sx * 0.0055, 0.128, 0.0018, 0.012) for sx in (1, -1))  # складки между бровей
    bags = sum(_g(x, y, sx * 0.031, 0.094, 0.018, 0.0055) for sx in (1, -1))
    bag_crease = sum(_g(x, y, sx * 0.032, 0.0875, 0.02, 0.0022) for sx in (1, -1))
    bones = sum(_g(x, y, sx * 0.055, 0.089, 0.017, 0.0095) for sx in (1, -1))
    cheeks = sum(_g(x, y, sx * 0.047, 0.056, 0.019, 0.022) for sx in (1, -1))
    temples = sum(_g(x, y, sx * 0.07, 0.128, 0.014, 0.022) for sx in (1, -1))
    # носогубные складки: от крыла носа вниз-наружу
    t = np.clip((0.072 - y) / 0.04, 0, 1)
    nl_x = 0.017 + 0.019 * t
    nlf = np.exp(-((ax - nl_x) ** 2) / 0.0000028) * (t > 0) * (y > 0.028)
    nl_bulge = np.exp(-((ax - nl_x - 0.006) ** 2) / 0.00002) * (t > 0) * (y > 0.03)
    # «морда» вокруг рта, сросшийся рот: горизонтальная складка и мелкие радиальные морщинки
    muzzle = _g(x, y, 0, 0.048, 0.03, 0.02)
    mouth_crease = band(y, 0.0465 + 0.0025 * (x / 0.022) ** 2, 0.0011) * np.exp(-(x / 0.023) ** 6)
    pucker = (np.abs(np.sin(np.arctan2(y - 0.0465, x) * 13)) ** 10) * _g(x, y, 0, 0.0465, 0.022, 0.012)
    chin = _g(x, y, 0, 0.014, 0.022, 0.014)
    chin_crease = band(y, 0.027, 0.0018) * np.exp(-(x / 0.016) ** 4)
    jowls = sum(_g(x, y, sx * 0.046, 0.022, 0.014, 0.014) for sx in (1, -1))
    # морщины на лбу и «гусиные лапки»
    fh = (np.sin((y - 0.14) * 2 * np.pi / 0.0105) * 0.5 + 0.5) ** 12 * np.clip((y - 0.142) / 0.01, 0, 1) * np.clip((0.2 - y) / 0.02, 0, 1)
    fh *= np.clip(1 - (ax / 0.06) ** 2, 0, 1) * (0.7 + 0.3 * np.sin(x * 140))
    crows = 0
    for sx in (1, -1):
        dx, dy = x - sx * 0.052, y - 0.111
        r = np.sqrt(dx * dx + dy * dy)
        ang = np.arctan2(dy, dx * sx)
        crows = crows + (np.abs(np.sin(ang * 7)) ** 14) * np.exp(-((r - 0.012) ** 2) / 0.00005) * (dx * sx > 0)

    disp = (-0.019 * sockets - 0.006 * inner + 0.0065 * brow - 0.0016 * glabella + 0.0032 * bags - 0.0018 * bag_crease
            + 0.0075 * bones - 0.015 * cheeks - 0.003 * nlf + 0.0022 * nl_bulge
            + 0.0035 * muzzle - 0.0019 * mouth_crease - 0.0008 * pucker + 0.006 * chin - 0.0015 * chin_crease
            + 0.004 * jowls - 0.0011 * fh - 0.0009 * crows) * front - 0.008 * temples
    v += m.normals * disp[:, None]
    jaw = np.clip((0.045 - y) / 0.06, 0, 1)
    v[:, 0] *= 1 - 0.17 * jaw ** 1.5                          # узкий старческий подбородок
    m.vertices = v
    ao = 1 - 0.85 * sockets * front - 0.4 * inner * front - 0.45 * cheeks * front - 0.3 * temples
    ao -= (0.3 * nlf + 0.6 * mouth_crease + 0.3 * pucker + 0.35 * bag_crease + 0.4 * fh + 0.35 * crows
           + 0.4 * glabella + 0.35 * chin_crease) * front
    m.uvs = np.stack([np.clip(ao, 0.05, 1), m.uvs[:, 1]], -1)
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

SK_RINGS, SK_SEG = 110, 228


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
                          (0.44, 0.18, 0.135, 0, -0.01)], rings=Q(18), seg=Q(32), noise=0.05, noise_scale=7, seed=seed)))
    P(PartSpec('spine2', 'spine1', (0, 0.42, 0), kind='none'))
    P(PartSpec('torso_up', 'spine2', (0, 0, 0), kind='linen',
               mesh=loft([(-0.04, 0.18, 0.135, 0, -0.01), (0.12, 0.19, 0.15, 0, -0.03), (0.24, 0.18, 0.15, 0, -0.045),
                          (0.32, 0.14, 0.12, 0, -0.03), (0.37, 0.07, 0.07, 0, -0.01)], rings=Q(18), seg=Q(32),
                         noise=0.05, noise_scale=7, seed=seed + 1)))
    # накидка на плечах: спереди разрез, край рваный (в шейдере)
    shawl = loft([(-0.62, 0.30, 0.27, 0, 0.0), (-0.35, 0.29, 0.25, 0, -0.01), (0.0, 0.28, 0.24, 0, -0.02),
                  (0.18, 0.28, 0.24, 0, -0.03), (0.30, 0.23, 0.20, 0, -0.03), (0.38, 0.12, 0.11, 0, -0.02),
                  (0.42, 0.06, 0.06, 0, -0.01)], rings=Q(34), seg=Q(56), shape=_cloth_folds(6, 0.09), noise=0.06,
                 noise_scale=5, seed=seed + 2)
    shawl = cut(shawl, lambda c: (c[:, 2] > 0.02) & (np.abs(c[:, 0]) < 0.07 + np.clip(0.3 - c[:, 1], 0, 1) * 0.35))
    P(PartSpec('shawl', 'spine2', (0, 0, 0), mesh=shawl, kind='wool'))

    # тонкая морщинистая шея (вытягивается, когда заметила) и голова
    P(PartSpec('neck', 'spine2', (0, 0.32, 0.0), kind='none'))
    P(PartSpec('neck_slide', 'neck', (0, 0, 0), kind='none'))
    P(PartSpec('neck_skin', 'neck_slide', (0, 0, 0), kind='skin',
               mesh=loft([(-0.36, 0.045, 0.045, 0, 0), (0.0, 0.04, 0.042, 0, 0.004), (0.08, 0.042, 0.044, 0, 0.008)],
                         rings=Q(30), seg=Q(18), shape=lambda S, TH, Pp: 1 + 0.06 * np.abs(np.sin(S * 55)) ** 3, seed=seed)))
    P(PartSpec('head', 'neck_slide', (0, 0.05, 0.01), kind='none'))
    P(PartSpec('skull', 'head', (0, 0, 0), mesh=gaunt_skull(), kind='face'))
    fz = HC[2] + HR[2]
    # старческий нос с горбинкой, крыльями и ноздрями
    nose = loft([(0.056, 0.004, 0.004, 0, fz - 0.003), (0.0605, 0.0085, 0.0075, 0, fz + 0.007), (0.067, 0.0115, 0.011, 0, fz + 0.013),
                 (0.075, 0.0095, 0.011, 0, fz + 0.0125), (0.086, 0.0072, 0.009, 0, fz + 0.0075), (0.097, 0.0068, 0.0085, 0, fz + 0.0055),
                 (0.106, 0.0068, 0.007, 0, fz + 0.001), (0.118, 0.0075, 0.006, 0, fz - 0.009)],
                rings=Q(26), seg=Q(22), round_start=0.004, noise=0.03, noise_scale=180, seed=3)
    P(PartSpec('nose', 'head', (0, 0, 0), mesh=nose, kind='skin'))
    for sx in (1, -1):
        P(PartSpec(f'ala_{sx}', 'head', (sx * 0.0105, 0.0635, fz + 0.0035), rot=(0, sx * 20, 0),
                   mesh=ellipsoid(0.0062, 0.0052, 0.0072, rings=Q(10), seg=Q(14)), kind='skin'))
        P(PartSpec(f'nostril_{sx}', 'head', (sx * 0.0058, 0.0592, fz + 0.0088), rot=(25, sx * 15, 0),
                   mesh=ellipsoid(0.0032, 0.0014, 0.0036, rings=Q(6), seg=Q(10)), kind='cavity'))

    for sx in (1, -1):
        ex, ey = sx * 0.03, 0.111
        ez = face_z(ex, ey) - 0.021
        er = 0.0102
        P(PartSpec(f'eye_{sx}', 'head', (ex, ey, ez), mesh=ellipsoid(er, er, er, rings=Q(14), seg=Q(18)), kind='eye'))
        P(PartSpec(f'lid_{sx}', 'head', (ex, ey + 0.004, ez + 0.002), rot=(-18, 0, 0),
                   mesh=ellipsoid(0.0122, 0.0072, 0.0108, rings=Q(10), seg=Q(16)), kind='skin'))
        # тяжёлое верхнее веко и нижнее с влажной кромкой — дуги вокруг глазного яблока
        up = [(ex + (er + 0.0018) * math.cos(a), ey + 0.0035 + (er + 0.0008) * math.sin(a) * 0.55, ez + er * 0.78)
              for a in np.linspace(0.15, math.pi - 0.15, 14)]
        lo = [(ex + (er + 0.0012) * math.cos(a), ey - 0.0015 + (er + 0.0008) * math.sin(a) * 0.62, ez + er * 0.8)
              for a in np.linspace(math.pi + 0.25, 2 * math.pi - 0.25, 12)]
        P(PartSpec(f'uplid_{sx}', 'head', (0, 0, 0), mesh=tube_path(up, [0.0018] + [0.0032] * 12 + [0.0018], seg=Q(8)), kind='skin'))
        P(PartSpec(f'lolid_{sx}', 'head', (0, 0, 0), mesh=tube_path(lo, [0.0012] + [0.0021] * 10 + [0.0012], seg=Q(8)), kind='skin'))
        # редкие заиндевевшие ресницы
        lashes = []
        for a in np.linspace(0.35, math.pi - 0.35, 11):
            b0 = np.array(up[0]) * 0 + np.array((ex + (er + 0.0018) * math.cos(a), ey + 0.002 + (er + 0.0008) * math.sin(a) * 0.55 - 0.002, ez + er * 0.95))
            lashes.append(tube_path([b0, b0 + np.array([0.0006 * math.cos(a), -0.0015, 0.0035]), b0 + np.array([0.001 * math.cos(a), -0.0005, 0.006])],
                                    [0.00045, 0.0004, 0.0002], seg=4))
        P(PartSpec(f'lashes_{sx}', 'head', (0, 0, 0), mesh=merge(lashes), kind='hair'))
        # брови: редкие седые волоски вдоль надбровья
        rng_b = np.random.default_rng(10 + sx)
        brows = []
        for k in range(34):
            tt = rng_b.uniform(0, 1)
            bx = sx * (0.013 + 0.038 * tt)
            by = 0.127 + 0.006 * math.sin(tt * math.pi) - 0.004 * tt + rng_b.uniform(-0.002, 0.002)
            bz = face_z(bx, by) + 0.003
            d = np.array([sx * rng_b.uniform(0.004, 0.008), rng_b.uniform(-0.001, 0.003), rng_b.uniform(0.0, 0.002)])
            p0 = np.array((bx, by, bz))
            brows.append(tube_path([p0, p0 + d * 0.5 + np.array([0, 0.0008, 0.0006]), p0 + d], [0.0006, 0.0005, 0.0002], seg=4))
        P(PartSpec(f'brow_{sx}', 'head', (0, 0, 0), mesh=merge(brows), kind='hair'))

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
        strands.append(tube_path(pts, np.linspace(0.003, 0.0012, len(pts)), seg=Q(5)))
    P(PartSpec('hair', 'head', (0, 0, 0), mesh=merge(strands), kind='hair'))

    # капюшон-покрывало: свободно лежит вокруг головы, спереди открыт ниже подбородка
    hood = loft([(-0.26, 0.24, 0.21, 0, -0.06), (-0.13, 0.17, 0.16, 0, -0.035), (-0.03, 0.125, 0.13, 0, -0.012),
                 (0.07, 0.112, 0.125, 0, 0.0), (0.15, 0.104, 0.116, 0, -0.008), (0.2, 0.088, 0.098, 0, -0.014),
                 (0.24, 0.05, 0.058, 0, -0.016), (0.258, 0.012, 0.012, 0, -0.016)], rings=Q(36), seg=Q(48),
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
    P(PartSpec('hood_rim', 'head', (0, 0, 0), mesh=tube_path(rim, [0.009] * len(rim), seg=Q(8)), kind='wool'))

    # руки: длинные, в широких рукавах; кисть на отдельном узле для наведения ладоней на лицо
    for side, sx in (('R', 1), ('L', -1)):
        P(PartSpec(f'shoulder_{side}', 'spine2', (sx * 0.18, 0.26, -0.02), kind='none'))
        P(PartSpec(f'abduct_{side}', f'shoulder_{side}', (0, 0, 0), kind='none'))
        P(PartSpec(f'upper_{side}', f'abduct_{side}', (0, 0, 0), kind='none'))
        P(PartSpec(f'upperarm_{side}', f'upper_{side}', (0, 0, 0), kind='linen',
                   mesh=loft([(0.05, 0.06, 0.06, 0, 0), (0.0, 0.066, 0.066, 0, 0), (-0.43, 0.056, 0.058, 0, 0),
                              (-0.46, 0.054, 0.054, 0, 0)], rings=Q(18), seg=Q(20), round_start=0.05, noise=0.08, noise_scale=12,
                             seed=seed + 5)))
        P(PartSpec(f'elbow_{side}', f'upper_{side}', (0, -0.43, 0), kind='none'))
        P(PartSpec(f'forearm_{side}', f'elbow_{side}', (0, 0, 0), kind='linen',
                   mesh=loft([(0.04, 0.056, 0.056, 0, 0), (0.0, 0.058, 0.058, 0, 0), (-0.25, 0.062, 0.062, 0, 0),
                              (-0.38, 0.08, 0.078, 0, 0.0), (-0.40, 0.082, 0.08, 0, 0.0)], rings=Q(20), seg=Q(24),
                             round_start=0.04, shape=_cloth_folds(5, 0.1), noise=0.08, noise_scale=12, seed=seed + 6)))
        P(PartSpec(f'wristskin_{side}', f'elbow_{side}', (0, 0, 0), kind='skin',
                   mesh=loft([(-0.30, 0.026, 0.024, 0, 0), (-0.43, 0.022, 0.02, 0, 0)], rings=Q(6), seg=Q(14))))
        P(PartSpec(f'wrist_{side}', f'elbow_{side}', (0, -0.43, 0), kind='none'))
        P(PartSpec(f'hand_aim_{side}', f'wrist_{side}', (0, 0, 0), kind='none'))
        palm = loft([(0.015, 0.024, 0.014, 0, 0), (0.0, 0.028, 0.015, 0, 0), (-0.085, 0.037, 0.012, 0, 0.002),
                     (-0.1, 0.034, 0.011, 0, 0.002)], rings=Q(12), seg=Q(16), round_start=0.015, round_end=0.01, noise=0.05,
                    noise_scale=60, seed=seed)
        thumb = tube_path([(0.03, -0.02, 0.012), (0.04, -0.06, 0.03), (0.035, -0.1, 0.038)], [0.009, 0.008, 0.006], seg=Q(8))
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
                             r0 * (1 - 0.15 * ts) * (1 + 0.25 * np.exp(-((ts - 0.05) ** 2) / 0.01) + 0.22 * np.exp(-((ts - 1.0) ** 2) / 0.01)), seg=Q(8))
            P(PartSpec(f'f{k}prox_{side}', f'f{k}a_{side}', (0, 0, 0), mesh=prox, kind='skin'))
            P(PartSpec(f'f{k}b_{side}', f'f{k}a_{side}', (0, -0.55 * L, 0), kind='none'))
            dist = tube_path([(0, -0.45 * L * t, 0.002 * t) for t in ts], r0 * 0.88 * (1 - 0.3 * ts ** 2), seg=Q(8))
            P(PartSpec(f'f{k}dist_{side}', f'f{k}b_{side}', (0, 0, 0), mesh=dist, kind='skin'))
            P(PartSpec(f'f{k}nail_{side}', f'f{k}b_{side}', (0, -0.45 * L + 0.009, -r0 * 0.62),
                       mesh=ellipsoid(r0 * 0.78, 0.0085, 0.0018, rings=Q(8), seg=Q(12)), kind='nail'))

    # ноги под платьем + стоптанные ботинки
    for side, sx in (('R', 1), ('L', -1)):
        P(PartSpec(f'hip_{side}', 'pelvis', (sx * 0.085, -0.05, 0), kind='none'))
        P(PartSpec(f'thigh_{side}', f'hip_{side}', (0, 0, 0), kind='linen',
                   mesh=loft([(0.04, 0.07, 0.07, 0, 0), (0.0, 0.075, 0.077, 0, 0), (-0.47, 0.05, 0.052, 0, 0)],
                             rings=Q(12), seg=Q(16), round_start=0.04, seed=seed)))
        P(PartSpec(f'knee_{side}', f'hip_{side}', (0, -THIGH, 0), kind='none'))
        P(PartSpec(f'shin_{side}', f'knee_{side}', (0, 0, 0), kind='wool',          # шерстяные чулки
                   mesh=loft([(0.03, 0.047, 0.049, 0, 0), (0.0, 0.048, 0.05, 0, 0), (-0.30, 0.036, 0.038, 0, 0)],
                             rings=Q(12), seg=Q(16), round_start=0.03, seed=seed)))
        P(PartSpec(f'valenok_{side}', f'knee_{side}', (0, 0, 0), kind='felt',          # голенище валенка
                   mesh=loft([(-0.47, 0.056, 0.058, 0, 0), (-0.32, 0.058, 0.06, 0, 0), (-0.2, 0.064, 0.066, 0, 0),
                              (-0.17, 0.068, 0.07, 0, 0), (-0.16, 0.05, 0.05, 0, 0)], rings=Q(16), seg=Q(20), noise=0.05,
                             noise_scale=14, seed=seed + 7)))
        P(PartSpec(f'ankle_{side}', f'knee_{side}', (0, -SHIN, 0), kind='none'))
        P(PartSpec(f'shoe_{side}', f'ankle_{side}', (0, 0, 0), kind='felt',
                   mesh=loft([(-0.07, 0.052, 0.058, 0, -0.012), (0.0, 0.058, 0.058, 0, -0.022), (0.12, 0.056, 0.046, 0, -0.04),
                              (0.2, 0.042, 0.036, 0, -0.045)], axis='z', rings=Q(14), seg=Q(18), round_start=0.035, round_end=0.035,
                             noise=0.06, noise_scale=16, seed=seed)))
    # ---- детали образа
    # концы пухового платка перекрещены на груди и завязаны узлом
    ends = []
    for sx in (1, -1):
        pts = [(sx * 0.15, 0.31, 0.11), (sx * 0.08, 0.22, 0.165), (-sx * 0.01, 0.12, 0.19), (-sx * 0.02, 0.085, 0.195)]
        ends.append(tube_path(pts, [0.022, 0.024, 0.022, 0.02], seg=Q(12)))
        hang = [(sx * 0.008, 0.07, 0.2), (sx * 0.025, -0.02, 0.2), (sx * 0.04, -0.12, 0.195), (sx * 0.05, -0.2, 0.19)]
        ends.append(tube_path(hang, [0.02, 0.022, 0.024, 0.026], seg=Q(12)))
    for e in ends:
        c = e.vertices.mean(0)
        e.vertices[:, 2] = c[2] + (e.vertices[:, 2] - c[2]) * 0.45       # плоские, как ткань
    P(PartSpec('shawl_ends', 'spine2', (0, 0, 0), mesh=merge(ends), kind='wool'))
    P(PartSpec('shawl_knot', 'spine2', (0, 0.085, 0.2), mesh=ellipsoid(0.03, 0.024, 0.022, rings=Q(12), seg=Q(16), noise=0.25, seed=9),
               kind='wool'))
    # кушак с кистями
    P(PartSpec('sash', 'spine1', (0, 0, 0), kind='sash',
               mesh=loft([(0.015, 0.168, 0.138, 0, 0.004), (0.02, 0.176, 0.146, 0, 0.004), (0.07, 0.176, 0.146, 0, 0.004),
                          (0.075, 0.168, 0.138, 0, 0.004)], rings=Q(8), seg=Q(48), noise=0.02, noise_scale=30, seed=5)))
    tassels = []
    for k, ox in enumerate((0.0, 0.025)):
        cord = [(0.1 + ox, 0.04, 0.13), (0.11 + ox, -0.05, 0.14), (0.115 + ox, -0.14, 0.145), (0.118 + ox, -0.2, 0.145)]
        tassels.append(tube_path(cord, [0.006] * 4, seg=Q(8)))
        end = np.array(cord[-1])
        for j in range(9):
            a = j / 9 * 2 * math.pi
            o = np.array([math.cos(a) * 0.006, 0, math.sin(a) * 0.006])
            tassels.append(tube_path([end + o, end + o * 1.6 + np.array([0, -0.05, 0]), end + o * 2.0 + np.array([0, -0.085, 0])],
                                     [0.0022, 0.002, 0.0015], seg=Q(4)))
    P(PartSpec('sash_tassels', 'spine1', (0, 0, 0), mesh=merge(tassels), kind='sash'))
    # варежки на резинке: висят у манжет
    for side, sx in (('R', 1), ('L', -1)):
        P(PartSpec(f'mitt_{side}', f'elbow_{side}', (0, -0.38, 0.03), kind='none'))
        string = tube_path([(0, 0, 0), (0.005, -0.09, 0.0), (0.0, -0.18, 0.0)], [0.0022] * 3, seg=Q(5))
        mitt = loft([(-0.335, 0.012, 0.008, 0, 0), (-0.32, 0.036, 0.018, 0, 0), (-0.27, 0.042, 0.021, 0, 0), (-0.22, 0.04, 0.02, 0, 0),
                     (-0.2, 0.042, 0.022, 0, 0), (-0.18, 0.04, 0.02, 0, 0)], rings=Q(18), seg=Q(20), round_start=0.02, noise=0.04,
                    noise_scale=60, seed=4)
        thumb = tube_path([(sx * 0.035, -0.23, 0.0), (sx * 0.05, -0.26, 0.0), (sx * 0.05, -0.285, 0.0)], [0.012, 0.011, 0.008], seg=Q(10))
        P(PartSpec(f'mitt_string_{side}', f'mitt_{side}', (0, 0, 0), mesh=string, kind='sash'))
        P(PartSpec(f'mitten_{side}', f'mitt_{side}', (0, 0, 0), mesh=merge([mitt, thumb]), kind='mitten'))
    # галоши на валенках
    for side in ('R', 'L'):
        P(PartSpec(f'galosh_{side}', f'ankle_{side}', (0, 0, 0), kind='rubber',
                   mesh=loft([(-0.078, 0.06, 0.03, 0, -0.056), (0.0, 0.066, 0.034, 0, -0.06), (0.13, 0.064, 0.033, 0, -0.064),
                              (0.215, 0.048, 0.027, 0, -0.064)], axis='z', rings=Q(16), seg=Q(24), round_start=0.03,
                             round_end=0.035, power=2.6)))

    # ---- снег и лёд прямо на ней
    def snowcap(rx, ry, rz, seed_, flat=0.35):
        m = ellipsoid(rx, ry, rz, rings=Q(14), seg=Q(22), noise=0.35, seed=seed_)
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
                     rings=Q(8), seg=Q(8), noise=0.3, noise_scale=60, seed=seed_)
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
