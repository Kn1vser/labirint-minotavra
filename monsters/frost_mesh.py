"""
Процедурная геометрия для «Ледяного двойника».

Здесь нет Ursina — только numpy. Каждая функция возвращает MeshData:
вершины, треугольники, нормали и uv. Из них потом собираются Entity.

Главный инструмент — loft(): «протягиваем» эллиптическое сечение вдоль оси
и получаем гладкую трубку (рука, палец, торс). Радиусы задаются ключами,
между ключами — плавная интерполяция Катмулла–Рома.
"""
from dataclasses import dataclass, field
import math
import numpy as np


@dataclass
class MeshData:
    vertices: np.ndarray            # (N, 3)
    triangles: np.ndarray           # (M, 3) int
    uvs: np.ndarray                 # (N, 2)
    normals: np.ndarray = field(default=None)

    def finish(self):
        """Считает нормали и разворачивает треугольники наружу."""
        self.normals = vertex_normals(self.vertices, self.triangles)
        center = self.vertices.mean(axis=0)
        outward = np.einsum('ij,ij->i', self.normals, self.vertices - center).mean()
        if outward < 0:
            self.triangles = self.triangles[:, ::-1].copy()
            self.normals = -self.normals
        return self

    def to_ursina_args(self):
        return dict(
            vertices=[tuple(map(float, v)) for v in self.vertices],
            # Ursina/Panda (y-up-left) считает лицевой другую сторону — меняем порядок обхода
            triangles=[int(i) for i in self.triangles[:, ::-1].reshape(-1)],
            uvs=[tuple(map(float, u)) for u in self.uvs],
            normals=[tuple(map(float, n)) for n in self.normals],
        )


# ---------------------------------------------------------------- утилиты

def vertex_normals(v, t):
    n = np.zeros_like(v)
    a, b, c = v[t[:, 0]], v[t[:, 1]], v[t[:, 2]]
    fn = np.cross(b - a, c - a)                    # длина = 2*площадь, т.е. взвешивание по площади
    for k in range(3):
        np.add.at(n, t[:, k], fn)
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    ln[ln == 0] = 1
    return n / ln


def _hash(ix, iy, iz, seed):
    h = (ix * 374761393 + iy * 668265263 + iz * 2147483647 + seed * 144665) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return (h & 0xFFFF) / 65535.0


def value_noise(p, seed=0):
    """3D value-noise для массива точек (N,3) -> (N,) в диапазоне 0..1."""
    p = np.asarray(p, dtype=np.float64)
    i = np.floor(p).astype(np.int64)
    f = p - i
    f = f * f * (3 - 2 * f)
    out = 0
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                w = (f[:, 0] if dx else 1 - f[:, 0]) * (f[:, 1] if dy else 1 - f[:, 1]) * (f[:, 2] if dz else 1 - f[:, 2])
                out = out + w * _hash(i[:, 0] + dx, i[:, 1] + dy, i[:, 2] + dz, seed)
    return out


def fbm(p, octaves=3, seed=0):
    s, a, q = 0.0, 0.5, np.asarray(p, dtype=np.float64)
    for o in range(octaves):
        s = s + a * value_noise(q, seed + o)
        q = q * 2.03
        a *= 0.5
    return s


def _catmull(keys_t, keys_v, t):
    """Гладкая интерполяция значений keys_v в точках t (ключи по возрастанию)."""
    keys_t = np.asarray(keys_t, float)
    keys_v = np.asarray(keys_v, float)
    t = np.clip(t, keys_t[0], keys_t[-1])
    idx = np.clip(np.searchsorted(keys_t, t, side='right') - 1, 0, len(keys_t) - 2)
    t0, t1 = keys_t[idx], keys_t[idx + 1]
    u = (t - t0) / np.where(t1 - t0 == 0, 1, t1 - t0)
    p0 = keys_v[np.clip(idx - 1, 0, len(keys_v) - 1)]
    p1 = keys_v[idx]
    p2 = keys_v[idx + 1]
    p3 = keys_v[np.clip(idx + 2, 0, len(keys_v) - 1)]
    u2, u3 = u * u, u * u * u
    return 0.5 * ((2 * p1) + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u2 + (-p0 + 3 * p1 - 3 * p2 + p3) * u3)


