"""
Скульпт-проход Бабки в Blender (через модуль bpy) и рендер в Cycles.

Что делает:
  * руки (ладонь + фаланги) и лицо (череп, нос, крылья носа, веки, шея) сплавляются voxel-remesh в цельные
    органические формы и сглаживаются — пропадают швы «трубок»;
  * на лицо и руки — мелкая скульптура дисплейсментом: поры, мелкие морщинки;
  * ткани получают толщину (Solidify) и складки (Displace); снег — мягкие сугробики;
  * материалы Cycles: кожа с подповерхностным рассеянием, шерсть с ворсом, лён, войлок, резина, снег, лёд, глаза;
  * сцена: снег, ступенька, тёплая лампа у ног, холодная луна сзади;
  * сохраняет babka_sculpt_lite.glb (прореженный), по --save — полный babka_sculpt.blend, и рендеры docs/babka/blender_*.png.

    pip install bpy                         # Blender как модуль Python (у нас 5.2)
    xvfb-run -a python tools/export_babka_pose.py sit
    xvfb-run -a python tools/export_babka_pose.py stand
    python tools/blender_sculpt_babka.py sit [--save]   # сидя: главный кадр, лицо, babka_sculpt_lite.glb (+ .blend)
    python tools/blender_sculpt_babka.py stand          # стоя: виды спереди / 3/4 / сбоку / сзади
    добавьте --fast для быстрого предпросмотра
"""
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'docs' / 'babka'
FAST = '--fast' in sys.argv
SAMPLES = 24 if FAST else 96

FACE_PARTS = ('skull', 'nose', 'ala_1', 'ala_-1', 'lid_1', 'lid_-1', 'uplid_1', 'uplid_-1', 'lolid_1', 'lolid_-1', 'neck_skin')


def group_of(name, kind):
    if name in FACE_PARTS:
        return 'face'
    for side in ('R', 'L'):
        if name.endswith('_' + side) and (name.startswith(('hand_', 'wristskin_')) or
                                          (name.startswith('f') and ('prox_' in name or 'dist_' in name))):
            return 'hand_' + side
    return name


# ------------------------------------------------------------------ загрузка позы
def load_pose(path):
    d = np.load(path, allow_pickle=False)
    groups = {}
    for name in d['names']:
        name = str(name)
        V = d[f'{name}__v']
        T = d[f'{name}__t']
        kind = str(d[f'{name}__k'])
        Vb = np.c_[V[:, 0], V[:, 2], V[:, 1]]               # Ursina (y вверх, левая) -> Blender (z вверх, правая)
        g = group_of(name, kind)
        groups.setdefault(g, dict(kind=kind if g not in ('face',) and not g.startswith('hand') else 'skin', parts=[]))
        groups[g]['parts'].append((Vb, T))
    return groups


def make_object(name, parts, collection):
    V = []
    F = []
    off = 0
    for Vb, T in parts:
        V.append(Vb)
        F.append(T + off)
        off += len(Vb)
    V = np.vstack(V)
    F = np.vstack(F)
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(V.tolist(), [], F.tolist())
    mesh.validate()
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    return obj


def select_only(obj):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def apply_mods(obj):
    select_only(obj)
    for m in list(obj.modifiers):
        bpy.ops.object.modifier_apply(modifier=m.name)


def recalc_normals(obj):
    select_only(obj)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')


def smooth_shading(obj):
    for p in obj.data.polygons:
        p.use_smooth = True


def tex(name, ttype, size, **kw):
    t = bpy.data.textures.new(name, ttype)
    if hasattr(t, 'noise_scale'):
        t.noise_scale = size
    for k, v in kw.items():
        setattr(t, k, v)
    return t


# ------------------------------------------------------------------ скульпт-проходы
def sculpt_organic(obj, voxel, detail):
    """Сплавить части в одну форму, сгладить и добавить мелкую скульптуру (поры, морщинки)."""
    r = obj.modifiers.new('remesh', 'REMESH')
    r.mode = 'VOXEL'
    r.voxel_size = voxel
    r.adaptivity = 0.0
    sm = obj.modifiers.new('smooth', 'CORRECTIVE_SMOOTH')
    sm.factor = 0.6
    sm.iterations = 6
    sm.smooth_type = 'LENGTH_WEIGHTED'
    sm.use_only_smooth = True
    apply_mods(obj)
    sub = obj.modifiers.new('sub', 'SUBSURF')
    sub.levels = sub.render_levels = 1
    d = obj.modifiers.new('pores', 'DISPLACE')
    d.texture = tex('pores_' + obj.name, 'VORONOI', 0.0016)
    d.strength = -detail
    d.mid_level = 0.5
    d2 = obj.modifiers.new('wrinkles', 'DISPLACE')
    d2.texture = tex('wr_' + obj.name, 'CLOUDS', 0.006, noise_depth=3)
    d2.strength = detail * 1.4
    apply_mods(obj)
    smooth_shading(obj)


