"""
«Кочкарь» — ходячая таёжная кочка.

Пласт земли с мхом, брусникой и ёлочкой на четырёх длинных ногах-корнях.
Мирный: бродит по тайге, разносит семена. Когда ложится, поджимает ноги
и прячет голову — становится обычной кочкой с ёлкой. Если «гудит»,
янтарные глаза разгораются, а из мха поднимаются светящиеся споры.

    from monsters.kochkar import Kochkar
    k = Kochkar(position=(0, 0, 0))
    k.walk_to((5, 0, 8))
    k.rest()        # лечь и стать кочкой
    k.wake()        # встать
    k.hum()         # загудеть
    k.look_target = player
"""
import math
import random

from panda3d.core import NodePath, Point3
from ursina import Entity, Mesh, Vec3, Vec4, camera, destroy, scene, time as utime
from ursina.shaders import unlit_shader

from .frost_mimic import init_scene_uniforms, set_environment  # общие uniform-ы сцены
from .kochkar_mesh import HIPS, LEG_L1, LEG_L2, build_kochkar
from .kochkar_shaders import MATERIAL, SWAY, eye_shader, nature_shader

STAND_H = 2.30        # высота центра кочки стоя
REST_H = 0.40         # лёжа
FOOT_Y = 0.07         # высота «щиколотки» над землёй
SX = -1               # знак rotation_x для «вперёд» у свисающей кости (проверено тестом)
SZ = -1              # знак rotation_z для отведения ноги в сторону

NECK_STAND = (58, -8, -22)
NECK_REST = (88, 45, 25)
NECK_HUM = (22, -10, -14)


def _approach(cur, target, rate, dt):
    return cur + (target - cur) * (1 - math.exp(-rate * dt))


def _smooth(a, b, x):
    t = min(max((x - a) / (b - a), 0.0), 1.0)
    return t * t * (3 - 2 * t)


def _angle_diff(a, b):
    return (b - a + 180) % 360 - 180


def build_parts(specs, root):
    parts = {}
    for s in specs:
        parent = parts.get(s.parent, root)
        if s.mesh is None:
            e = Entity(parent=parent, position=s.pos, rotation=s.rot)
        else:
            m = Mesh(**s.mesh.to_ursina_args())
            if s.kind == 'eye':
                e = Entity(parent=parent, position=s.pos, rotation=s.rot, model=m, shader=eye_shader)
            else:
                e = Entity(parent=parent, position=s.pos, rotation=s.rot, model=m, shader=nature_shader,
                           double_sided=s.kind in ('needles', 'lichen', 'cap'))
                e.set_shader_input('material', MATERIAL.get(s.kind, 4))
                e.set_shader_input('base_color', Vec3(0.86, 0.82, 0.74) if s.kind == 'stem' else Vec3(0.5, 0.5, 0.5))
            e.set_shader_input('part_offset', Vec3(*s.body_pos))
            e.set_shader_input('sway', SWAY.get(s.kind, 0.0))
        e.name = s.name
        parts[s.name] = e
    return parts