# ---------------------------------------------------------------- loft

def loft(keys, rings=36, seg=24, axis='y', round_start=0.0, round_end=0.0,
         noise=0.0, noise_scale=18.0, seed=0, shape=None, power=2.0):
    """
    keys: список (s, ra, rb, ca, cb)
        s      — координата вдоль оси (axis)
        ra, rb — радиусы эллипса сечения
        ca, cb — смещение центра сечения (для изгибов)
      Для axis='y' сечение лежит в плоскости (x, z), для axis='z' — в (x, y).
    round_*: длина скругления концов (в метрах), чтобы концы были как полусферы.
    noise:   относительная неровность поверхности (кора, лёд).
    shape:   функция (s, theta, P) -> множитель радиуса, для рёбер, желобков и т.п.
    power:   2 — эллипс, больше — «квадратнее» сечение (суперэллипс).
    """
    keys = sorted(keys, key=lambda k: k[0])
    ks = [k[0] for k in keys]
    s = np.linspace(ks[0], ks[-1], rings)
    ra = _catmull(ks, [k[1] for k in keys], s)
    rb = _catmull(ks, [k[2] for k in keys], s)
    ca = _catmull(ks, [k[3] for k in keys], s)
    cb = _catmull(ks, [k[4] for k in keys], s)

    # скругление концов
    fac = np.ones_like(s)
    if round_start > 0:
        d = s - s[0]
        m = d < round_start
        fac[m] *= np.sqrt(np.clip(1 - ((round_start - d[m]) / round_start) ** 2, 0.0025, 1))
    if round_end > 0:
        d = s[-1] - s
        m = d < round_end
        fac[m] *= np.sqrt(np.clip(1 - ((round_end - d[m]) / round_end) ** 2, 0.0025, 1))

    theta = np.linspace(0, 2 * math.pi, seg + 1)        # последняя колонка дублирует первую (шов для uv)
    S, TH = np.meshgrid(s, theta, indexing='ij')
    c, sn = np.cos(TH), np.sin(TH)
    e = 2.0 / power
    cs = np.sign(c) * np.abs(c) ** e
    ss = np.sign(sn) * np.abs(sn) ** e
    A = ca[:, None] + ra[:, None] * fac[:, None] * cs
    B = cb[:, None] + rb[:, None] * fac[:, None] * ss

    if axis == 'y':
        P = np.stack([A, S, B], axis=-1)
    else:  # 'z'
        P = np.stack([A, B, S], axis=-1)

    mult = np.ones_like(S)
    if shape is not None:
        mult = mult * shape(S, TH, P)
    if noise > 0:
        flat = P.reshape(-1, 3)
        n = fbm(flat * noise_scale, 3, seed).reshape(S.shape) - 0.5
        mult = mult * (1 + noise * n)
    # шов: последняя колонка = первая
    mult[:, -1] = mult[:, 0]

    center = np.stack([ca, s, cb], -1) if axis == 'y' else np.stack([ca, cb, s], -1)
    P = center[:, None, :] + (P - center[:, None, :]) * mult[..., None]

    verts = P.reshape(-1, 3)
    U = TH / (2 * math.pi)
    V = (S - s[0]) / max(s[-1] - s[0], 1e-6)
    uvs = np.stack([U, V], -1).reshape(-1, 2)

    tris = []
    cols = seg + 1
    for i in range(rings - 1):
        for j in range(seg):
            a = i * cols + j
            b = a + 1
            c2 = a + cols
            d = c2 + 1
            tris.append((a, c2, b))
            tris.append((b, c2, d))
    tris = np.array(tris, dtype=np.int64)

    # крышки на концах
    verts = list(verts)
    uvs = list(uvs)
    extra = []
    for ring_i, end_s in ((0, s[0]), (rings - 1, s[-1])):
        ci = len(verts)
        cpos = center[ring_i].copy()
        verts.append(cpos)
        uvs.append((0.5, 0.0 if ring_i == 0 else 1.0))
        base = ring_i * cols
        for j in range(seg):
            if ring_i == 0:
                extra.append((ci, base + j, base + j + 1))
            else:
                extra.append((ci, base + j + 1, base + j))
    tris = np.vstack([tris, np.array(extra, dtype=np.int64)])
    return MeshData(np.array(verts), tris, np.array(uvs)).finish()


