"""
Экспорт текущей модели Бабки в один файл GLB (glTF) с материалами — для Blender, Unity, Unreal, просмотрщиков.

    xvfb-run -a python tools/export_babka_pose.py stand --detail 2.6
    python tools/export_babka_glb.py                 # -> docs/babka/babka.glb
"""
import sys
from pathlib import Path

import bpy
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'docs' / 'babka'
pose = sys.argv[1] if len(sys.argv) > 1 else 'stand'

# цвета нового (страшного) облика
COLORS = dict(
    face=((0.36, 0.38, 0.46), 0.55), skin=((0.36, 0.38, 0.46), 0.55), wool=((0.20, 0.018, 0.028), 0.95),
    linen=((0.035, 0.04, 0.065), 0.85), felt=((0.30, 0.29, 0.28), 1.0), rubber=((0.02, 0.02, 0.025), 0.2),
    sash=((0.55, 0.05, 0.07), 0.8), mitten=((0.6, 0.2, 0.2), 0.95), snowpack=((0.92, 0.95, 1.0), 0.75),
    ice=((0.80, 0.92, 1.0), 0.05), hair=((0.85, 0.86, 0.90), 0.45), nail=((0.12, 0.11, 0.12), 0.35),
    cavity=((0.02, 0.01, 0.01), 0.9), eye=((0.86, 0.90, 0.96), 0.15), leather=((0.12, 0.09, 0.07), 0.5),
)


def material(kind):
    name = 'babka_' + kind
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    col, rough = COLORS.get(kind, ((0.5, 0.5, 0.5), 0.6))
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*col, 1)
    b.inputs['Roughness'].default_value = rough
    if kind == 'ice':
        b.inputs['Transmission Weight'].default_value = 1.0
    if kind == 'eye':
        b.inputs['Emission Color'].default_value = (0.7, 0.85, 1.0, 1)
        b.inputs['Emission Strength'].default_value = 0.6
    if kind in ('wool', 'mitten', 'felt'):
        b.inputs['Sheen Weight'].default_value = 1.0
    return m


bpy.ops.wm.read_factory_settings(use_empty=True)
d = np.load(OUT / f'pose_{pose}.npz')
root = bpy.data.objects.new('Babka', None)
bpy.context.scene.collection.objects.link(root)
tris = 0
for name in d['names']:
    name = str(name)
    V = d[f'{name}__v']
    T = d[f'{name}__t']
    kind = str(d[f'{name}__k'])
    Vb = np.c_[V[:, 0], V[:, 2], V[:, 1]]           # Ursina (y вверх) -> Blender (z вверх)
    me = bpy.data.meshes.new(name)
    me.from_pydata(Vb.tolist(), [], T.tolist())
    me.validate()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    ob.parent = root
    bpy.context.scene.collection.objects.link(ob)
    me.materials.append(material(kind))
    tris += len(T)

path = OUT / 'babka.glb'
bpy.ops.export_scene.gltf(filepath=str(path), export_format='GLB')
print('saved', path, tris, 'треугольников')