def sculpt_cloth(obj, thick, folds):
    recalc_normals(obj)
    d = obj.modifiers.new('folds', 'DISPLACE')
    t = tex('folds_' + obj.name, 'CLOUDS', 0.05, noise_depth=2)
    d.texture = t
    d.strength = folds
    d2 = obj.modifiers.new('weave', 'DISPLACE')
    d2.texture = tex('weave_' + obj.name, 'CLOUDS', 0.004)
    d2.strength = folds * 0.18
    s = obj.modifiers.new('thick', 'SOLIDIFY')
    s.thickness = thick
    s.offset = 0.0
    apply_mods(obj)
    smooth_shading(obj)


def sculpt_snow(obj):
    r = obj.modifiers.new('remesh', 'REMESH')
    r.mode = 'VOXEL'
    r.voxel_size = 0.0035
    sm = obj.modifiers.new('smooth', 'SMOOTH')
    sm.factor = 0.8
    sm.iterations = 6
    d = obj.modifiers.new('lumps', 'DISPLACE')
    d.texture = tex('snowlumps_' + obj.name, 'CLOUDS', 0.02, noise_depth=2)
    d.strength = 0.004
    apply_mods(obj)
    smooth_shading(obj)


# ------------------------------------------------------------------ материалы
def principled(name, color, rough=0.6, **kw):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*color, 1)
    b.inputs['Roughness'].default_value = rough
    for k, v in kw.items():
        if k in b.inputs:
            b.inputs[k].default_value = v
    return m, b


def add_noise_color(m, b, color_a, color_b, scale, coords='Object'):
    nt = m.node_tree
    tc = nt.nodes.new('ShaderNodeTexCoord')
    n = nt.nodes.new('ShaderNodeTexNoise')
    n.inputs['Scale'].default_value = scale
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (*color_a, 1)
    ramp.color_ramp.elements[1].color = (*color_b, 1)
    nt.links.new(tc.outputs[coords], n.inputs['Vector'])
    nt.links.new(n.outputs['Fac'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], b.inputs['Base Color'])
    return n


def add_bump(m, b, scale, strength, kind='noise', distance=0.002):
    nt = m.node_tree
    tc = nt.nodes.new('ShaderNodeTexCoord')
    if kind == 'voronoi':
        t = nt.nodes.new('ShaderNodeTexVoronoi')
        t.feature = 'DISTANCE_TO_EDGE'
        out = t.outputs['Distance']
    elif kind == 'wave':
        t = nt.nodes.new('ShaderNodeTexWave')
        t.wave_type = 'BANDS'
        t.bands_direction = 'Z'
        out = t.outputs['Fac']
    else:
        t = nt.nodes.new('ShaderNodeTexNoise')
        t.inputs['Detail'].default_value = 8
        out = t.outputs['Fac']
    t.inputs['Scale'].default_value = scale
    nt.links.new(tc.outputs['Object'], t.inputs['Vector'])
    bump = nt.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = strength
    bump.inputs['Distance'].default_value = distance
    nt.links.new(out, bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], b.inputs['Normal'])


