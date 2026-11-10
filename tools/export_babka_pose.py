"""
Выгружает Бабку в нужной позе (сидит / стоит) из движка в .npz: вершины в мировых координатах + тип материала.
Дальше tools/blender_sculpt_babka.py делает из этого скульпт в Blender.

    xvfb-run -a python tools/export_babka_pose.py sit      # или stand
"""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ursina import Entity, Ursina, application, scene  # noqa: E402

app = Ursina(size=(64, 64), borderless=True, development_mode=False)
from monsters.babka import Babka  # noqa: E402
from monsters.babka_mesh import build_babka  # noqa: E402

pose = sys.argv[1] if len(sys.argv) > 1 else 'sit'
b = Babka(target=Entity(position=(0.2, 1.55, 3.5)), sitting=(pose == 'sit'))
b.detect_range = 0
b.fixed_dt = 1 / 30
b._shudder_next = 1e9
for _ in range(60):
    app.step()

kinds = {s.name: s.kind for s in build_babka()}
out = {}
names = []
for name, e in b.p.items():
    if not e.model or name not in kinds:
        continue
    m = e.model
    V = np.array(m.vertices, dtype=np.float64)
    T = np.array(m.triangles, dtype=np.int64).reshape(-1, 3)
    M = np.array(e.getMat(scene), dtype=np.float64)          # строки: p' = p · M
    Vw = np.c_[V, np.ones(len(V))] @ M
    out[f'{name}__v'] = Vw[:, :3]
    out[f'{name}__t'] = T
    out[f'{name}__k'] = np.array(kinds[name])
    names.append(name)
out['names'] = np.array(names)
path = ROOT / 'docs' / 'babka' / f'pose_{pose}.npz'
np.savez_compressed(path, **out)
print('saved', path, len(names), 'частей')
application.quit()
