"""
Демо: у избы на ступеньке сидит Бабка. Вид от первого лица.

Запуск:  python babka_demo.py          (--selftest — автопрогон)

  W A S D — ходить, мышь — смотреть, Shift — бежать
  F       — фонарь (посвети ей в лицо — ослепнет на пару секунд)
  Tab     — свободная камера / от первого лица
  P       — кино / старая фотография
  C       — кинокамера: медленный наезд на неё (ещё раз — выход)
  Esc     — отпустить мышь
"""
import math
import random
import sys

from ursina import (EditorCamera, Entity, Text, Ursina, Vec3, camera, color, held_keys, mouse, time, window)

from monsters.babka import Babka
from monsters.cinema import Atmosphere, FilmLook, KeroseneLamp
from monsters.porch import build_porch
from monsters.frost_mimic import set_environment
from panda3d.core import NodePath, Point3
from ursina import scene
from taiga_demo import build_taiga

NIGHT_FOG = (0.06, 0.07, 0.10)

app = Ursina(title='Бабка', development_mode=False)
build_taiga(clear=9.0)
build_porch(position=(0, 0, 9), rotation_y=180)
set_environment(light_dir=(0.5, 0.55, -0.55), light_color=(0.48, 0.54, 0.68), fog_color=NIGHT_FOG, fog_density=0.07)
NodePath.set_shader_input(scene, 'rim_dir', Vec3(-0.5, 0.6, 0.7))
NodePath.set_shader_input(scene, 'rim_color', Vec3(0.30, 0.36, 0.52))
lamp = KeroseneLamp(position=(-0.62, 0.0, 8.58), power=5.0)
Atmosphere(center=(0, 0, 8.2), radius=6)
window.color = color.rgb(*NIGHT_FOG)

player = Entity(position=(0, 0, -4))
head = Entity(parent=player, y=1.65)
babka = Babka(position=(0, 0, 9), rotation_y=180, target=head, sitting=True,
              waypoints=[(0, 0, 6), (6, 0, 3), (2, 0, -3), (-5, 0, 2)])
film = FilmLook(grade='cinema', letterbox=False, aperture=0.9)
film.focus_on(babka.p['head'])

subtitle = Text('', origin=(0, 0), y=-0.4, scale=1.3, color=color.rgb(0.95, 0.9, 0.8))
status = Text('', origin=(0, 0), y=0.1, scale=2.2, color=color.rgb(0.9, 0.2, 0.15))
Text('WASD — ходить, Shift — бежать, F — фонарь, Tab — свободная камера, P — кино/фото, C — кинокамера, Esc — мышь',
     position=window.top_left + Vec3(0.02, -0.02, 0), scale=0.8, color=color.rgb(0.6, 0.6, 0.65))
flash_overlay = Entity(parent=camera.ui, model='circle', scale=0.9, color=color.rgba(1, 1, 0.9, 0), z=1)
state = dict(sub_t=0, fp=True, flash_cd=0, caught_t=-1, cine=False, cine_t=0.0)


def say(text):
    subtitle.text = f'«{text}»'
    state['sub_t'] = 3.0


def caught():
    status.text = 'ПОЙМАЛА'
    state['caught_t'] = 3.0


babka.on_say = say
babka.on_catch = caught

ec = EditorCamera(enabled=False)
camera.parent = head
camera.position = Vec3(0, 0, 0)
camera.rotation = Vec3(0, 0, 0)
mouse.locked = True


def input(key):
    if key == 'tab':
        state['fp'] = not state['fp']
        if state['fp']:
            ec.enabled = False
            camera.parent = head
            camera.position = Vec3(0, 0, 0)
            camera.rotation = Vec3(0, 0, 0)
            mouse.locked = True
        else:
            camera.parent = None
            ec.enabled = True
            ec.position = babka.world_position + Vec3(0, 1.5, 0)
            mouse.locked = False
    elif key == 'p':
        film.toggle_grade()
    elif key == 'c':
        state['cine'] = not state['cine']
        state['cine_t'] = 0.0
        film.letterbox = 1.0 if state['cine'] else 0.0
        if state['cine']:
            ec.enabled = False
            camera.parent = None
            mouse.locked = False
        else:
            camera.parent = head
            camera.position = Vec3(0, 0, 0)
            camera.rotation = Vec3(0, 0, 0)
            state['fp'] = True
    elif key == 'escape':
        mouse.locked = False
    elif key == 'f' and state['flash_cd'] <= 0:
        state['flash_cd'] = 4.0
        flash_overlay.color = color.rgba(1, 1, 0.9, 0.25)
        to = babka.p['head'].world_position - head.world_position
        if to.length() < 12 and to.normalized().dot(camera.forward) > 0.93:
            babka.flash()


def update():
    dt = time.dt
    if state['cine']:
        # медленный наезд с лёгким «ручным» покачиванием
        state['cine_t'] += dt
        k = min(state['cine_t'] / 14.0, 1.0)
        t = state['cine_t']
        hp = babka.p['head'].world_position
        a = math.radians(-20 + 25 * k)
        dist = 6.5 - 5.3 * (k * k * (3 - 2 * k))
        shake = Vec3(math.sin(t * 1.7) * 0.012 + math.sin(t * 3.1) * 0.006, math.sin(t * 2.3) * 0.01, 0)
        camera.position = Vec3(hp.x + math.sin(a) * dist, hp.y - 0.1 + 0.4 * (1 - k), hp.z - math.cos(a) * dist) + shake
        NodePath.lookAt(camera, Point3(*hp), Vec3(0, 1, 0))
    elif state['fp']:
        if mouse.locked:
            player.rotation_y += mouse.velocity[0] * 120
            head.rotation_x = max(-80, min(80, head.rotation_x - mouse.velocity[1] * 120))
        move = player.forward * (held_keys['w'] - held_keys['s']) + player.right * (held_keys['d'] - held_keys['a'])
        if move.length() > 0:
            player.position += move.normalized() * (4.5 if held_keys['shift'] else 2.2) * dt
    state['flash_cd'] -= dt
    c = flash_overlay.color
    flash_overlay.color = color.rgba(c[0], c[1], c[2], max(0, c[3] - dt * 0.6))
    state['sub_t'] -= dt
    if state['sub_t'] <= 0:
        subtitle.text = ''
    if state['caught_t'] > 0:
        state['caught_t'] -= dt
        if state['caught_t'] <= 0:
            status.text = ''
            player.position = Vec3(random.uniform(-4, 4), 0, -8)


if '--selftest' in sys.argv:
    mouse.locked = False
    for i in range(260):
        if 40 < i < 120:
            player.position += (babka.world_position - player.world_position).normalized() * 0.05
        if i == 130:
            input('f')
        if i == 200:
            input('tab')
        if i == 220:
            input('c')
        if i == 240:
            input('p')
        app.step()
    print('SELFTEST OK state =', babka.state, 'caught =', bool(status.text))
else:
    app.run()