def ellipsoid(rx, ry, rz, rings=24, seg=32, center=(0, 0, 0), noise=0.0, seed=0, power=2.0):
    k = []
    n = 13
    for i in range(n):
        t = -1 + 2 * i / (n - 1)
        r = math.sqrt(max(1 - t * t, 0.0))
        k.append((center[1] + t * ry, rx * r + 1e-4, rz * r + 1e-4, center[0], center[2]))
    return loft(k, rings=rings, seg=seg, noise=noise, seed=seed, power=power)


def face_cap(rx, ry, rz, center=(0, 0, 0), theta_max=62, phi_low=-58, phi_high=42, inflate=1.006, res=28):
    """
    Овальная «маска»-зеркало на передней части головы-эллипсоида.
    uv идёт от 0 до 1 по ширине и высоте овала — по ним шейдер кладёт отражение.
    """
    verts, uvs = [], []
    for j in range(res + 1):
        v = j / res
        for i in range(res + 1):
            u = i / res
            # квадрат -> круг (мягкое отображение), чтобы край был овальным
            x, y = u * 2 - 1, v * 2 - 1
            dx = x * math.sqrt(max(1 - y * y / 2, 0))
            dy = y * math.sqrt(max(1 - x * x / 2, 0))
            th = math.radians(dx * theta_max)
            ph = math.radians(phi_low + (dy * 0.5 + 0.5) * (phi_high - phi_low))
            px = center[0] + rx * inflate * math.sin(th) * math.cos(ph)
            py = center[1] + ry * inflate * math.sin(ph)
            pz = center[2] + rz * inflate * math.cos(th) * math.cos(ph)
            verts.append((px, py, pz))
            uvs.append((dx * 0.5 + 0.5, dy * 0.5 + 0.5))
    tris = []
    cols = res + 1
    for j in range(res):
        for i in range(res):
            a = j * cols + i
            tris.append((a, a + 1, a + cols))
            tris.append((a + 1, a + cols + 1, a + cols))
    md = MeshData(np.array(verts), np.array(tris), np.array(uvs))
    md.normals = vertex_normals(md.vertices, md.triangles)
    # нормали должны смотреть вперёд (+z)
    if md.normals[:, 2].mean() < 0:
        md.triangles = md.triangles[:, ::-1].copy()
        md.normals = -md.normals
    return md


def crack_ribbon(length=0.09, width=0.006, segments=14, seed=3, radius=0.032, center_z=0.0):
    """
    Тонкая рваная трещина-лента, обёрнутая по передней стороне цилиндра (шеи).
    uv.x — поперёк трещины (0..1), uv.y — вдоль.
    """
    rng = np.random.default_rng(seed)
    verts, uvs = [], []
    xoff = 0.0
    for i in range(segments + 1):
        t = i / segments
        y = (t - 0.5) * length
        xoff += rng.uniform(-1, 1) * 0.0035
        xoff *= 0.75
        w = width * math.sin(math.pi * t) ** 0.6 * rng.uniform(0.6, 1.25) + 1e-4
        for side in (-1, 1):
            x = xoff + side * w
            ang = x / radius
            verts.append((radius * math.sin(ang), y, center_z + radius * math.cos(ang) + 0.0012))
            uvs.append((0.0 if side < 0 else 1.0, t))
    tris = []
    for i in range(segments):
        a = i * 2
        tris.append((a, a + 1, a + 2))
        tris.append((a + 1, a + 3, a + 2))
    md = MeshData(np.array(verts), np.array(tris), np.array(uvs))
    md.normals = vertex_normals(md.vertices, md.triangles)
    if md.normals[:, 2].mean() < 0:
        md.triangles = md.triangles[:, ::-1].copy()
        md.normals = -md.normals
    return md


