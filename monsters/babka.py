"""
«Бабка» — враг (по фото-референсу).

Измождённая старуха в длинном грязном покрывале сидит на ступеньке крыльца, закрыв рот
ладонями, и смотрит на тебя. Подойдёшь — медленно встаёт. Она выше человека, руки и пальцы
слишком длинные. Идёт следом, не отнимая ладоней от лица; голос глухой, из-под ладоней.
Когда хватает — опускает руки: рта под ними нет, только гладкая кожа.
Свет фонаря ей неприятен: закрывает глаза ладонями и замирает на пару секунд.

    from monsters.babka import Babka
    b = Babka(position=(0, 0, 9), target=player_head, sitting=True)
    b.on_say = show_subtitle
    b.on_catch = game_over
    b.flash()
"""
import math
import random

from panda3d.core import NodePath, Point3
from ursina import Entity, Mesh, Vec3, Vec4, camera, scene, time as utime
from ursina.shaders import unlit_shader

from .babka_mesh import NECK_MAX, PELVIS_Y, SEAT_H, build_babka, skirt_vertices
from .babka_shaders import FRAYED, MATERIALS, WINDY, cloth_shader
from .frost_mimic import init_scene_uniforms

L_UP, L_FORE = 0.43, 0.43
SX, SZ = -1, -1          # знаки поворотов (как у ног Кочкаря — та же иерархия)

LINES_NOTICE = ['…тише…', 'Ты чей будешь?..', 'Я тебя ждала.']
LINES_CHASE = ['Не ходи туда, внучек…', 'Посиди со мной…', 'Куда же ты…', 'Тш-ш-ш…']
LINES_LOST = ['…вернёшься.', '…я подожду.']
LINES_IDLE = ['…', '…м-м-м…', '…тише…']


def _approach(cur, target, rate, dt):
    return cur + (target - cur) * (1 - math.exp(-rate * dt))


def _angle_diff(a, b):
    return (b - a + 180) % 360 - 180


def _lerp(a, b, t):
    return a + (b - a) * t


