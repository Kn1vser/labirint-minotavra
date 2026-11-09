"""
Геометрия «Бабки» — жуткой советской бабушки.

Платок с розами, ватник, ситцевый халат с фартуком, чулки, валенки с галошами,
круглые очки, авоська с банкой огурцов и батоном, вязание. Рост 2.2 м (сгорбившись ~1.9),
шея в шерстяном шарфе выдвигается ещё на полметра. Перёд смотрит в +z.
"""
import math

import numpy as np

from .frost_mesh import MeshData, PartSpec, _finalize, ellipsoid, loft
from .kochkar_mesh import merge, tube_path

PELVIS_Y = 1.06
THIGH = 0.48
SHIN = 0.46
NECK_MAX = 0.55


def cut(mesh, keep):
    """Убирает треугольники, центр которых не проходит keep(centroids) -> bool[]."""
    c = mesh.vertices[mesh.triangles].mean(axis=1)
    m = keep(c)
    return MeshData(mesh.vertices, mesh.triangles[m], mesh.uvs, mesh.normals)


def circle(center, r, n=24, axis='z'):
    pts = []
    for i in range(n + 1):
        a = 2 * math.pi * i / n
        if axis == 'z':
            pts.append((center[0] + r * math.cos(a), center[1] + r * math.sin(a), center[2]))
    return pts


def _quilt(S, TH, P):
    # стёганые валики ватника
    return 1 + 0.025 * np.abs(np.sin(S * 40))


def _folds(S, TH, P):
    depth = np.clip(-S / 0.6, 0, 1)
    return 1 + 0.05 * depth * np.sin(TH * 9 + np.sin(TH * 3) * 1.5)