def build_materials():
    M = {}
    m, b = principled('skin', (0.52, 0.42, 0.40), 0.55, **{'Subsurface Weight': 0.35, 'Subsurface Scale': 0.004})
    b.inputs['Subsurface Radius'].default_value = (1.0, 0.35, 0.25)
    add_noise_color(m, b, (0.42, 0.40, 0.48), (0.58, 0.42, 0.40), 60)
    add_bump(m, b, 900, 0.25, 'voronoi', 0.0006)
    M['skin'] = m
    m, b = principled('wool', (0.40, 0.03, 0.05), 0.95, **{'Sheen Weight': 1.0, 'Sheen Roughness': 0.4})
    b.inputs['Sheen Tint'].default_value = (1.0, 0.85, 0.85, 1)
    add_noise_color(m, b, (0.30, 0.02, 0.04), (0.50, 0.05, 0.07), 25)
    add_bump(m, b, 260, 0.35, 'wave', 0.002)
    M['wool'] = m
    m, b = principled('linen', (0.07, 0.10, 0.24), 0.85)
    add_noise_color(m, b, (0.05, 0.07, 0.18), (0.11, 0.14, 0.30), 12)
    add_bump(m, b, 600, 0.2)
    M['linen'] = m
    m, b = principled('felt', (0.30, 0.29, 0.28), 1.0, **{'Sheen Weight': 0.8})
    add_bump(m, b, 400, 0.3)
    M['felt'] = m
    M['rubber'] = principled('rubber', (0.02, 0.02, 0.025), 0.2)[0]
    m, b = principled('sash', (0.55, 0.05, 0.07), 0.8)
    add_bump(m, b, 300, 0.3, 'wave')
    M['sash'] = m
    m, b = principled('mitten', (0.55, 0.06, 0.08), 0.95, **{'Sheen Weight': 1.0})
    add_bump(m, b, 300, 0.35, 'wave')
    M['mitten'] = m
    m, b = principled('snow', (0.92, 0.95, 1.0), 0.75, **{'Subsurface Weight': 1.0, 'Subsurface Scale': 0.02})
    b.inputs['Subsurface Radius'].default_value = (0.6, 0.8, 1.0)
    add_bump(m, b, 120, 0.4)
    M['snowpack'] = m
    M['ice'] = principled('ice', (0.80, 0.92, 1.0), 0.05, **{'Transmission Weight': 1.0, 'IOR': 1.31})[0]
    M['hair'] = principled('hair', (0.85, 0.86, 0.90), 0.45)[0]
    M['nail'] = principled('nail', (0.40, 0.34, 0.22), 0.35)[0]
    M['cavity'] = principled('cavity', (0.08, 0.03, 0.03), 0.8)[0]
    M['leather'] = principled('leather', (0.12, 0.09, 0.07), 0.5)[0]
    # глаза: желтоватый белок, ледяная радужка, зрачок; блик — от прозрачной роговицы (Coat)
    m, b = principled('eye', (0.75, 0.72, 0.66), 0.3, **{'Coat Weight': 1.0, 'Coat Roughness': 0.02})
    nt = m.node_tree
    geo = nt.nodes.new('ShaderNodeNewGeometry')
    dot = nt.nodes.new('ShaderNodeVectorMath')
    dot.operation = 'DOT_PRODUCT'
    dot.inputs[1].default_value = (0.0, 1.0, 0.1)
    nt.links.new(geo.outputs['Normal'], dot.inputs[0])
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    el = ramp.color_ramp.elements
    el[0].position, el[0].color = 0.80, (0.72, 0.68, 0.62, 1)
    el[1].position, el[1].color = 0.84, (0.40, 0.62, 0.82, 1)
    e3 = el.new(0.95)
    e3.color = (0.65, 0.85, 0.98, 1)
    e4 = el.new(0.965)
    e4.color = (0.01, 0.01, 0.01, 1)
    nt.links.new(dot.outputs['Value'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], b.inputs['Base Color'])
    M['eye'] = m
    return M


# ------------------------------------------------------------------ сцена
def build_scene(groups, M, with_step):
    col = bpy.context.scene.collection
    objs = []
    for gname, g in groups.items():
        kind = g['kind']
        obj = make_object(gname, g['parts'], col)
        if gname == 'face':
            sculpt_organic(obj, 0.0009, 0.00035)
        elif gname.startswith('hand_'):
            sculpt_organic(obj, 0.0008, 0.0003)
        elif kind in ('wool', 'linen'):
            sculpt_cloth(obj, 0.006 if kind == 'wool' else 0.003, 0.006 if kind == 'wool' else 0.004)
        elif kind == 'snowpack':
            sculpt_snow(obj)
        else:
            smooth_shading(obj)
        mat = M.get(kind if kind not in ('face',) else 'skin', M['skin'])
        obj.data.materials.append(mat)
        objs.append(obj)

    # земля в снегу
    bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0, 0))
    ground = bpy.context.active_object
    sub = ground.modifiers.new('sub', 'SUBSURF')
    sub.subdivision_type = 'SIMPLE'
    sub.levels = sub.render_levels = 6
    d = ground.modifiers.new('drifts', 'DISPLACE')
    d.texture = tex('drifts', 'CLOUDS', 1.2, noise_depth=2)
    d.strength = 0.08
    ground.data.materials.append(M['snowpack'])
    smooth_shading(ground)
    if with_step:
        wood, wb = principled('wood', (0.07, 0.045, 0.03), 0.75)
        add_bump(wood, wb, 40, 0.6)
        for (y, z, h) in ((-0.22, 0.43, 0.04), (-0.55, 0.58, 0.04)):
            bpy.ops.mesh.primitive_cube_add(size=1, location=(0, y, z))
            st = bpy.context.active_object
            st.scale = (2.2, 0.4, h * 2)
            st.data.materials.append(wood)
            bpy.ops.mesh.primitive_cube_add(size=1, location=(0, y - 0.05, z + h + 0.012))
            sn = bpy.context.active_object
            sn.scale = (2.0, 0.3, 0.024)
            bv = sn.modifiers.new('bevel', 'BEVEL')
            bv.width = 0.012
            bv.segments = 4
            sn.data.materials.append(M['snowpack'])
        for i in range(10):
            z = 0.15 + i * 0.27
            spans = ((-1.9, 2.6), (1.9, 2.6)) if z < 2.1 else ((0.0, 6.4),)
            for cx, ln in spans:
                bpy.ops.mesh.primitive_cylinder_add(radius=0.14, depth=ln, location=(cx, -0.85, z), rotation=(0, math.pi / 2, 0),
                                                    vertices=48)
                lg = bpy.context.active_object
                lg.data.materials.append(wood)
                smooth_shading(lg)
        bpy.ops.mesh.primitive_plane_add(size=1, location=(0, -0.9, 1.05), rotation=(math.pi / 2, 0, 0))
        door = bpy.context.active_object
        door.scale = (1.25, 2.1, 1)
        dm, db = principled('dark', (0.0, 0.0, 0.0), 1.0)
        door.data.materials.append(dm)

    # свет: холодная луна сзади-слева (контур), тёплая лампа у ног, слабая заливка неба
    bpy.ops.object.light_add(type='SUN', location=(0, 0, 5), rotation=(math.radians(68), 0, math.radians(200)))
    sun = bpy.context.active_object
    sun.data.energy = 2.2
    sun.data.color = (0.62, 0.72, 1.0)
    sun.data.angle = math.radians(2)
    bpy.ops.object.light_add(type='POINT', location=(0.6, 0.45, 0.22))
    lamp = bpy.context.active_object
    lamp.data.energy = 22
    lamp.data.color = (1.0, 0.55, 0.22)
    lamp.data.shadow_soft_size = 0.03
    bpy.ops.object.light_add(type='AREA', location=(-1.8, 3.0, 2.2))
    fill = bpy.context.active_object
    fill.data.energy = 35
    fill.data.size = 2.5
    fill.data.color = (0.55, 0.65, 0.95)
    fill.rotation_euler = (math.radians(60), 0, math.radians(-150))
    world = bpy.data.worlds.new('night')
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.012, 0.016, 0.03, 1)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value = 1.0
    bpy.context.scene.world = world
    return objs


