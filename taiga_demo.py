"""
Демо: Кочкарь бродит по осенней тайге.

Запуск:  python taiga_demo.py        (python taiga_demo.py --selftest — прогон без окна-человека)

Управление:
  ПКМ + мышь — вращать камеру, колесо — зум
  G       — идти в случайную точку
  R       — лечь (стать кочкой) / встать
  Пробел  — гудеть (глаза разгораются, из мха летят споры)
  L       — смотреть на камеру / оглядываться самому
  1 2 3 4 — вид спереди / сбоку / 3/4 / сзади
"""
import math
import random
import sys

import numpy as np
from ursina import EditorCamera, Entity, Mesh, Text, Ursina, Vec3, camera, color, window

from monsters.kochkar_mesh import birch, ellipsoid, spruce
from monsters.kochkar_shaders import MATERIAL, ground_shader, nature_shader

SUN_DIR = (-0.55, 0.42, 0.62)
SUN_COLOR = (1.0, 0.80, 0.58)
FOG = (0.56, 0.62, 0.66)


def _nature(mesh, kind, parent, base=(0.5, 0.5, 0.5), sway=0.0, **kw):
    e = Entity(parent=parent, model=Mesh(**mesh.to_ursina_args()), shader=nature_shader,
               double_sided=kind in ('needles', 'plain'), **kw)
    e.set_shader_input('material', MATERIAL[kind])
    e.set_shader_input('base_color', Vec3(*base))
    e.set_shader_input('part_offset', Vec3(*e.position))
    e.set_shader_input('sway', sway)
    return e


def build_taiga(seed=5, radius=28, clear=6.0, trees=True, winter=False):
    """Земля, ели, берёзы и камни. Поляна радиусом clear в центре остаётся свободной.
    winter=True — снежная тайга: снег везде, берёзы голые."""
    from monsters.frost_mimic import set_environment
    set_environment(light_dir=SUN_DIR, light_color=SUN_COLOR, fog_color=FOG, fog_density=0.03, snow=1.0 if winter else 0.0)
    window.color = color.rgb(*FOG)
    root = Entity()
    g = Entity(parent=root, model='plane', scale=radius * 2.5, shader=ground_shader)
    g.set_shader_input('part_offset', Vec3(0, 0, 0))
    g.set_shader_input('sway', 0.0)
    if not trees:
        return root
    rng = np.random.default_rng(seed)
    spruce_models = [spruce(rng.uniform(7, 12), rng.uniform(2.0, 2.8), tiers=12, seed=i) for i in range(4)]
    birch_models = [birch(rng.uniform(7, 10), seed=i) for i in range(3)]
    rock = ellipsoid(0.8, 0.45, 0.65, rings=12, seg=18, noise=0.35, seed=3)
    placed = []
    for _ in range(70):
        a = rng.uniform(0, 2 * math.pi)
        r = rng.uniform(clear, radius)
        x, z = math.cos(a) * r, math.sin(a) * r
        if any((x - px) ** 2 + (z - pz) ** 2 < 4 for px, pz in placed):
            continue
        placed.append((x, z))
        kind = rng.random()
        if kind < 0.6:
            m = spruce_models[rng.integers(0, 4)]
            _nature(m, 'needles', root, position=(x, 0, z), rotation_y=rng.uniform(0, 360), sway=0.15)
        elif kind < 0.9:
            trunk, crown = birch_models[rng.integers(0, 3)]
            ry = rng.uniform(0, 360)
            _nature(trunk, 'birch', root, position=(x, 0, z), rotation_y=ry)
            gold = (0.86, 0.62 + rng.uniform(-0.08, 0.06), 0.12)
            if not winter:
                _nature(crown, 'plain', root, base=gold, position=(x, 0, z), rotation_y=ry, sway=0.12)
        else:
            _nature(rock, 'wood', root, position=(x, 0.1, z), rotation_y=rng.uniform(0, 360),
                    scale=rng.uniform(0.6, 1.4))
    return root


if __name__ == '__main__':
    from monsters.kochkar import Kochkar

    app = Ursina(title='Кочкарь — тайга', development_mode=False)
    build_taiga()
    k = Kochkar(position=(0, 0, 0))

    ec = EditorCamera(rotation=(10, 150, 0))
    ec.target_z = -11
    Text('G — идти   R — лечь/встать   Пробел — гудеть   L — смотреть на камеру   1-4 — виды\n'
         'ПКМ — вращать камеру, колесо — зум', position=window.top_left + Vec3(0.02, -0.02, 0), scale=0.8,
         color=color.rgb(0.1, 0.12, 0.1))

    def input(key):
        if key == 'g':
            k.walk_to((random.uniform(-5, 5), 0, random.uniform(-5, 5)))
        elif key == 'r':
            k.toggle_rest()
        elif key == 'space':
            k.hum()
        elif key == 'l':
            k.look_target = None if k.look_target else camera
        elif key in ('1', '2', '3', '4'):
            ec.rotation_y = {'1': 180, '2': 270, '3': 215, '4': 0}[key] + k.rotation_y
            ec.rotation_x = 8

    def update():
        ec.position = ec.position * 0.95 + (k.world_position + Vec3(0, 1.8, 0)) * 0.05

    if '--selftest' in sys.argv:
        script = {5: 'g', 60: 'space', 100: 'r', 160: 'r', 190: 'l', 200: '3'}
        for i in range(230):
            if i in script:
                input(script[i])
            app.step()
        print('SELFTEST OK pos =', k.position, 'rest =', round(k._rest, 2))
    else:
        app.run()