class Kochkar(Entity):
    fixed_dt = None

    def __init__(self, resting=False, **kwargs):
        super().__init__(**kwargs)
        init_scene_uniforms()
        self.specs = build_kochkar()
        self.p = build_parts(self.specs, self)
        self.body = self.p['body']
        self.look_target = None
        self.max_speed = 0.9
        self._goal = None
        self._speed = 0.0
        self._t = 0.0
        self._rest = 1.0 if resting else 0.0       # 0 — стоит, 1 — лежит кочкой
        self._rest_target = self._rest
        self._hum = 0.0
        self._hum_t = -1.0
        self._blink_timer = random.uniform(2, 5)
        self._blink = 0.0
        self._head_yaw = 0.0
        self._look_pitch = 0.0
        self.spores = []
        self.glow = 0.35

        self.shadow = Entity(parent=self, model='quad', texture='radial_gradient', rotation_x=90, y=0.01,
                             scale=(2.8, 3.4), color=Vec4(0, 0, 0, 0.5), shader=unlit_shader)
        self.shadow.set_depth_write(False)

        # ноги: где стоит каждая ступня (в мире), идёт ли шаг
        self.feet = {}
        self._place_feet_home()
        self._pair_turn = 0
        self._apply_pose(0.0)

    # ------------------------------------------------------------ API
    def walk_to(self, target):
        if self._rest_target > 0.5:
            self.wake()
        self._goal = Vec3(target[0], 0, target[2])

    def stop(self):
        self._goal = None

    def rest(self):
        """Лечь: ноги разъезжаются и сгибаются, голова ложится на землю. Получается кочка."""
        self._goal = None
        self._rest_target = 1.0

    def wake(self):
        self._rest_target = 0.0

    def toggle_rest(self):
        self.wake() if self._rest_target > 0.5 else self.rest()

    def hum(self, seconds=3.0):
        """Гудит: поднимает голову, глаза разгораются, из мха летят светящиеся споры."""
        self._hum_t = 0.0
        self._hum_dur = seconds

    # ------------------------------------------------------------ ноги
    def _home(self, name, lead=Vec3(0, 0, 0)):
        hx, _, hz = HIPS[name]
        r = self._rest
        # стоя — ступни под бёдрами чуть шире; лёжа — ноги вытянуты вперёд/назад
        lx = hx * (1.25 + 0.35 * r)
        lz = hz * (1.0 - 0.1 * r) + (2.0 if hz > 0 else -1.9) * r * 0.85
        p = scene.getRelativePoint(self, Point3(lx, 0, lz))
        return Vec3(p[0], self.world_y + FOOT_Y, p[2]) + lead

    def _place_feet_home(self):
        for n in HIPS:
            self.feet[n] = dict(pos=self._home(n), step=None)

    def _solve_leg(self, name):
        """Две кости: бедро и голень. Передние колени вперёд, задние назад, как у лося."""
        foot = self.feet[name]['pos']
        hip = self.p[f'hip_{name}']
        d = hip.getRelativePoint(scene, Point3(*foot))
        dx, dy, dz = d[0], d[1], d[2]
        ab = math.atan2(dx, -dy)
        self.p[f'abduct_{name}'].rotation_z = SZ * math.degrees(ab)
        dyp = -math.sqrt(dx * dx + dy * dy)
        D = min(max(math.sqrt(dz * dz + dyp * dyp), 0.05), LEG_L1 + LEG_L2 - 1e-3)
        a = math.atan2(dz, -dyp)
        b = math.acos(min(1, max(-1, (LEG_L1 ** 2 + D ** 2 - LEG_L2 ** 2) / (2 * LEG_L1 * D))))
        c = math.acos(min(1, max(-1, (LEG_L1 ** 2 + LEG_L2 ** 2 - D ** 2) / (2 * LEG_L1 * LEG_L2))))
        front = HIPS[name][2] > 0
        thigh = a + b if front else a - b
        knee = -(math.pi - c) if front else (math.pi - c)
        self.p[f'thigh_{name}'].rotation_x = SX * math.degrees(thigh)
        self.p[f'knee_{name}'].rotation_x = SX * math.degrees(knee)
        # пальцы-корешки всегда лежат на земле
        self.p[f'toes_{name}'].world_rotation = Vec3(0, self.world_rotation_y, 0)

    def _update_feet(self, dt, vel):
        stepping = [n for n, f in self.feet.items() if f['step']]
        pairs = (('FR', 'HL'), ('FL', 'HR'))
        resting_move = abs(self._rest - self._rest_target) > 0.001 or self._rest > 0.02
        for n, f in self.feet.items():
            s = f['step']
            if s:
                s['t'] += dt / s['dur']
                k = min(s['t'], 1.0)
                e = k * k * (3 - 2 * k)
                pos = s['from'] * (1 - e) + s['to'] * e
                pos.y += math.sin(math.pi * k) * s['lift']
                f['pos'] = pos
                if s['t'] >= 1:
                    f['step'] = None
            elif resting_move:
                f['pos'] = _lerp_vec(f['pos'], self._home(n), 1 - math.exp(-3 * dt))
        if resting_move or stepping:
            return
        # кому шагать: самая «отставшая» пара
        lead = vel * 0.55
        best, err = None, 0.0
        for pair in pairs:
            e = max((self.feet[n]['pos'] - self._home(n, lead)).length() for n in pair)
            if e > err:
                best, err = pair, e
        if best and err > (0.35 if self._speed > 0.05 else 0.12):
            for n in best:
                f = self.feet[n]
                to = self._home(n, lead)
                f['step'] = dict(t=0.0, dur=max(0.55, 0.9 - self._speed * 0.3), **{'from': Vec3(*f['pos']), 'to': to},
                                 lift=0.18 + 0.15 * min(1, self._speed))

    # ------------------------------------------------------------ поза
    def _apply_pose(self, dt):
        r = _smooth(0, 1, self._rest)
        stepping = sum(1 for f in self.feet.values() if f['step'])
        bob = math.sin(self._t * 3.2) * 0.03 * min(1, self._speed) if stepping else 0
        self.body.y = STAND_H + (REST_H - STAND_H) * r + bob
        self.body.rotation_x = math.sin(self._t * 1.6) * 1.2 * min(1, self._speed)
        self.body.rotation_z = math.sin(self._t * 1.6 + 1) * 1.5 * min(1, self._speed)
        for n in HIPS:
            self._solve_leg(n)

        h = _smooth(0, 1, self._hum)
        for i in range(3):
            a = NECK_STAND[i] + (NECK_REST[i] - NECK_STAND[i]) * r
            a = a + (NECK_HUM[i] - a) * h * (1 - r)
            a += math.sin(self._t * 0.7 + i) * 2.5 * (1 - r)            # медленно покачивает шеей
            self.p[f'neck{i}'].rotation_x = a
        # голова держится примерно горизонтально (лёжа — опущена к земле)
        total = sum(self.p[f'neck{i}'].rotation_x for i in range(3))
        head = self.p['head']
        head.rotation_x = -total + 8 + 25 * r - 25 * h + self._look_pitch
        self.p['neck0'].rotation_y = self._head_yaw * 0.4 * (1 - r)
        head.rotation_y = self._head_yaw * 0.6 * (1 - r)

        # моргание и свечение глаз
        open_ = (1 - self._blink) * (1 - 0.92 * r)
        for sx in (1, -1):
            self.p[f'eye_{sx}'].scale_y = max(0.08, open_)
        glow = (0.35 + 1.6 * h) * (1 - 0.8 * r)
        self.glow = glow
        for sx in (1, -1):
            self.p[f'eye_{sx}'].set_shader_input('glow', glow)

        # корешки и ёлка покачиваются
        for i in range(16):
            t = self.p.get(f'tendril_{i}')
            if t:
                t.rotation_x = math.sin(self._t * 1.3 + i) * 6 * (1 - r) + self._speed * 10
                t.rotation_z = math.cos(self._t * 1.1 + i * 2) * 5 * (1 - r)
        self.p['spruce'].rotation_z = -3 + math.sin(self._t * 1.6) * 2.0 * min(1, self._speed + 0.2)

    # ------------------------------------------------------------ споры
    def _spawn_spore(self):
        a = random.uniform(0, 6.28)
        r = random.uniform(0.2, 1.0)
        local = Point3(math.cos(a) * r * 0.9, 0.25 + random.uniform(0, 0.3), math.sin(a) * r * 1.1)
        wp = scene.getRelativePoint(self.body, local)
        s = Entity(model='quad', texture='radial_gradient', billboard=True, shader=unlit_shader, position=Vec3(*wp),
                   scale=random.uniform(0.03, 0.06), color=Vec4(1.0, 0.8, 0.35, 0))
        s.set_depth_write(False)
        s.vel = Vec3(random.uniform(-.1, .1), random.uniform(0.25, 0.5), random.uniform(-.1, .1))
        s.life = 0
        s.max_life = random.uniform(2.5, 4.0)
        s.phase = random.uniform(0, 6.28)
        self.spores.append(s)

    def _update_spores(self, dt):
        alive = []
        for s in self.spores:
            s.life += dt
            k = s.life / s.max_life
            if k >= 1:
                destroy(s)
                continue
            s.position += (s.vel + Vec3(math.sin(s.life * 2 + s.phase) * 0.15, 0, math.cos(s.life * 1.7 + s.phase) * 0.15)) * dt
            a = _smooth(0, 0.15, k) * (1 - _smooth(0.6, 1, k)) * (0.6 + 0.4 * math.sin(s.life * 9 + s.phase))
            s.color = Vec4(1.0, 0.8, 0.35, a)
            alive.append(s)
        self.spores = alive

    # ------------------------------------------------------------ кадр
    def update(self):
        dt = self.fixed_dt or min(utime.dt, 1 / 20)
        self._t += dt
        NodePath.set_shader_input(scene, 'time', self._t)
        NodePath.set_shader_input(scene, 'cam_pos', Vec3(*camera.world_position))

        # лечь / встать — медленно, около 3 секунд
        self._rest = _approach(self._rest, self._rest_target, 1.3, dt)
        if abs(self._rest - self._rest_target) < 0.002:
            self._rest = self._rest_target

        # гудение
        if self._hum_t >= 0:
            self._hum_t += dt
            target = 1.0 if self._hum_t < self._hum_dur else 0.0
            if self._hum_t > self._hum_dur + 2:
                self._hum_t = -1
            if target > 0 and random.random() < dt * 18:
                self._spawn_spore()
        else:
            target = 0.0
        self._hum = _approach(self._hum, target, 2.0, dt)

        # движение
        vel = Vec3(0, 0, 0)
        if self._goal is not None and self._rest < 0.05:
            to = self._goal - self.position
            to.y = 0
            dist = to.length()
            if dist < 0.15:
                self._goal = None
            else:
                want = math.degrees(math.atan2(to.x, to.z))
                turn = _angle_diff(self.rotation_y, want)
                self.rotation_y += max(-35 * dt, min(35 * dt, turn))
                facing = 1.0 if abs(turn) < 35 else 0.25
                self._speed = _approach(self._speed, self.max_speed * min(1, dist / 1.5) * facing, 1.5, dt)
                vel = to.normalized() * self._speed
                self.position += vel * dt
        if self._goal is None:
            self._speed = _approach(self._speed, 0, 3, dt)

        self._update_feet(dt, vel)

        # куда смотрит
        if self.look_target is not None:
            tp = self.look_target.world_position if hasattr(self.look_target, 'world_position') else Vec3(*self.look_target)
            d = Vec3(*tp) - self.world_position
            want = max(-70, min(70, _angle_diff(self.world_rotation_y, math.degrees(math.atan2(d.x, d.z)))))
        else:
            want = math.sin(self._t * 0.21) * 25        # оглядывается сам
        self._head_yaw = _approach(self._head_yaw, want, 1.2, dt)

        # моргание
        self._blink_timer -= dt
        if self._blink_timer <= 0:
            self._blink_t = 0.0
            self._blink_timer = random.uniform(3, 7)
        if hasattr(self, '_blink_t'):
            self._blink_t += dt
            self._blink = math.sin(min(self._blink_t / 0.22, 1) * math.pi)

        self._apply_pose(dt)
        self._update_spores(dt)

    def on_destroy(self):
        for s in self.spores:
            destroy(s)


def _lerp_vec(a, b, t):
    return a + (b - a) * t


__all__ = ['Kochkar', 'set_environment']
