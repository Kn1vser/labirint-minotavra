"""
Экспорт базового меша «Ледяного двойника» в OBJ (для Blender / ZBrush / Substance).
Окно не нужно.

    python tools/export_frost_mimic_obj.py          # -> docs/frost_mimic/frost_mimic_true.obj и ..._mask.obj
"""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from monsters.frost_mesh import build_human, build_true_form  # noqa: E402


def write_obj(parts, path):
    lines = [f'# Frost Mimic — {path.stem}', '# y-up, метры']
    off = 1
    for p in parts:
        if p.mesh is None:
            continue
        v = p.mesh.vertices + np.array(p.body_pos)
        n = p.mesh.normals
        v = v * np.array([1, 1, -1])       # из левосторонних координат Ursina в правосторонние OBJ
        n = n * np.array([1, 1, -1])
        lines.append(f'o {p.name}')
        lines += [f'v {a:.5f} {b:.5f} {c:.5f}' for a, b, c in v]
        lines += [f'vt {a:.5f} {b:.5f}' for a, b in p.mesh.uvs]
        lines += [f'vn {a:.4f} {b:.4f} {c:.4f}' for a, b, c in n]
        for t in p.mesh.triangles[:, ::-1] + off:
            lines.append('f ' + ' '.join(f'{i}/{i}/{i}' for i in t))
        off += len(v)
    path.write_text('\n'.join(lines))
    print('saved', path, f'({off - 1} вершин)')


if __name__ == '__main__':
    out = ROOT / 'docs' / 'frost_mimic'
    out.mkdir(parents=True, exist_ok=True)
    write_obj(build_true_form(), out / 'frost_mimic_true.obj')
    write_obj(build_human(), out / 'frost_mimic_mask.obj')