def shard(size=0.03, rng=None):
    """Осколок «кожи-льда» — неровный треугольный кусочек с толщиной."""
    rng = rng or np.random.default_rng()
    pts = [(rng.uniform(-1, 1) * size, rng.uniform(-1, 1) * size, 0) for _ in range(3)]
    th = size * 0.15
    v = np.array(pts + [(x, y, -th) for x, y, _ in pts])
    t = np.array([(0, 1, 2), (3, 5, 4), (0, 3, 1), (1, 3, 4), (1, 4, 2), (2, 4, 5), (2, 5, 0), (0, 5, 3)])
    md = MeshData(v, t, np.zeros((6, 2)))
    md.normals = vertex_normals(v, t)
    return md


# ---------------------------------------------------------------- риг

@dataclass
class PartSpec:
    name: str
    parent: str            # имя родителя ('' — корень)
    pos: tuple             # позиция шарнира относительно родителя
    rot: tuple = (0, 0, 0)  # поза покоя (градусы, как в Ursina)
    mesh: MeshData = None
    kind: str = 'shell'    # shell | face | crack | skin | cloth | eye | dark
    color: tuple = (1, 1, 1)
    body_pos: tuple = (0, 0, 0)  # примерная позиция в пространстве тела (для узоров)


def _finalize(parts):
    by = {p.name: p for p in parts}
    for p in parts:
        bp = np.array(p.pos, float)
        q = by.get(p.parent)
        while q is not None:
            bp += np.array(q.pos, float)
            q = by.get(q.parent)
        p.body_pos = tuple(bp)
    return parts


# ---------- истинный облик: ~2.8 м, худой, пустая оболочка

def _torso_shape_true(S, TH, P):
    m = np.ones_like(S)
    front = np.cos(TH - math.pi / 2)        # theta=pi/2 -> +z (перёд)
    # рёбра — тонкие горизонтальные гребни на груди
    rib = (np.sin((S - 1.84) * 62) * 0.5 + 0.5) ** 3
    ribzone = np.clip(1 - np.abs(S - 1.98) / 0.16, 0, 1)
    m += 0.022 * rib * ribzone * np.clip(front, 0, 1)
    # желобок позвоночника
    m -= 0.07 * np.exp(-((TH - 3 * math.pi / 2) ** 2) / 0.02) * np.clip((S - 1.4) / 0.4, 0, 1)
    # впалый живот
    m -= 0.05 * np.clip(front, 0, 1) ** 2 * np.exp(-((S - 1.62) ** 2) / 0.006)
    return m


