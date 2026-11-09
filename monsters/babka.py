"""
«Бабка» — враг. Жуткая советская бабушка.

Ходит сгорбившись, шаркает валенками, бормочет. Лицо в тени платка, светятся только
толстые круглые очки, на лице застывшая улыбка с золотым зубом. Заметив игрока, медленно
распрямляется, шея в шарфе вытягивается из платка, голова склоняется набок — и она
быстро шаркает следом, протянув длинные руки. Свет фонаря её слепит: закрывает очки руками.

    from monsters.babka import Babka
    b = Babka(position=(0, 0, 10), target=player, waypoints=[(0,0,10), (6,0,4), (-4,0,0)])
    b.on_say = lambda text: subtitle.set(text)
    b.on_catch = lambda: game_over()
    b.flash()          # игрок посветил фонарём
"""
import math
import random

from panda3d.core import NodePath
from ursina import Entity, Mesh, Vec3, Vec4, camera, scene, time as utime
from ursina.shaders import unlit_shader
from panda3d.core import TransparencyAttrib

from .babka_mesh import NECK_MAX, build_babka
from .babka_shaders import MATERIALS, cloth_shader, lens_shader
from .frost_mimic import init_scene_uniforms

LINES_NOTICE = ['Внучек?..', 'Это кто там у меня?', 'А я тебя вижу.']
LINES_CHASE = ['Куда без шапки?!', 'Иди покушай, остынет!', 'Стой, кому говорю!', 'Бабушку не слушаешь?']
LINES_LOST = ['Ну ничего... придёшь ещё.', 'Всё равно найду.']
LINES_PATROL = ['…огурчики закрыла…', '…пенсия в четверг…', '…ходят тут…']


def _approach(cur, target, rate, dt):
    return cur + (target - cur) * (1 - math.exp(-rate * dt))


def _angle_diff(a, b):
    return (b - a + 180) % 360 - 180