def setup_render(w, h):
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = SAMPLES
    sc.cycles.use_denoising = True
    sc.render.resolution_x = w
    sc.render.resolution_y = h
    sc.render.film_transparent = False
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'AgX - High Contrast'
    sc.view_settings.exposure = -0.7
    sc.cycles.max_bounces = 6


def camera(name, loc, target, lens=50, dof=None):
    cam_data = bpy.data.cameras.new(name)
    cam_data.lens = lens
    if dof:
        cam_data.dof.use_dof = True
        cam_data.dof.focus_distance = dof
        cam_data.dof.aperture_fstop = 2.8
    cam = bpy.data.objects.new(name, cam_data)
    bpy.context.scene.collection.objects.link(cam)
    cam.location = loc
    d = Vector(target) - Vector(loc)
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    return cam


def render(cam, path):
    bpy.context.scene.camera = cam
    bpy.context.scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    print('saved', path)


def head_center(groups):
    V = np.vstack([v for v, _ in groups['face']['parts']])
    return Vector(V.mean(0)) + Vector((0, 0, 0.06))


def lite_glb(path, ratio=0.12):
    """Облегчённая копия для игры/репозитория: прореживание сетки."""
    for o in bpy.context.scene.objects:
        if o.type == 'MESH' and len(o.data.polygons) > 4000:
            d = o.modifiers.new('decimate', 'DECIMATE')
            d.ratio = ratio
    bpy.ops.export_scene.gltf(filepath=str(path), export_format='GLB', export_apply=True)
    print('saved', path)


def main():
    pose = 'stand' if 'stand' in sys.argv else 'sit'
    bpy.ops.wm.read_factory_settings(use_empty=True)
    groups = load_pose(OUT / f'pose_{pose}.npz')
    M = build_materials()
    build_scene(groups, M, with_step=(pose == 'sit'))
    hc = head_center(groups)
    if pose == 'sit':
        setup_render(900, 1200)
        render(camera('hero', (0.9, 3.6, 1.25), (0.0, 0.2, 0.85), lens=45, dof=3.7), OUT / 'blender_hero.png')
        face_pt = hc + Vector((0, 0.085, -0.01))
        cam_pos = hc + Vector((0.16, 0.6, 0.03))
        render(camera('face', cam_pos, face_pt, lens=85, dof=(cam_pos - face_pt).length), OUT / 'blender_face.png')
        if '--save' in sys.argv:
            bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'babka_sculpt.blend'))
            print('saved', OUT / 'babka_sculpt.blend')
        lite_glb(OUT / 'babka_sculpt_lite.glb')
    else:
        setup_render(700, 1100)
        for yaw, lab in ((0, 'front'), (40, 'three_quarter'), (90, 'side'), (180, 'back')):
            a = math.radians(yaw)
            loc = (math.sin(a) * 5.2, math.cos(a) * 5.2, 1.2)
            render(camera('cam_' + lab, loc, (0, 0, 1.0), lens=50), OUT / f'blender_{lab}.png')


main()