class Babka(Entity):
    fixed_dt = None
    detect_range = 9.0
    lose_range = 24.0
    fov = 80

    def __init__(self, target=None, waypoints=None, sitting=True, **kwargs):
        super().__init__(**kwargs)
        init_scene_uniforms()
        self.target = target
        self.waypoints = [Vec3(*w) for w in (waypoints or [])]
        self._wp = 0
        self.on_say = None
        self.on_catch = None
        self.state = 'sit' if sitting else 'patrol'
        self._st = 0.0
        self._t = 0.0
        self._speed = 0.0
        self._phase = 0.0
        self.sit = 1.0 if sitting else 0.0
        self._seated_origin = sitting
        self._skirt_sit = -1.0
        self.unfold = 0.0
        self.reach = 0.0
        self.cover = 1.0        # ладони у лица
        self.eyes = 0.0         # 0 — закрывает рот, 1 — закрывает глаза
        self._tilt = 0.0
        self._yaw_head = 0.0
        self._pitch_head = 0.0
        self._lunge = 0.0
        self._mutter = random.uniform(5, 9)
        self._blink_t = 9.0
        self._blink_next = random.uniform(2, 5)
        self._shudder = 0.0
        self._shudder_next = random.uniform(6, 12)
        self._sacc = Vec3(0, 0, 0)
        self._sacc_next = 0.5
        self._breath_next = 2.0
        self.puffs = []
        self._finger_seed = [random.uniform(0, 10) for _ in range(8)]

        self.p = {}
        for s in build_babka():
            parent = self.p.get(s.parent, self)
            if s.mesh is None:
                e = Entity(parent=parent, position=s.pos, rotation=s.rot)
            else:
                e = Entity(parent=parent, position=s.pos, rotation=s.rot, model=Mesh(**s.mesh.to_ursina_args(), static=False),
                           shader=cloth_shader, double_sided=s.kind == 'linen')
                e.set_shader_input('material', MATERIALS[s.kind])
                e.set_shader_input('fray', 1.0 if s.name in FRAYED else 0.0)
                e.set_shader_input('part_offset', Vec3(*s.body_pos))
                e.set_shader_input('wind', WINDY.get(s.name, 0.0))
            e.name = s.name
            self.p[s.name] = e
        self.shadow = Entity(parent=self, model='quad', texture='radial_gradient', rotation_x=90, y=0.01,
                             scale=1.3, color=Vec4(0, 0, 0, 0.5), shader=unlit_shader)
        self.shadow.set_depth_write(False)
        self._pose(0.0)

    # ------------------------------------------------------------ API
    def flash(self):
        if self.state not in ('caught',):
            self._set('stunned')
            self._say(random.choice(['…не надо…', 'Убери-и…']))

    def alert(self):
        if self.state == 'sit':
            self._set('rise')
            self._say(random.choice(LINES_NOTICE))
        elif self.state in ('patrol', 'search'):
            self._set('notice')
            self._say(random.choice(LINES_NOTICE))

    # ------------------------------------------------------------ мозг
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

    def _turn_to(self, goal, rate, dt):
        to = goal - self.world_position
        want = math.degrees(math.atan2(to.x, to.z))
        turn = _angle_diff(self.rotation_y, want)
        self.rotation_y += max(-rate * dt, min(rate * dt, turn))
        return abs(turn)

    def _brain(self, dt):
        tp = self._target_pos()
        dist, seen = 1e9, False
        if tp is not None:
            d = tp - self.world_position
            d.y = 0
            dist = d.length()
            ang = abs(_angle_diff(self.rotation_y, math.degrees(math.atan2(d.x, d.z))))
            seen = dist < self.detect_range and (ang < self.fov or dist < 2.5)
        self._st += dt
        st = self.state
        want_speed = 0.0
        if st == 'sit':
            self._mutter -= dt
            if self._mutter < 0:
                self._say(random.choice(LINES_IDLE))
                self._mutter = random.uniform(7, 14)
            if seen:
                self.alert()
        elif st == 'rise':
            if self._st > 2.8:
                self._set('chase')
                self._say(random.choice(LINES_CHASE))
        elif st == 'patrol':
            if self.waypoints:
                goal = self.waypoints[self._wp]
                if (goal - self.world_position).length() < 0.4:
                    self._wp = (self._wp + 1) % len(self.waypoints)
                turn = self._turn_to(goal, 50, dt)
                want_speed = 0.5 * max(0.2, 1 - turn / 90)
            if seen:
                self.alert()
        elif st == 'notice':
            if tp is not None:
                self._turn_to(tp, 90, dt)
            if self._st > 1.8:
                self._set('chase')
                self._say(random.choice(LINES_CHASE))
        elif st == 'chase':
            turn = self._turn_to(tp, 150, dt)
            want_speed = 2.7 * max(0.2, 1 - turn / 90)
            if dist < 1.45:
                self._set('grab')
            elif dist > self.lose_range:
                self._set('search')
                self._say(random.choice(LINES_LOST))
            elif random.random() < dt * 0.1:
                self._say(random.choice(LINES_CHASE))
        elif st == 'grab':
            if tp is not None:
                self._turn_to(tp, 200, dt)
            want_speed = 1.0
            if self._st > 0.5:
                if dist < 1.65:
                    self._set('caught')
                    self._say('…вот и посидим.')
                    if self.on_catch:
                        self.on_catch()
                else:
                    self._set('chase')
        elif st == 'caught':
            if self._st > 3.0:
                self._set('search')
        elif st == 'stunned':
            if self._st > 2.6:
                self._set('chase' if dist < self.lose_range else 'search')
        elif st == 'search':
            self.rotation_y += math.sin(self._t * 0.7) * 35 * dt
            want_speed = 0.35
            if seen and self._st > 1.0:
                self._set('notice')
            elif self._st > 6:
                self._set('patrol')
        self._speed = _approach(self._speed, want_speed, 3, dt)
        if self.sit < 0.02:
            self.position += self.forward * self._speed * dt

        # цели позы: (сидит, распрямилась, руки вперёд, ладони у лица, у глаз)
        T = dict(sit=(1, 0, 0, 1, 0), rise=(0, 0.2, 0, 1, 0), patrol=(0, 0, 0, 1, 0), notice=(0, 1, 0, 1, 0),
                 chase=(0, 0.75, 0, 1, 0), grab=(0, 1, 1, 0, 0), caught=(0, 1, 0.8, 0, 0), stunned=(0, 0.2, 0, 1, 1),
                 search=(0, 0.4, 0, 1, 0))[self.state]
        self.sit = _approach(self.sit, T[0], 1.1 if self.state == 'rise' else 3, dt)
        self.unfold = _approach(self.unfold, T[1], 1.5, dt)
        self.reach = _approach(self.reach, T[2], 7, dt)
        self.cover = _approach(self.cover, T[3], 6 if T[3] == 0 else 3, dt)
        self.eyes = _approach(self.eyes, T[4], 8, dt)
        self._lunge = _approach(self._lunge, 1.0 if self.state in ('grab', 'caught') else 0.0, 9, dt)

        # смотрит на цель всегда, когда видит (даже сидя)
        want_yaw, want_pitch = math.sin(self._t * 0.3) * 20, 0.0
        if tp is not None and dist < self.lose_range:
            d = tp - Vec3(*self.p['head'].world_position)
            want_yaw = max(-75, min(75, _angle_diff(self.world_rotation_y, math.degrees(math.atan2(d.x, d.z)))))
            want_pitch = -math.degrees(math.atan2(d.y, math.hypot(d.x, d.z)))
        self._yaw_head = _approach(self._yaw_head, want_yaw, 2.0, dt)
        self._pitch_head = _approach(self._pitch_head, max(-30, min(30, want_pitch)), 2.0, dt)
        tilt = {'notice': 22, 'rise': 10, 'chase': 8, 'grab': 16, 'caught': 26, 'search': 14, 'sit': 6}.get(self.state, 3)
        self._tilt = _approach(self._tilt, tilt, 2, dt)

    # ------------------------------------------------------------ IK руки
    def _solve_arm(self, side, target):
        sh = self.p[f'shoulder_{side}']
        d = sh.getRelativePoint(scene, Point3(*target))
        dx, dy, dz = d[0], d[1], d[2]
        ab = math.atan2(dx, -dy)
        dyp = -math.sqrt(dx * dx + dy * dy)
        if abs(ab) > math.pi / 2:          # цель выше плеча: не переворачиваем плоскость руки
            ab -= math.copysign(math.pi, ab)
            dyp = -dyp
        self.p[f'abduct_{side}'].rotation_z = SZ * math.degrees(ab)
        D = min(max(math.hypot(dz, dyp), 0.08), L_UP + L_FORE - 1e-3)
        a = math.atan2(dz, -dyp)
        b = math.acos(min(1, max(-1, (L_UP ** 2 + D ** 2 - L_FORE ** 2) / (2 * L_UP * D))))
        c = math.acos(min(1, max(-1, (L_UP ** 2 + L_FORE ** 2 - D ** 2) / (2 * L_UP * L_FORE))))
        self.p[f'upper_{side}'].rotation_x = SX * math.degrees(a - b)
        self.p[f'elbow_{side}'].rotation_x = SX * math.degrees(math.pi - c)

    def _head_point(self, x, y, z):
        return Vec3(*scene.getRelativePoint(self.p['head'], Point3(x, y, z)))

    # ------------------------------------------------------------ поза
    def _pose(self, dt):
        p = self.p
        sit = self.sit * self.sit * (3 - 2 * self.sit)
        u = self.unfold
        sp = min(self._speed / 2.7, 1.0)
        self._phase += dt * (2.0 + 4.0 * sp) * (0.25 + sp) * 2
        s = math.sin(self._phase)

        # таз: сидя — на ступеньке, стоя — над ступнями
        p['pelvis'].y = _lerp(PELVIS_Y, SEAT_H + 0.08, sit)
        if self._seated_origin:
            p['pelvis'].z = 0.45 * (1 - sit)
            if self.sit < 0.02 and self.state != 'rise':
                # встала: переносим корень вперёд, дальше идёт от ступней
                self.position += self.forward * 0.45
                p['pelvis'].z = 0.0
                self._seated_origin = False
        else:
            p['pelvis'].z = 0.0

        # платье пересчитываем, только когда меняется посадка
        if abs(self.sit - self._skirt_sit) > 0.01:
            self._skirt_sit = self.sit
            m = p['skirt'].model
            m.vertices = [tuple(map(float, v)) for v in skirt_vertices(self.sit)]
            m.generate()

        bend1 = _lerp(20 * (1 - u) + 8 * sp + 6 * self._lunge, 12, sit) + math.sin(self._t * 0.6) * 2 * sit
        bend2 = _lerp(26 * (1 - u) + 6 * sp + 6 * self._lunge, 20, sit) + 10 * self.eyes
        breath = math.sin(self._t * 1.5)
        rock = math.sin(self._t * 0.85) * 4.0 * sit                       # медленно раскачивается, как в горе
        shud = math.sin(self._t * 47.0) * 1.6 * self._shudder
        bend1 += rock + shud
        bend2 += breath * 1.3
        p['spine1'].rotation_x = bend1
        p['spine1'].rotation_z = s * 2.5 * (0.3 + sp) * (1 - sit)
        p['spine2'].rotation_x = bend2
        tilt_total = bend1 + bend2
        p['neck'].rotation_x = -6 * (1 - u) + 18 * self._lunge
        p['neck_slide'].y = NECK_MAX * max(0.0, (u - 0.3) / 0.7) + 0.08 * self._lunge
        p['head'].rotation_x = -(tilt_total + p['neck'].rotation_x) + 4 + self._pitch_head + 12 * self.eyes
        p['head'].rotation_y = self._yaw_head
        p['head'].rotation_z = self._tilt + math.sin(self._t * 0.8) * 1.5 + math.sin(self._t * 53.0) * 2.0 * self._shudder
        p['head'].rotation_x -= rock * 0.8                                   # взгляд не отрывается, пока качается
        for side, sx in (('R', 1), ('L', -1)):
            p[f'shoulder_{side}'].y = 0.26 + breath * 0.006

        # глаза: следят за целью короткими рывками; веки моргают
        for sx in (1, -1):
            eye = p[f'eye_{sx}']
            eye.rotation = Vec3(self._sacc.x - self._pitch_head * 0.3, self._sacc.y, 0)
            close = max(0.0, 1 - abs(self._blink_t - 0.09) / 0.09) if self._blink_t < 0.18 else 0.0
            close = max(close, 0.55 * self.eyes)
            p[f'lid_{sx}'].rotation_x = -18 + 52 * close
            p[f'lid_{sx}'].scale_y = 1 + 0.6 * close

        # пальцы: у лица слегка поджаты и подрагивают, при хватке растопырены и загнуты крючком
        for side in ('R', 'L'):
            for k in range(4):
                sd = self._finger_seed[k + (0 if side == 'R' else 4)]
                tap = max(0.0, math.sin(self._t * 1.3 + sd)) ** 12 * 14       # редкое «постукивание»
                twitch = math.sin(self._t * 9.0 + sd * 3) * 1.2
                curl_a = _lerp(_lerp(6, 4, self.reach) + tap + twitch, 12, self.cover) + 30 * self.reach * self._lunge
                curl_b = _lerp(10 + twitch, 18 + tap * 0.6, self.cover) + 35 * self.reach * self._lunge
                spread = (k - 1.5) * _lerp(4, 9, self.reach)
                p[f'f{k}a_{side}'].rotation = Vec3(-curl_a, 0, spread)
                p[f'f{k}b_{side}'].rotation_x = -curl_b

        # ноги
        for side, sx in (('R', 1), ('L', -1)):
            walk_hip = s * sx * (5 + 24 * sp)
            walk_knee = (6 + 12 * sp) + max(0, -s * sx) * 16 * sp
            p[f'hip_{side}'].rotation_x = _lerp(walk_hip, -88, sit)
            p[f'knee_{side}'].rotation_x = _lerp(walk_knee, 90, sit)

        # руки: цель кисти = смесь «висит» / «тянется» / «у лица»
        fz = 0.015 + 0.09
        for side, sx in (('R', 1), ('L', -1)):
            sh = Vec3(*scene.getRelativePoint(p[f'shoulder_{side}'], Point3(0, 0, 0)))
            fwd = Vec3(*scene.getRelativeVector(self, Vec3(0, 0, 1))).normalized()
            right = Vec3(*scene.getRelativeVector(self, Vec3(1, 0, 0))).normalized()
            swing = s * sx * 0.12 * (0.3 + sp) * (1 - self.reach)
            hang = sh + Vec3(0, -0.82, 0) + right * sx * 0.05 + fwd * (0.06 + swing)
            reach = sh + fwd * 0.8 + Vec3(0, -0.05 + 0.08 * self._lunge, 0) + right * sx * -0.06
            y_face = _lerp(0.045 - 0.065, 0.111 - 0.06, self.eyes)     # запястья у подбородка
            face = self._head_point(sx * 0.05, y_face, fz + 0.035)
            tgt = _lerp(_lerp(hang, reach, self.reach), face, self.cover)
            self._solve_arm(side, tgt)
            # ладонь: у лица — к лицу пальцами вверх; висит — к бедру пальцами вниз
            aim = p[f'hand_aim_{side}']
            ap = Vec3(*aim.world_position)
            head_up = Vec3(*scene.getRelativeVector(p['head'], Vec3(0, 1, 0))).normalized()
            head_fwd = Vec3(*scene.getRelativeVector(p['head'], Vec3(0, 0, 1))).normalized()
            head_right = Vec3(*scene.getRelativeVector(p['head'], Vec3(1, 0, 0))).normalized()
            d_cover = (-head_fwd - head_right * sx * 0.2).normalized()     # ладонь смотрит на лицо
            d_hang = (-right * sx + fwd * 0.2).normalized()
            d_reach = Vec3(0, -1, 0)
            d = _lerp(_lerp(d_hang, d_reach, self.reach), d_cover, self.cover).normalized()
            up = _lerp(_lerp(Vec3(0, -1, 0), fwd, self.reach), (head_up + head_right * sx * _lerp(0.42, 0.25, self.eyes)).normalized(), self.cover).normalized()
            NodePath.lookAt(aim, scene, Point3(*(ap + d)), up)

    def update(self):
        dt = self.fixed_dt or min(utime.dt, 1 / 20)
        self._t += dt
        NodePath.set_shader_input(scene, 'time', self._t)
        NodePath.set_shader_input(scene, 'cam_pos', Vec3(*camera.world_position))
        self._brain(dt)
        self._life(dt)
        self._pose(dt)

    def _life(self, dt):
        self._blink_t += dt
        self._blink_next -= dt
        if self._blink_next <= 0:
            self._blink_t = 0.0
            self._blink_next = random.uniform(2.5, 7) if self.state == 'sit' else random.uniform(5, 12)  # в погоне почти не моргает
        self._shudder_next -= dt
        if self._shudder_next <= 0:
            self._shudder = 1.0
            self._shudder_next = random.uniform(7, 14)
        self._shudder = max(0.0, self._shudder - dt * 1.6)
        self._sacc_next -= dt
        if self._sacc_next <= 0:
            self._sacc = Vec3(random.uniform(-4, 4), random.uniform(-6, 6), 0)
            self._sacc_next = random.uniform(0.3, 1.4)
        # пар изо рта сквозь пальцы
        self._breath_next -= dt
        if self._breath_next <= 0 and self.cover > 0.6:
            self._breath_next = random.uniform(2.8, 4.2)
            mouth = self._head_point(0, 0.045, 0.14)
            fwd = Vec3(*scene.getRelativeVector(self.p['head'], Vec3(0, 0, 1))).normalized()
            for _ in range(7):
                e = Entity(model='quad', texture='radial_gradient', billboard=True, shader=unlit_shader,
                           position=mouth + Vec3(random.uniform(-.03, .03), random.uniform(-.02, .02), 0),
                           scale=0.03, color=Vec4(0.85, 0.85, 0.85, 0))
                e.setTransparency(True)
                e.set_depth_write(False)
                e.vel = fwd * random.uniform(0.08, 0.16) + Vec3(random.uniform(-.03, .03), random.uniform(0.04, 0.09), 0)
                e.life = random.uniform(-0.3, 0.0)
                self.puffs.append(e)
        alive = []
        for e in self.puffs:
            e.life += dt
            if e.life >= 2.2:
                from ursina import destroy
                destroy(e)
                continue
            if e.life > 0:
                k = e.life / 2.2
                e.position += e.vel * dt
                e.scale = 0.03 + k * 0.12
                e.color = Vec4(0.85, 0.85, 0.85, 0.16 * math.sin(math.pi * k))
            alive.append(e)
        self.puffs = alive