class Babka(Entity):
    fixed_dt = None
    detect_range = 13.0
    lose_range = 24.0
    fov = 75                 # половина угла обзора

    def __init__(self, target=None, waypoints=None, **kwargs):
        super().__init__(**kwargs)
        init_scene_uniforms()
        self.target = target
        self.waypoints = [Vec3(*w) for w in (waypoints or [])]
        self._wp = 0
        self.on_say = None
        self.on_catch = None
        self.state = 'patrol'
        self._st = 0.0
        self._t = 0.0
        self._speed = 0.0
        self._phase = 0.0
        self.unfold = 0.0        # 0 сгорблена, 1 распрямилась и вытянула шею
        self.reach = 0.0         # руки вперёд
        self.cover = 0.0         # закрывает очки
        self.glow = 0.15
        self.blind = 0.0
        self._tilt = 0.0
        self._yaw_head = 0.0
        self._lunge = 0.0
        self._mutter = random.uniform(4, 8)

        specs = build_babka()
        self.p = {}
        for s in specs:
            parent = self.p.get(s.parent, self)
            if s.mesh is None:
                e = Entity(parent=parent, position=s.pos, rotation=s.rot)
            else:
                m = Mesh(**s.mesh.to_ursina_args())
                if s.kind == 'lens':
                    e = Entity(parent=parent, position=s.pos, rotation=s.rot, model=m, shader=lens_shader)
                else:
                    mat, col, gl = MATERIALS[s.kind]
                    e = Entity(parent=parent, position=s.pos, rotation=s.rot, model=m, shader=cloth_shader,
                               double_sided=s.kind in ('platok', 'net', 'dress'))
                    e.set_shader_input('material', mat)
                    e.set_shader_input('base_color', Vec3(*col))
                    e.set_shader_input('gloss', float(gl))
                    if s.kind == 'jar':
                        e.setTransparency(TransparencyAttrib.M_alpha)
                e.set_shader_input('part_offset', Vec3(*s.body_pos))
                e.set_shader_input('sway', 0.0)
                e.set_shader_input('face_shadow', 1.0 if s.parent == 'head' and s.kind == 'skin' else 0.0)
            e.name = s.name
            parts = self.p
            parts[s.name] = e

        self.shadow = Entity(parent=self, model='quad', texture='radial_gradient', rotation_x=90, y=0.01,
                             scale=1.4, color=Vec4(0, 0, 0, 0.55), shader=unlit_shader)
        self.shadow.set_depth_write(False)
        self._pose(0)

    # ------------------------------------------------------------ API
    def flash(self):
        """Игрок посветил фонарём ей в лицо."""
        if self.state in ('notice', 'chase', 'grab', 'search', 'patrol'):
            self._set('stunned')
            self._say(random.choice(['Ой! Глаза-то!', 'Убери, ирод!']))

    def alert(self):
        if self.state in ('patrol', 'search'):
            self._set('notice')
            self._say(random.choice(LINES_NOTICE))

    # ------------------------------------------------------------ внутреннее
    def _say(self, text):
        if self.on_say:
            self.on_say(text)

    def _set(self, st):
        self.state = st
        self._st = 0.0

    def _target_pos(self):
        if self.target is None:
            return None
        t = self.target
        return Vec3(*(t.world_position if hasattr(t, 'world_position') else t))

    def _move_toward(self, goal, speed, dt, turn_rate=120):
        to = goal - self.world_position
        to.y = 0
        dist = to.length()
        if dist > 0.01:
            want = math.degrees(math.atan2(to.x, to.z))
            turn = _angle_diff(self.rotation_y, want)
            self.rotation_y += max(-turn_rate * dt, min(turn_rate * dt, turn))
            facing = max(0.2, 1 - abs(turn) / 90)
            self._speed = _approach(self._speed, speed * facing, 3, dt)
        return dist

    def _brain(self, dt):
        tp = self._target_pos()
        dist, seen = 1e9, False
        if tp is not None:
            d = tp - self.world_position
            d.y = 0
            dist = d.length()
            ang = abs(_angle_diff(self.rotation_y, math.degrees(math.atan2(d.x, d.z))))
            seen = dist < self.detect_range and (ang < self.fov or dist < 3.0)

        st = self.state
        self._st += dt
        if st == 'patrol':
            if self.waypoints:
                if self._move_toward(self.waypoints[self._wp], 0.55, dt, 60) < 0.4:
                    self._wp = (self._wp + 1) % len(self.waypoints)
            else:
                self._speed = _approach(self._speed, 0, 3, dt)
            self._mutter -= dt
            if self._mutter <= 0:
                self._say(random.choice(LINES_PATROL))
                self._mutter = random.uniform(6, 12)
            if seen:
                self.alert()
        elif st == 'notice':
            self._speed = _approach(self._speed, 0, 6, dt)
            if tp is not None:
                self._move_toward(tp, 0.0, dt, 90)
            if self._st > 1.9:
                self._set('chase')
                self._say(random.choice(LINES_CHASE))
        elif st == 'chase':
            self._move_toward(tp, 3.1, dt, 160)
            if dist < 1.5:
                self._set('grab')
            elif dist > self.lose_range:
                self._set('search')
                self._say(random.choice(LINES_LOST))
            elif random.random() < dt * 0.12:
                self._say(random.choice(LINES_CHASE))
        elif st == 'grab':
            self._speed = _approach(self._speed, 1.0, 8, dt)
            if tp is not None:
                self._move_toward(tp, 1.0, dt, 200)
            if self._st > 0.45:
                if dist < 1.6:
                    self._set('caught')
                    self._say('Попался, внучек.')
                    if self.on_catch:
                        self.on_catch()
                else:
                    self._set('chase')
        elif st == 'caught':
            self._speed = _approach(self._speed, 0, 8, dt)
            if self._st > 3.0:
                self._set('search')
        elif st == 'stunned':
            self._speed = _approach(self._speed, 0, 8, dt)
            if self._st > 2.6:
                self._set('chase' if seen or dist < self.lose_range else 'search')
        elif st == 'search':
            self._speed = _approach(self._speed, 0.4, 2, dt)
            self.rotation_y += math.sin(self._t * 0.8) * 40 * dt
            if seen and self._st > 1.0:
                self._set('notice')
                self._say(random.choice(LINES_NOTICE))
            elif self._st > 5:
                self._set('patrol')
        self.position += self.forward * self._speed * dt

        # целевые значения позы
        targets = dict(
            patrol=(0.0, 0.0, 0.0, 0.15), notice=(1.0, 0.0, 0.0, 1.0), chase=(0.85, 0.65, 0.0, 1.0),
            grab=(1.0, 1.0, 0.0, 1.3), caught=(1.0, 1.0, 0.0, 1.0), stunned=(0.25, 0.0, 1.0, 0.0),
            search=(0.4, 0.0, 0.0, 0.6),
        )[self.state]
        rate = 1.6 if self.state == 'notice' else 4
        self.unfold = _approach(self.unfold, targets[0], rate, dt)
        self.reach = _approach(self.reach, targets[1], 6, dt)
        self.cover = _approach(self.cover, targets[2], 8, dt)
        self.glow = _approach(self.glow, targets[3], 3, dt)
        self.blind = _approach(self.blind, 1.0 if self.state == 'stunned' and self._st < 0.6 else 0.0, 6, dt)
        self._lunge = _approach(self._lunge, 1.0 if self.state in ('grab', 'caught') else 0.0, 10, dt)

        # голова: следит за целью, когда заметила; склоняется набок
        want_yaw = 0.0
        if tp is not None and self.state in ('notice', 'chase', 'grab', 'caught', 'search'):
            d = tp - self.world_position
            want_yaw = max(-80, min(80, _angle_diff(self.world_rotation_y, math.degrees(math.atan2(d.x, d.z)))))
        else:
            want_yaw = math.sin(self._t * 0.4) * 30
        self._yaw_head = _approach(self._yaw_head, want_yaw, 3, dt)
        tilt = {'notice': 28, 'chase': 12, 'grab': 20, 'caught': 32, 'search': 18}.get(self.state, 4)
        self._tilt = _approach(self._tilt, tilt, 2.5, dt)

    def _pose(self, dt):
        u, rch, cov = self.unfold, self.reach, self.cover
        sp = min(self._speed / 3.0, 1.0)
        self._phase += dt * (2.2 + 4.5 * sp) * (0.2 + sp) * 2
        s = math.sin(self._phase)
        p = self.p

        bend1 = 24 * (1 - u) + 10 * sp + 8 * self._lunge + 12 * cov
        bend2 = 30 * (1 - u) + 6 * sp + 6 * self._lunge + 10 * cov
        p['spine1'].rotation_x = bend1
        p['spine1'].rotation_z = s * 3 * (0.3 + sp)                 # покачивается при шарканье
        p['spine2'].rotation_x = bend2
        tilt_total = bend1 + bend2
        p['neck'].rotation_x = -8 * (1 - u) + 20 * self._lunge          # шея идёт вдоль сгорбленной спины
        p['neck_slide'].y = NECK_MAX * max(0.0, (u - 0.3) / 0.7) + 0.12 * self._lunge
        head_pitch = -(tilt_total + p['neck'].rotation_x) + 6
        p['head'].rotation_x = head_pitch
        p['head'].rotation_y = self._yaw_head
        p['head'].rotation_z = self._tilt + math.sin(self._t * 0.9) * 2

        for side, sx in (('R', 1), ('L', -1)):
            swing = s * sx * (8 + 18 * sp) * (1 - rch)
            p[f'shoulder_{side}'].rotation_x = -tilt_total - swing - rch * 82 - cov * 75
            p[f'shoulder_{side}'].rotation_z = sx * (-6 + 4 * rch) + sx * cov * 28
            p[f'elbow_{side}'].rotation_x = -12 - 8 * sp + rch * 6 - cov * 105
            # шаркающие шаги: ступни почти не отрываются
            p[f'hip_{side}'].rotation_x = s * sx * (6 + 26 * sp)
            p[f'knee_{side}'].rotation_x = (8 + 14 * sp) + max(0, -s * sx) * 18 * sp
        # авоська и вязание висят отвесно и раскачиваются
        for name in ('avoska', 'knitting'):
            p[name].world_rotation = Vec3(s * 8 * (0.3 + sp), self.world_rotation_y, math.cos(self._phase) * 5 * sp)

        for sx in (1, -1):
            p[f'lens_{sx}'].set_shader_input('glow', self.glow)
            p[f'lens_{sx}'].set_shader_input('blind', self.blind)

    def update(self):
        dt = self.fixed_dt or min(utime.dt, 1 / 20)
        self._t += dt
        NodePath.set_shader_input(scene, 'time', self._t)
        NodePath.set_shader_input(scene, 'cam_pos', Vec3(*camera.world_position))
        self._brain(dt)
        self._pose(dt)