def build_babka(seed=4):
    rng = np.random.default_rng(seed)
    parts = []
    P = parts.append
    P(PartSpec('pelvis', '', (0, PELVIS_Y, 0), kind='none'))

    # халат-юбка с фартуком (фартук рисует шейдер спереди)
    skirt = loft([(-0.70, 0.29, 0.26, 0, 0.02), (-0.66, 0.305, 0.275, 0, 0.02), (-0.5, 0.28, 0.25, 0, 0.02),
                  (-0.25, 0.24, 0.21, 0, 0.01), (0.0, 0.19, 0.16, 0, 0), (0.10, 0.16, 0.13, 0, 0)],
                 rings=34, seg=48, shape=_folds, noise=0.03, noise_scale=6, seed=seed)
    P(PartSpec('skirt', 'pelvis', (0, 0, 0), mesh=skirt, kind='dress'))

    # туловище: два позвонка, горб
    P(PartSpec('spine1', 'pelvis', (0, 0.08, 0), kind='none'))
    lower = loft([(-0.14, 0.205, 0.175, 0, 0.0), (0.0, 0.21, 0.175, 0, 0), (0.22, 0.215, 0.17, 0, 0),
                  (0.42, 0.22, 0.175, 0, -0.01), (0.47, 0.20, 0.16, 0, -0.01)],
                 rings=26, seg=36, shape=_quilt, noise=0.02, noise_scale=8, seed=seed)
    P(PartSpec('torso_low', 'spine1', (0, 0, 0), mesh=lower, kind='vatnik'))
    P(PartSpec('spine2', 'spine1', (0, 0.42, 0), kind='none'))
    upper = loft([(-0.05, 0.215, 0.17, 0, -0.01), (0.10, 0.22, 0.18, 0, -0.03), (0.22, 0.21, 0.19, 0, -0.055),
                  (0.30, 0.175, 0.155, 0, -0.045), (0.36, 0.105, 0.10, 0, -0.02), (0.40, 0.05, 0.05, 0, 0)],
                 rings=26, seg=36, shape=_quilt, noise=0.02, noise_scale=8, seed=seed + 1)
    P(PartSpec('torso_up', 'spine2', (0, 0, 0), mesh=upper, kind='vatnik'))

    # шея в шарфе (выдвигается) и голова
    P(PartSpec('neck', 'spine2', (0, 0.33, 0.0), kind='none'))
    P(PartSpec('neck_slide', 'neck', (0, 0, 0), kind='none'))
    neck = loft([(-0.58, 0.06, 0.06, 0, 0), (0.0, 0.062, 0.062, 0, 0), (0.08, 0.058, 0.058, 0, 0.005)],
                rings=40, seg=20, shape=lambda S, TH, Pp: 1 + 0.12 * np.abs(np.sin(S * 38 + TH * 0.16)),
                noise=0.04, noise_scale=30, seed=seed)
    P(PartSpec('scarf_neck', 'neck_slide', (0, 0, 0), mesh=neck, kind='knit_grey'))
    P(PartSpec('head', 'neck_slide', (0, 0.06, 0.01), kind='none'))
    HC, HR = (0, 0.10, 0.02), (0.082, 0.108, 0.095)
    P(PartSpec('skull', 'head', (0, 0, 0), mesh=ellipsoid(*HR, rings=26, seg=34, center=HC), kind='skin'))
    fz = HC[2] + HR[2]

    platok = loft([(-0.10, 0.112, 0.102, 0, -0.045), (-0.03, 0.102, 0.106, 0, -0.02), (0.04, 0.097, 0.112, 0, -0.004),
                   (0.12, 0.099, 0.113, 0, 0.0), (0.18, 0.088, 0.1, 0, -0.005), (0.222, 0.05, 0.06, 0, -0.01),
                   (0.238, 0.01, 0.01, 0, -0.01)], rings=34, seg=44, noise=0.03, noise_scale=10, seed=seed)
    platok = cut(platok, lambda c: ~((c[:, 2] > 0.0) & ((c[:, 0] / 0.066) ** 2 + ((c[:, 1] - 0.088) / 0.088) ** 2 < 1)))
    P(PartSpec('platok', 'head', (0, 0, 0), mesh=platok, kind='platok'))
    P(PartSpec('knot', 'head', (0, -0.005, 0.07), mesh=ellipsoid(0.03, 0.022, 0.026, rings=10, seg=14, noise=0.2, seed=2),
               kind='platok'))
    tails = [tube_path([(0, 0, 0), (sx * 0.02, -0.035, 0.01), (sx * 0.03, -0.07, 0.005)], [0.016, 0.017, 0.012], seg=8)
             for sx in (1, -1)]
    for t in tails:
        t.vertices[:, 2] = t.vertices[:, 2] * 0.45             # плоские концы платка
    P(PartSpec('platok_tails', 'knot', (0, 0, 0), mesh=merge(tails), kind='platok'))

    # лицо: нос, улыбка, золотой зуб, очки
    P(PartSpec('nose', 'head', (0, 0.085, fz - 0.004), rot=(-15, 0, 0),
               mesh=ellipsoid(0.012, 0.021, 0.015, rings=10, seg=14), kind='skin'))

    def on_face(x, y, lift=0.002):
        q = 1 - (x / HR[0]) ** 2 - ((y - HC[1]) / HR[1]) ** 2
        return HC[2] + HR[2] * math.sqrt(max(q, 0)) + lift

    smile = []
    for i in range(17):
        x = -0.058 + 0.116 * i / 16
        y = 0.040 + 0.03 * (x / 0.058) ** 2
        smile.append((x, y, on_face(x, y)))
    widths = [0.002 + 0.0075 * math.sin(math.pi * i / 16) ** 0.7 for i in range(17)]   # серп: шире в середине
    P(PartSpec('smile', 'head', (0, 0, 0), mesh=tube_path(smile, widths, seg=10), kind='mouth'))
    P(PartSpec('gold_tooth', 'head', (0.016, 0.044, on_face(0.016, 0.044, 0.004)),
               mesh=ellipsoid(0.0065, 0.0075, 0.003, rings=8, seg=10), kind='gold'))
    for sx in (1, -1):
        cx, cy = sx * 0.035, 0.108
        cz = on_face(cx, cy, 0.012)
        P(PartSpec(f'lens_{sx}', 'head', (cx, cy, cz), mesh=ellipsoid(0.026, 0.026, 0.006, rings=10, seg=20), kind='lens'))
        P(PartSpec(f'frame_{sx}', 'head', (cx, cy, cz), mesh=tube_path(circle((0, 0, 0), 0.027, 28), [0.0035] * 29, seg=6),
                   kind='rubber'))
        temple = [(sx * 0.027, 0, 0), (sx * 0.05, 0.0, -0.03), (sx * 0.05, -0.005, -0.09)]
        P(PartSpec(f'temple_{sx}', f'frame_{sx}', (0, 0, 0), mesh=tube_path(temple, [0.0025] * 3, seg=6), kind='rubber'))
    bz = on_face(0, 0.112, 0.014)
    P(PartSpec('bridge', 'head', (0, 0.112, bz), mesh=tube_path([(-0.009, 0, 0), (0, 0.004, 0.002), (0.009, 0, 0)],
                                                                 [0.0025] * 3, seg=6), kind='rubber'))

    # руки — длинные (около метра)
    for side, sx in (('R', 1), ('L', -1)):
        P(PartSpec(f'shoulder_{side}', 'spine2', (sx * 0.205, 0.27, -0.02), kind='none'))
        upper_arm = loft([(0.05, 0.06, 0.06, 0, 0), (0.0, 0.068, 0.068, 0, 0), (-0.42, 0.055, 0.055, 0, 0),
                          (-0.46, 0.052, 0.052, 0, 0)], rings=22, seg=20, round_start=0.05, shape=_quilt,
                         noise=0.03, noise_scale=10, seed=seed + 3)
        P(PartSpec(f'upperarm_{side}', f'shoulder_{side}', (0, 0, 0), mesh=upper_arm, kind='vatnik'))
        P(PartSpec(f'elbow_{side}', f'shoulder_{side}', (0, -0.43, 0), kind='none'))
        fore = loft([(0.03, 0.052, 0.052, 0, 0), (0.0, 0.054, 0.054, 0, 0), (-0.36, 0.047, 0.047, 0, 0),
                     (-0.40, 0.055, 0.055, 0, 0), (-0.43, 0.054, 0.054, 0, 0)], rings=22, seg=20, round_start=0.03,
                    shape=_quilt, noise=0.03, noise_scale=10, seed=seed + 4)
        P(PartSpec(f'forearm_{side}', f'elbow_{side}', (0, 0, 0), mesh=fore, kind='vatnik'))
        P(PartSpec(f'wrist_{side}', f'elbow_{side}', (0, -0.43, 0), kind='none'))
        palm = loft([(0.02, 0.028, 0.02, 0, 0), (0.0, 0.03, 0.022, 0, 0), (-0.08, 0.04, 0.016, 0, 0.003),
                     (-0.1, 0.036, 0.014, 0, 0.003)], rings=12, seg=16, round_start=0.02, round_end=0.012, seed=seed)
        fingers = []
        for k, (fx, L) in enumerate(((0.027, 0.12), (0.009, 0.14), (-0.009, 0.135), (-0.026, 0.11))):
            pts = [(fx, -0.095 - L * t, 0.004 + 0.04 * t * t) for t in np.linspace(0, 1, 7)]
            r = np.linspace(0.0085, 0.0055, 7) * (1 + 0.15 * np.sin(np.linspace(0, 3 * math.pi, 7)) ** 8)
            fingers.append(tube_path(pts, r, seg=8))
        fingers.append(tube_path([(sx * -0.0, -0.02, 0.018), (0.0, -0.06, 0.035), (0.0, -0.1, 0.04)], [0.01, 0.009, 0.007], seg=8))
        P(PartSpec(f'hand_{side}', f'wrist_{side}', (0, 0, 0), rot=(0, -sx * 90, 0), mesh=merge([palm] + fingers), kind='skin'))

    # авоська в правой руке, вязание в левой
    P(PartSpec('avoska', 'wrist_R', (0, -0.17, 0.02), kind='none'))
    handles = [tube_path([(sx * 0.05, -0.08, 0), (sx * 0.035, 0.0, 0), (0, 0.02, 0), (-sx * 0.0, 0.02, 0)], [0.004] * 4, seg=6)
               for sx in (1, -1)]
    P(PartSpec('avoska_handles', 'avoska', (0, 0, 0), mesh=merge(handles), kind='string'))
    net = ellipsoid(0.13, 0.17, 0.11, rings=20, seg=28, center=(0, -0.24, 0), noise=0.08, seed=5)
    P(PartSpec('avoska_net', 'avoska', (0, 0, 0), mesh=net, kind='net'))
    jar = loft([(-0.36, 0.06, 0.06, 0, 0), (-0.35, 0.064, 0.064, 0, 0), (-0.18, 0.064, 0.064, 0, 0), (-0.15, 0.05, 0.05, 0, 0),
                (-0.13, 0.045, 0.045, 0, 0)], rings=10, seg=24)
    P(PartSpec('jar', 'avoska', (-0.035, 0.0, 0.0), mesh=jar, kind='jar'))
    P(PartSpec('jar_lid', 'avoska', (-0.035, -0.125, 0), mesh=ellipsoid(0.047, 0.01, 0.047, rings=8, seg=20), kind='tin'))
    pickles = [ellipsoid(0.017, 0.05, 0.017, rings=8, seg=10, center=(rng.uniform(-0.03, 0.03), rng.uniform(-0.32, -0.22),
                                                                    rng.uniform(-0.03, 0.03)), noise=0.2, seed=int(i))
               for i in range(7)]
    P(PartSpec('pickles', 'avoska', (-0.035, 0, 0), mesh=merge(pickles), kind='pickle'))
    P(PartSpec('loaf', 'avoska', (0.055, -0.2, 0.015), rot=(10, 30, 70),
               mesh=ellipsoid(0.045, 0.11, 0.05, rings=12, seg=16, noise=0.05, seed=9), kind='bread'))

    P(PartSpec('knitting', 'wrist_L', (0, -0.15, 0.03), kind='none'))
    P(PartSpec('yarn', 'knitting', (0, -0.03, 0), mesh=ellipsoid(0.05, 0.05, 0.05, rings=14, seg=18, noise=0.08, seed=3),
               kind='knit_red'))
    needles = [tube_path([(-0.12, -0.1, -0.02), (0.14, 0.06, 0.03)], [0.0035, 0.003], seg=6),
               tube_path([(0.12, -0.09, -0.03), (-0.13, 0.07, 0.04)], [0.0035, 0.003], seg=6)]
    P(PartSpec('needles', 'knitting', (0, -0.03, 0), mesh=merge(needles), kind='tin'))

    # ноги: чулки, валенки с галошами
    for side, sx in (('R', 1), ('L', -1)):
        P(PartSpec(f'hip_{side}', 'pelvis', (sx * 0.09, -0.05, 0), kind='none'))
        P(PartSpec(f'thigh_{side}', f'hip_{side}', (0, 0, 0), kind='stocking',
                   mesh=loft([(0.04, 0.07, 0.07, 0, 0), (0.0, 0.078, 0.08, 0, 0), (-0.48, 0.055, 0.056, 0, 0)],
                             rings=16, seg=20, round_start=0.04, seed=seed)))
        P(PartSpec(f'knee_{side}', f'hip_{side}', (0, -THIGH, 0), kind='none'))
        P(PartSpec(f'shin_{side}', f'knee_{side}', (0, 0, 0), kind='stocking',
                   mesh=loft([(0.03, 0.055, 0.056, 0, 0), (0.0, 0.056, 0.058, 0, 0), (-0.16, 0.052, 0.054, 0, -0.005)],
                             rings=10, seg=20, round_start=0.03, seed=seed)))
        P(PartSpec(f'valenok_{side}', f'knee_{side}', (0, 0, 0), kind='felt',
                   mesh=loft([(-0.47, 0.062, 0.064, 0, 0), (-0.30, 0.066, 0.068, 0, 0), (-0.16, 0.072, 0.074, 0, 0),
                              (-0.13, 0.078, 0.08, 0, 0), (-0.12, 0.06, 0.06, 0, 0)], rings=16, seg=22, noise=0.05,
                             noise_scale=14, seed=seed + 7)))
        P(PartSpec(f'ankle_{side}', f'knee_{side}', (0, -SHIN, 0), kind='none'))
        P(PartSpec(f'foot_{side}', f'ankle_{side}', (0, 0, 0), kind='felt',
                   mesh=loft([(-0.06, 0.055, 0.05, 0, -0.02), (0.0, 0.06, 0.055, 0, -0.025), (0.12, 0.058, 0.045, 0, -0.035),
                              (0.19, 0.045, 0.035, 0, -0.04)], axis='z', rings=14, seg=20, round_start=0.03, round_end=0.03,
                             noise=0.04, noise_scale=14, seed=seed)))
        P(PartSpec(f'galosh_{side}', f'ankle_{side}', (0, 0, 0), kind='rubber',
                   mesh=loft([(-0.068, 0.06, 0.03, 0, -0.058), (0.0, 0.066, 0.036, 0, -0.062), (0.13, 0.064, 0.034, 0, -0.066),
                              (0.205, 0.048, 0.028, 0, -0.066)], axis='z', rings=14, seg=22, round_start=0.03,
                             round_end=0.035, power=2.6)))
    return _finalize(parts)
