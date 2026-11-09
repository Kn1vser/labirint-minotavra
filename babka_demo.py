"""
Демо: Бабка патрулирует ночную тайгу. Вид от первого лица.

Запуск:  python babka_demo.py          (--selftest — автопрогон)

  W A S D — ходить, мышь — смотреть, Shift — бежать
  F       — фонарь (посвети ей в лицо — ослепнет на пару секунд)
  Tab     — свободная камера / от первого лица
  Esc     — отпустить мышь
"""
import random
import sys

from ursina import (EditorCamera, Entity, Text, Ursina, Vec3, camera, color, held_keys, mouse, time, window)

from monsters.babka import Babka
from monsters.frost_mimic import set_environment
from taiga_demo import build_taiga

NIGHT_FOG = (0.06, 0.07, 0.10)

app = Ursina(title='Бабка', development_mode=False)
build_taiga(clear=9.0)
set_environment(light_dir=(0.3, 0.6, 0.5), light_color=(0.55, 0.60, 0.78), fog_color=NIGHT_FOG, fog_density=0.07)
window.color = color.rgb(*NIGHT_FOG)

player = Entity(position=(0, 0, -6))
head = Entity(parent=player, y=1.65)
babka = Babka(position=(0, 0, 9), target=head, waypoints=[(0, 0, 9), (6, 0, 3), (2, 0, -3), (-5, 0, 2)])

subtitle = Text('', origin=(0, 0), y=-0.4, scale=1.3, color=color.rgb(0.95, 0.9, 0.8))
status = Text('', origin=(0, 0), y=0.1, scale=2.2, color=color.rgb(0.9, 0.2, 0.15))
Text('WASD — ходить, Shift — бежать, F — фонарь, Tab — свободная камера, Esc — мышь',
     position=window.top_left + Vec3(0.02, -0.02, 0), scale=0.8, color=color.rgb(0.6, 0.6, 0.65))
flash_overlay = Entity(parent=camera.ui, model='circle', scale=0.9, color=color.rgba(1, 1, 0.9, 0), z=1)
state = dict(sub_t=0, fp=True, flash_cd=0, caught_t=-1)


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
    if state['fp']:
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
        app.step()
    print('SELFTEST OK state =', babka.state, 'caught =', bool(status.text))
else:
    app.run()
