"""Крыльцо избы для сцены с Бабкой: бревенчатая стена, тёмный дверной проём, ступенька."""
import numpy as np
from ursina import Entity, Mesh, Vec3, color

from .babka_mesh import SEAT_H
from .frost_mesh import loft
from .kochkar_mesh import tube_path
from .kochkar_shaders import MATERIAL, nature_shader


def _wood(mesh, parent, **kw):
    e = Entity(parent=parent, model=Mesh(**mesh.to_ursina_args()), shader=nature_shader, **kw)
    e.set_shader_input('material', MATERIAL['wood'])
    e.set_shader_input('base_color', Vec3(0.3, 0.25, 0.2))
    e.set_shader_input('part_offset', Vec3(*e.position))
    e.set_shader_input('sway', 0.0)
    return e


def build_porch(position=(0, 0, 0), rotation_y=0):
    """Ступенька стоит перед стеной; бабка садится на её край (локально z≈0)."""
    root = Entity(position=position, rotation_y=rotation_y)
    rng = np.random.default_rng(2)
    # брёвна стены (по оси x), с проёмом двери шириной 1.2 м
    for i in range(10):
        y = 0.15 + i * 0.27
        for x0, x1 in ((-3.2, -0.6), (0.6, 3.2)) if y < 2.1 else ((-3.2, 3.2),):
            log = tube_path([(x0, 0, 0), ((x0 + x1) / 2, rng.uniform(-0.01, 0.01), 0), (x1, 0, 0)], [0.14, 0.15, 0.14], seg=12)
            _wood(log, root, position=(0, y, -0.75))
    # тьма в проёме
    Entity(parent=root, model='quad', color=color.rgb(0.004, 0.004, 0.004), position=(0, 1.05, -0.78), scale=(1.25, 2.1),
           double_sided=True)
    # косяки
    for x in (-0.62, 0.62):
        _wood(loft([(0, 0.07, 0.09, 0, 0), (2.15, 0.07, 0.09, 0, 0)], rings=4, seg=8, noise=0.1, seed=3), root,
              position=(x, 0, -0.68))
    # ступенька и порог: доски
    for k, (z, y) in enumerate(((-0.22, SEAT_H - 0.03), (-0.55, SEAT_H + 0.12))):
        board = loft([(-1.1, 0.2, 0.04, 0, 0), (1.1, 0.2, 0.04, 0, 0)], axis='z', rings=4, seg=6, power=6, noise=0.05,
                     seed=k)
        board.vertices = board.vertices[:, [2, 1, 0]]          # доска вдоль x
        board.normals = board.normals[:, [2, 1, 0]]
        board.triangles = board.triangles[:, ::-1].copy()
        _wood(board, root, position=(0, y, z))
        _wood(loft([(0, 0.08, 0.08, 0, 0), (y, 0.08, 0.08, 0, 0)], rings=3, seg=6), root, position=(-1.0, 0, z))
        _wood(loft([(0, 0.08, 0.08, 0, 0), (y, 0.08, 0.08, 0, 0)], rings=3, seg=6), root, position=(1.0, 0, z))
    return root