def build_true_form(seed=7):
    """Возвращает список PartSpec истинного облика (высота ~2.8 м, лицо смотрит в +z)."""
    parts = []
    N = dict(noise=0.05, noise_scale=22, seed=seed)

    parts.append(PartSpec('pelvis', '', (0, 1.38, 0), mesh=None, kind='none'))
    torso = loft([
        (1.29, 0.070, 0.060, 0, 0.000),
        (1.36, 0.130, 0.084, 0, 0.000),
        (1.45, 0.150, 0.092, 0, 0.000),
        (1.56, 0.126, 0.080, 0, 0.006),
        (1.68, 0.120, 0.078, 0, 0.010),
        (1.80, 0.138, 0.088, 0, 0.014),
        (1.94, 0.166, 0.100, 0, 0.016),
        (2.05, 0.188, 0.104, 0, 0.012),
        (2.14, 0.212, 0.094, 0, 0.000),
        (2.20, 0.200, 0.080, 0, -0.006),
        (2.245, 0.120, 0.060, 0, -0.006),
        (2.275, 0.045, 0.038, 0, 0.000),
    ], rings=64, seg=40, round_start=0.05, shape=_torso_shape_true, power=2.3, **N)
    torso.vertices -= np.array([0, 1.38, 0])
    parts.append(PartSpec('torso', 'pelvis', (0, 0, 0), mesh=torso))

    # шея и голова
    neck = loft([(-0.04, 0.050, 0.046, 0, -0.004), (0.0, 0.042, 0.040, 0, 0.0), (0.10, 0.030, 0.032, 0, 0.008),
                 (0.20, 0.030, 0.032, 0, 0.016), (0.245, 0.036, 0.036, 0, 0.02), (0.265, 0.02, 0.02, 0, 0.02)],
                rings=28, seg=24, round_end=0.02, **N)
    parts.append(PartSpec('neck', 'pelvis', (0, 2.25 - 1.38, -0.01), mesh=neck))
    parts.append(PartSpec('throat_crack', 'neck', (0, 0.115, 0.008),
                          mesh=crack_ribbon(length=0.085, width=0.0055, radius=0.0315), kind='crack'))
    parts.append(PartSpec('head', 'neck', (0, 0.225, 0.02), mesh=None, kind='none'))
    HR = (0.104, 0.166, 0.118)
    HC = (0, 0.15, 0.006)
    head = ellipsoid(*HR, rings=32, seg=40, center=HC, noise=0.025, seed=seed + 1)
    parts.append(PartSpec('skull', 'head', (0, 0, 0), mesh=head))
    parts.append(PartSpec('face', 'head', (0, 0, 0), mesh=face_cap(*HR, center=HC), kind='face'))

    # руки
    for side, sx in (('R', 1), ('L', -1)):
        parts.append(PartSpec(f'shoulder_{side}', 'pelvis', (sx * 0.212, 2.165 - 1.38, -0.012),
                              rot=(0, 0, sx * -4.0), kind='none'))
        upper = loft([(0.05, .040, .040, 0, 0), (0.0, .057, .057, 0, 0), (-0.10, .052, .054, 0, 0),
                      (-0.45, .037, .039, 0, 0), (-0.58, .031, .033, 0, 0), (-0.61, .029, .029, 0, 0)],
                     rings=40, seg=24, round_start=0.05, round_end=0.03, **N)
        parts.append(PartSpec(f'upperarm_{side}', f'shoulder_{side}', (0, 0, 0), mesh=upper))
        parts.append(PartSpec(f'elbow_{side}', f'shoulder_{side}', (0, -0.58, 0), rot=(-4, 0, 0), kind='none'))
        fore = loft([(0.03, .029, .029, 0, 0), (0.0, .035, .035, 0, 0), (-0.10, .037, .035, 0, 0),
                     (-0.40, .025, .023, 0, 0), (-0.53, .020, .017, 0, 0), (-0.565, .019, .016, 0, 0)],
                    rings=40, seg=24, round_start=0.03, round_end=0.02, **N)
        parts.append(PartSpec(f'forearm_{side}', f'elbow_{side}', (0, 0, 0), mesh=fore))
        parts.append(PartSpec(f'wrist_{side}', f'elbow_{side}', (0, -0.545, 0), kind='none'))
        palm = loft([(0.02, .016, .020, 0, 0), (0.0, .014, .028, 0, 0), (-0.06, .013, .036, 0, 0),
                     (-0.105, .012, .034, 0, 0), (-0.125, .010, .022, 0, 0)],
                    rings=18, seg=20, round_start=0.02, round_end=0.015, **N)
        parts.append(PartSpec(f'hand_{side}', f'wrist_{side}', (0, 0, 0), mesh=palm))
        # пальцы: длинные, тонкие, чуть загнутые к телу
        fingers = [('index', 0.026, 0.215), ('middle', 0.009, 0.245), ('ring', -0.008, 0.228), ('pinky', -0.024, 0.19)]
        for k, (fname, z, L) in enumerate(fingers):
            fk = []
            for i in range(9):
                t = i / 8
                r = 0.0088 * (1 - 0.55 * t)
                bump = 1 + 0.16 * math.exp(-((t - 0.36) ** 2) / 0.003) + 0.12 * math.exp(-((t - 0.68) ** 2) / 0.003)
                curl = -sx * 0.06 * t * t * L / 0.22
                fk.append((-t * L, r * bump, r * bump * 0.92, curl, 0.004 * t))
            fm = loft(fk, rings=30, seg=12, round_start=0.008, round_end=0.012, noise=0.04, noise_scale=40, seed=seed + k)
            parts.append(PartSpec(f'finger_{fname}_{side}', f'hand_{side}', (0, -0.108, z),
                                  rot=(0, 0, sx * (2 + k * 1.5)), mesh=fm))
        tk = []
        for i in range(7):
            t = i / 6
            r = 0.010 * (1 - 0.5 * t)
            tk.append((-t * 0.13, r, r, -sx * 0.01 * t, 0.01 * t))
        tm = loft(tk, rings=20, seg=12, round_start=0.008, round_end=0.01, noise=0.04, noise_scale=40, seed=seed + 9)
        parts.append(PartSpec(f'thumb_{side}', f'hand_{side}', (-sx * 0.004, -0.035, 0.03),
                              rot=(-22, 0, sx * -14), mesh=tm))

    # ноги
    for side, sx in (('R', 1), ('L', -1)):
        parts.append(PartSpec(f'hip_{side}', 'pelvis', (sx * 0.094, 0, 0), kind='none'))
        thigh = loft([(0.05, .050, .050, 0, 0), (0.0, .073, .076, 0, 0.004), (-0.10, .071, .073, 0, 0.006),
                      (-0.35, .055, .058, 0, 0.004), (-0.60, .042, .045, 0, 0), (-0.69, .037, .039, 0, 0)],
                     rings=44, seg=24, round_start=0.05, round_end=0.03, **N)
        parts.append(PartSpec(f'thigh_{side}', f'hip_{side}', (0, 0, 0), mesh=thigh))
        parts.append(PartSpec(f'knee_{side}', f'hip_{side}', (0, -0.66, 0), kind='none'))
        shin = loft([(0.03, .036, .038, 0, 0), (0.0, .042, .045, 0, 0), (-0.12, .045, .050, 0, -0.006),
                     (-0.40, .031, .033, 0, -0.002), (-0.60, .026, .027, 0, 0), (-0.645, .024, .025, 0, 0)],
                    rings=44, seg=24, round_start=0.03, round_end=0.02, **N)
        parts.append(PartSpec(f'shin_{side}', f'knee_{side}', (0, 0, 0), mesh=shin))
        parts.append(PartSpec(f'ankle_{side}', f'knee_{side}', (0, -0.62, 0), kind='none'))
        foot = loft([(-0.05, .028, .030, 0, -0.050), (0.0, .034, .040, 0, -0.058), (0.08, .040, .028, sx * 0.004, -0.076),
                     (0.18, .037, .017, sx * 0.008, -0.088), (0.25, .020, .010, sx * 0.01, -0.092)],
                    axis='z', rings=30, seg=20, round_start=0.03, round_end=0.02, power=2.6, **N)
        parts.append(PartSpec(f'foot_{side}', f'ankle_{side}', (0, 0, 0), mesh=foot))

    return _finalize(parts)


