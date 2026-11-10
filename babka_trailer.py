"""
Трейлер Бабки вживую, в окне (≈20 секунд, затем повторяется).

    pip install ursina
    python babka_trailer.py              # окно
    python babka_trailer.py --fullscreen # на весь экран

Esc — выход, Пробел — начать заново, P — кино / старая фотография.
"""
import math
import sys

from panda3d.core import NodePath, Point3
from ursina import Entity, Text, Ursina, Vec3, application, camera, color, scene, window

from monsters.babka import Babka
from monsters.cinema import Atmosphere, FilmLook, KeroseneLamp
from monsters.frost_mimic import set_environment
from monsters.porch import build_porch
from taiga_demo import build_taiga

app = Ursina(title='Бабка — трейлер', fullscreen='--fullscreen' in sys.argv, development_mode=False)
FOG = (0.06, 0.07, 0.095)
build_taiga(clear=10.0, winter=True)
build_porch(position=(0, 0, 0), icicles=True)
set_environment(light_dir=(0.5, 0.55, 0.55), light_color=(0.52, 0.60, 0.80), fog_color=FOG, fog_density=0.055)
NodePath.set_shader_input(scene, 'rim_dir', Vec3(-0.5, 0.6, -0.7))
NodePath.set_shader_input(scene, 'rim_color', Vec3(0.30, 0.36, 0.52))
window.color = color.rgb(*FOG)
KeroseneLamp(position=(0.62, 0.0, 0.42), power=5.0)
Atmosphere(center=(0, 0, 0.8), radius=5, motes=30, snowfall=650)
film = FilmLook(grade='cinema', letterbox=True, aperture=1.2)
camera.fov = 32
title = Text('', origin=(0, 0), y=-0.3, scale=1.6, color=color.rgb(0.92, 0.88, 0.8))

S = dict(t=0.0, b=None, viewer=None, events=set())


def reset():
    if S['b']:
        from ursina import destroy
        destroy(S['b'])
        destroy(S['viewer'])
    S['viewer'] = Entity(position=(0.4, 1.6, 30))
    b = Babka(target=S['viewer'], sitting=True)
    b.detect_range = 0
    b.on_say = lambda text: setattr(title, 'text', f'«{text}»')
    S['b'] = b
    S['t'] = 0.0
    S['events'] = set()


def head():
    return Vec3(*S['b'].p['head'].world_position) + Vec3(0, 0.1, 0.05)


def hfwd():
    v = Vec3(*scene.getRelativeVector(S['b'].p['head'], Vec3(0, 0, 1)))
    v.y = 0
    return v.normalized()


def shot(pos, look, focus):
    t = S['t']
    shake = Vec3(math.sin(t * 1.7) * 0.6 + math.sin(t * 3.1) * 0.3, math.sin(t * 2.3) * 0.5, 0) * 0.02
    camera.position = Vec3(*pos) + shake
    NodePath.lookAt(camera, Point3(*look), Vec3(0, 1, 0))
    film.focus_on(focus)


def once(name):
    if name in S['events']:
        return False
    S['events'].add(name)
    return True


# (начало, конец, функция кадра k∈[0,1])
def shots():
    b = S['b']
    return [
        (0.0, 5.0, lambda k: shot(Vec3(2.6 - 1.6 * k, 2.0 - 0.5 * k, 10.0 - 4.0 * k), Vec3(0, 1.0, 0), b)),
        (5.0, 9.5, lambda k: shot(head() + Vec3(0.25 - 0.1 * k, 0.0, 1.05 - 0.3 * k), head() - Vec3(0, 0.03, 0), b.p['eye_1'])),
        (9.5, 12.0, lambda k: shot(head() + Vec3(-0.35 + 0.1 * k, -0.08, 0.5), head() - Vec3(0, 0.08, -0.06), b.p['hand_R'])),
        (12.0, 15.5, lambda k: shot(Vec3(1.1, 0.5, 3.6), head() - Vec3(0, 0.25, 0), b.p['head'])),
        (15.5, 18.0, lambda k: shot(head() + hfwd() * (1.25 - 0.3 * k) + Vec3(0.12, -0.42, 0), head() - Vec3(0, 0.02, 0), b.p['head'])),
        (18.0, 20.5, lambda k: shot(head() + hfwd() * 1.6 + Vec3(-0.3, -0.2, 0), head() - Vec3(0, 0.1, 0), b.p['head'])),
    ]


def update():
    from ursina import time
    S['t'] += time.dt
    t = S['t']
    b = S['b']
    if t < 0.1:
        S['viewer'].position = Vec3(0.4, 1.6, 4.5)
    if t > 12.0 and once('rise'):
        S['viewer'].position = Vec3(0.4, 1.6, 6.0)
        b.detect_range = 9
    if t > 15.5 and once('grab'):
        S['viewer'].position = Vec3(*b.world_position) + b.forward * 1.2 + Vec3(0, 1.6, 0)
        b._set('grab')
    if t > 18.0 and once('flash'):
        b.flash()
    for start, end, fn in shots():
        if start <= t < end:
            fn((t - start) / (end - start))
            break
    if t > 20.5:
        reset()


def input(key):
    if key == 'escape':
        application.quit()
    elif key == 'space':
        reset()
    elif key == 'p':
        film.toggle_grade()


reset()
if '--selftest' in sys.argv:
    from ursina import time as _t
    for i in range(260):
        _t.dt = 0.1
        update()
        app.step()
    print('SELFTEST OK t =', round(S['t'], 1), 'state =', S['b'].state)
else:
    app.run()