# ---------- маска: обычный человек ~1.8 м

def build_human(seed=11, palette=None):
    """
    Человеческая «маска» (и наблюдатель в демо). palette — цвета одежды/кожи.
    """
    pal = dict(skin=(0.86, 0.68, 0.57), coat=(0.24, 0.21, 0.19), pants=(0.15, 0.15, 0.17),
               boots=(0.07, 0.06, 0.05), hair=(0.17, 0.12, 0.09), eyes=(0.25, 0.33, 0.38), lips=(0.66, 0.40, 0.38))
    if palette:
        pal.update(palette)
    parts = []
    N = dict(noise=0.02, noise_scale=14, seed=seed)
    parts.append(PartSpec('pelvis', '', (0, 0.93, 0), kind='none'))

    def coat_shape(S, TH, P):
        m = np.ones_like(S)
        front = np.cos(TH - math.pi / 2)
        m += 0.03 * np.clip(front, 0, 1) * np.exp(-((S - 1.27) ** 2) / 0.004)   # грудь
        # складки полы
        m += 0.018 * np.sin(TH * 7) * np.clip((0.95 - S) / 0.3, 0, 1)
        return m

    torso = loft([
        (0.60, 0.200, 0.150, 0, 0.0),
        (0.75, 0.190, 0.140, 0, 0.0),
        (0.92, 0.180, 0.130, 0, 0.0),
        (1.05, 0.165, 0.118, 0, 0.004),
        (1.20, 0.180, 0.122, 0, 0.008),
        (1.32, 0.200, 0.120, 0, 0.004),
        (1.42, 0.200, 0.105, 0, -0.004),
        (1.47, 0.130, 0.080, 0, -0.006),
        (1.50, 0.060, 0.055, 0, 0.0),
    ], rings=48, seg=40, shape=coat_shape, power=2.4, **N)
    torso.vertices -= np.array([0, 0.93, 0])
    parts.append(PartSpec('torso', 'pelvis', (0, 0, 0), mesh=torso, kind='cloth', color=pal['coat']))

    neck = loft([(-0.03, .055, .055, 0, -.005), (0.0, .050, .052, 0, 0), (0.10, .046, .050, 0, 0.006), (0.13, .04, .04, 0, 0.008)],
                rings=16, seg=24, round_end=0.02, **N)
    parts.append(PartSpec('neck', 'pelvis', (0, 1.47 - 0.93, -0.005), mesh=neck, kind='skin', color=pal['skin']))
    parts.append(PartSpec('head', 'neck', (0, 0.10, 0.008), kind='none'))
    HR = (0.078, 0.112, 0.094)
    HC = (0, 0.105, 0.006)

    def head_shape(S, TH, P):
        # подбородок и скулы: чуть уже внизу спереди
        m = np.ones_like(S)
        front = np.clip(np.cos(TH - math.pi / 2), 0, 1)
        low = np.clip((HC[1] - S) / HR[1], 0, 1)
        m -= 0.10 * low * low * (1 - front * 0.4)
        return m

    hk = []
    for i in range(15):
        t = -1 + 2 * i / 14
        r = math.sqrt(max(1 - t * t, 0)) + 1e-4
        hk.append((HC[1] + t * HR[1], HR[0] * r, HR[2] * r, 0, HC[2]))
    parts.append(PartSpec('skull', 'head', (0, 0, 0), mesh=loft(hk, rings=30, seg=36, shape=head_shape, **N),
                          kind='skin', color=pal['skin']))
    hair = ellipsoid(HR[0] * 1.07, HR[1] * 0.78, HR[2] * 1.05, center=(0, HC[1] + 0.035, HC[2] - 0.012), rings=20, seg=32,
                     noise=0.12, seed=seed + 3)
    parts.append(PartSpec('hair', 'head', (0, 0, 0), mesh=hair, kind='cloth', color=pal['hair']))
    fz = HC[2] + HR[2]
    # лицо: глаза, брови, нос, губы, уши
    for sx in (1, -1):
        parts.append(PartSpec(f'eye_white_{sx}', 'head', (sx * 0.029, HC[1] + 0.012, fz - 0.016),
                              mesh=ellipsoid(0.012, 0.0075, 0.008, rings=10, seg=14), kind='skin', color=(0.92, 0.9, 0.87)))
        parts.append(PartSpec(f'iris_{sx}', 'head', (sx * 0.029, HC[1] + 0.012, fz - 0.0085),
                              mesh=ellipsoid(0.0055, 0.0055, 0.0015, rings=8, seg=12), kind='eye', color=pal['eyes']))
        parts.append(PartSpec(f'brow_{sx}', 'head', (sx * 0.03, HC[1] + 0.029, fz - 0.011),
                              rot=(0, 0, sx * -6), mesh=ellipsoid(0.017, 0.0035, 0.004, rings=8, seg=12), kind='cloth',
                              color=pal['hair']))
        parts.append(PartSpec(f'ear_{sx}', 'head', (sx * (HR[0] - 0.004), HC[1] + 0.0, HC[2] - 0.004),
                              mesh=ellipsoid(0.008, 0.022, 0.014, rings=10, seg=14), kind='skin', color=pal['skin']))
    parts.append(PartSpec('nose', 'head', (0, HC[1] - 0.008, fz - 0.004), rot=(-14, 0, 0),
                          mesh=ellipsoid(0.010, 0.022, 0.012, rings=10, seg=14), kind='skin', color=pal['skin']))
    parts.append(PartSpec('mouth_dark', 'head', (0, HC[1] - 0.046, fz - 0.017),
                          mesh=ellipsoid(0.016, 0.008, 0.004, rings=8, seg=14), kind='eye', color=(0.08, 0.02, 0.02)))
    parts.append(PartSpec('lip_upper', 'head', (0, HC[1] - 0.041, fz - 0.014),
                          mesh=ellipsoid(0.018, 0.0045, 0.0065, rings=8, seg=16), kind='skin', color=pal['lips']))
    parts.append(PartSpec('jaw', 'head', (0, HC[1] - 0.03, HC[2] - 0.01), kind='none'))
    parts.append(PartSpec('lip_lower', 'jaw', (0, -0.020, fz - HC[2] + 0.006),
                          mesh=ellipsoid(0.017, 0.005, 0.0065, rings=8, seg=16), kind='skin', color=pal['lips']))

    for side, sx in (('R', 1), ('L', -1)):
        parts.append(PartSpec(f'shoulder_{side}', 'pelvis', (sx * 0.19, 1.41 - 0.93, -0.01), rot=(0, 0, sx * -5), kind='none'))
        parts.append(PartSpec(f'upperarm_{side}', f'shoulder_{side}', (0, 0, 0), kind='cloth', color=pal['coat'],
                              mesh=loft([(0.04, .05, .05, 0, 0), (0, .058, .058, 0, 0), (-0.28, .048, .05, 0, 0), (-0.31, .045, .045, 0, 0)],
                                        rings=20, seg=20, round_start=0.04, round_end=0.02, **N)))
        parts.append(PartSpec(f'elbow_{side}', f'shoulder_{side}', (0, -0.29, 0), rot=(-8, 0, 0), kind='none'))
        parts.append(PartSpec(f'forearm_{side}', f'elbow_{side}', (0, 0, 0), kind='cloth', color=pal['coat'],
                              mesh=loft([(0.03, .046, .046, 0, 0), (0, .048, .048, 0, 0), (-0.22, .044, .044, 0, 0), (-0.25, .047, .047, 0, 0)],
                                        rings=18, seg=20, round_start=0.03, **N)))
        parts.append(PartSpec(f'wrist_{side}', f'elbow_{side}', (0, -0.25, 0), kind='none'))
        parts.append(PartSpec(f'hand_{side}', f'wrist_{side}', (0, 0, 0), kind='skin', color=pal['skin'],
                              mesh=loft([(0.02, .02, .022, 0, 0), (0, .02, .03, 0, 0), (-0.08, .017, .036, 0, 0.004),
                                         (-0.15, .012, .03, -sx * 0.01, 0.01), (-0.17, .008, .018, -sx * 0.015, 0.012)],
                                        rings=18, seg=20, round_start=0.02, round_end=0.02, **N)))
        parts.append(PartSpec(f'hip_{side}', 'pelvis', (sx * 0.095, 0, 0), kind='none'))
        parts.append(PartSpec(f'thigh_{side}', f'hip_{side}', (0, 0, 0), kind='cloth', color=pal['pants'],
                              mesh=loft([(0.04, .06, .06, 0, 0), (0, .075, .078, 0, 0), (-0.40, .058, .06, 0, 0), (-0.44, .055, .055, 0, 0)],
                                        rings=20, seg=20, round_start=0.04, **N)))
        parts.append(PartSpec(f'knee_{side}', f'hip_{side}', (0, -0.43, 0), kind='none'))
        parts.append(PartSpec(f'shin_{side}', f'knee_{side}', (0, 0, 0), kind='cloth', color=pal['pants'],
                              mesh=loft([(0.03, .055, .055, 0, 0), (0, .056, .058, 0, 0), (-0.35, .05, .05, 0, 0), (-0.40, .05, .05, 0, 0)],
                                        rings=20, seg=20, round_start=0.03, **N)))
        parts.append(PartSpec(f'ankle_{side}', f'knee_{side}', (0, -0.40, 0), kind='none'))
        parts.append(PartSpec(f'foot_{side}', f'ankle_{side}', (0, 0, 0), kind='cloth', color=pal['boots'],
                              mesh=loft([(-0.06, .045, .05, 0, -0.04), (0.0, .05, .055, 0, -0.045), (0.10, .048, .038, 0, -0.065),
                                         (0.19, .040, .030, 0, -0.072), (0.22, .03, .025, 0, -0.075)],
                                        axis='z', rings=22, seg=20, round_start=0.03, round_end=0.025, power=2.8, **N)))
    return _finalize(parts)


def merged_rest_mesh(parts):
    """Склеивает все части в позе покоя (без поворотов) — для быстрого экспорта/проверки."""
    V, T, offset = [], [], 0
    for p in parts:
        if p.mesh is None:
            continue
        V.append(p.mesh.vertices + np.array(p.body_pos))
        T.append(p.mesh.triangles + offset)
        offset += len(p.mesh.vertices)
    return np.vstack(V), np.vstack(T)
