"""
«Ледяной двойник» — существо, которое снимает чужую внешность.

Истинный облик: 2.8 м, худая пустая оболочка из инея и заледеневшей бересты,
внутри темнота и кружащий снег. Лицо — гладкий овал льда, отражает того, кто смотрит.
Голос идёт из трещины на горле, поэтому губы маски двигаются чуть невпопад.

Быстрый старт:

    from monsters.frost_mimic import FrostMimic
    mimic = FrostMimic(position=(0, 0, 0), form='mask', mirror_target=camera)
    mimic.reveal()          # маска -> истинный облик
    mimic.disguise()        # обратно в человека
    mimic.speak(2.5)        # «говорит» 2.5 секунды
    mimic.glide_to((3, 0, 4))
    mimic.look_target = player   # голова следит за игроком
"""
import math
import random

import numpy as np
from panda3d.core import (BitMask32, NodePath, PerspectiveLens, Point3, Texture,
                          TransparencyAttrib)
from ursina import (Entity, Mesh, Vec3, Vec4, application, camera, destroy,
                    scene, time as utime)
from ursina.shaders import unlit_shader

from .frost_mesh import build_human, build_true_form, shard
from .frost_shaders import (GLOBAL_DEFAULTS, crack_shader, face_shader,
                            frost_ground_shader, mask_shader, shell_shader)

MIRROR_MASK = BitMask32.bit(9)      # что не видит камера-зеркало

TRUE_HEIGHT = 2.8
MASK_HEIGHT = 1.8

# насколько «глубокая» пустота внутри каждой части (для слоёв снега)
INNER_DEPTH = dict(torso=1.0, skull=0.8, neck=0.35, upperarm=0.45, forearm=0.35, hand=0.15,
                   finger=0.08, thumb=0.08, thigh=0.55, shin=0.4, foot=0.25)


def _smooth(a, b, x):
    if b == a:
        return 1.0 if x >= b else 0.0
    t = min(max((x - a) / (b - a), 0.0), 1.0)
    return t * t * (3 - 2 * t)


def _ease_out_back(t, s=1.4):
    t = min(max(t, 0.0), 1.0) - 1
    return t * t * ((s + 1) * t + s) + 1


def _approach(cur, target, rate, dt):
    return cur + (target - cur) * (1 - math.exp(-rate * dt))


def _angle_diff(a, b):
    return (b - a + 180) % 360 - 180


def _palette_key(name):
    for key, names in (('coat', ('torso', 'upperarm', 'forearm')), ('pants', ('thigh', 'shin')),
                       ('boots', ('foot',)), ('hair', ('hair', 'brow')), ('lips', ('lip',)),
                       ('eyes', ('iris',)),
                       ('skin', ('skull', 'neck', 'hand', 'ear', 'nose'))):
        if any(name.startswith(n) for n in names):
            return key
    return None


class _Particle(Entity):
    pass


class FrostPatch(Entity):
    """Пятно инея на земле. Растёт, пока существо стоит, и медленно тает потом."""

    def __init__(self, max_radius=2.2, grow_time=9.0, **kwargs):
        size = max_radius * 2.6
        super().__init__(model='quad', rotation_x=90, scale=size, shader=frost_ground_shader,
                         double_sided=True, **kwargs)
        self.setTransparency(TransparencyAttrib.M_alpha)
        self.set_depth_write(False)
        self.size = size
        self.max_radius = max_radius
        self.grow_time = grow_time
        self.radius = 0.0
        self.fade = 1.0
        self.growing = True
        self.set_shader_input('decal_size', size)
        self.set_shader_input('seed', random.uniform(0, 50))
        self.set_shader_input('radius', 0.0)
        self.set_shader_input('fade', 1.0)

    def tick(self, dt):
        if self.growing:
            # быстро в начале, потом медленнее — как настоящий иней
            self.radius += (self.max_radius - self.radius) * dt / self.grow_time * 2.2
        else:
            self.fade -= dt / 14.0
        self.set_shader_input('radius', self.radius)
        self.set_shader_input('fade', max(self.fade, 0.0))
        return self.fade > 0


def build_rig(specs, root, human):
    """Создаёт Entity для каждой части спецификации. Возвращает dict имя -> Entity."""
    parts = {}
    for s in specs:
        parent = parts.get(s.parent, root)
        if s.mesh is None:
            e = Entity(parent=parent, position=s.pos, rotation=s.rot)
        else:
            m = Mesh(**s.mesh.to_ursina_args())
            if s.kind == 'face':
                sh = face_shader
            elif s.kind == 'crack':
                sh = crack_shader
            elif human:
                sh = mask_shader
            else:
                sh = shell_shader
            e = Entity(parent=parent, position=s.pos, rotation=s.rot, model=m, shader=sh,
                       double_sided=human)
            e.set_shader_input('part_offset', Vec3(*s.body_pos))
            if human:
                e.set_shader_input('base_color', Vec3(*s.color))
                e.set_shader_input('is_skin', 1.0 if s.kind in ('skin',) else 0.0)
            elif s.kind == 'shell':
                key = s.name.split('_')[0]
                e.set_shader_input('inner_depth', INNER_DEPTH.get(key, 0.3))
                e.set_shader_input('breach', 1.0 if s.name == 'torso' else 0.0)
                e.set_shader_input('frost_boost', 1.0 if key == 'foot' else 0.4 if key == 'shin' else 0.0)
                e.setTransparency(TransparencyAttrib.M_alpha)
            elif s.kind == 'crack':
                e.setTransparency(TransparencyAttrib.M_alpha)
                e.set_depth_offset(2)
            if s.kind == 'face' or s.name == 'skull':
                e.hide(MIRROR_MASK)
        e.name = s.name
        parts[s.name] = e
    return parts


_scene_ready = False


def init_scene_uniforms():
    """Общие uniform-ы (время, камера, свет, туман) живут на корне сцены — их наследуют все."""
    global _scene_ready
    if _scene_ready:
        return
    for k, v in GLOBAL_DEFAULTS.items():
        NodePath.set_shader_input(scene, k, Vec3(*v) if isinstance(v, tuple) else v)
    _scene_ready = True


def set_environment(light_dir=None, light_color=None, fog_color=None, fog_density=None, snow=None):
    init_scene_uniforms()
    if snow is not None:
        NodePath.set_shader_input(scene, 'snow', float(snow))
    for k, v in (('light_dir', light_dir), ('light_color', light_color), ('fog_color', fog_color)):
        if v is not None:
            NodePath.set_shader_input(scene, k, Vec3(*v))
    if fog_density is not None:
        NodePath.set_shader_input(scene, 'fog_density', fog_density)


def _fallback_texture():
    t = Texture('frost_fallback')
    t.setup2dTexture(1, 1, Texture.T_unsigned_byte, Texture.F_rgb)
    return t


def make_human(palette=None, **kwargs):
    """Обычный человек тем же сборщиком (наблюдатель/жертва в демо)."""
    init_scene_uniforms()
    root = Entity(**kwargs)
    specs = build_human(seed=23, palette=palette)
    root.parts = build_rig(specs, root, human=True)
    for k in ('frost', 'crack', 'shatter', 'voice'):
        NodePath.set_shader_input(root, k, 0.0)
    for k in ('throat_pos', 'hand_r_pos', 'hand_l_pos'):
        NodePath.set_shader_input(root, k, Vec3(0, -10, 0))
    root.palette = palette or {}
    return root


class FrostMimic(Entity):
    fixed_dt = None     # для рендера кадров с постоянным шагом

    def __init__(self, form='mask', mirror_target=None, mask_palette=None, mirror=True,
                 mask_frost_clue=True, **kwargs):
        super().__init__(**kwargs)
        init_scene_uniforms()

        self.mirror_target = mirror_target or camera
        self.look_target = None
        self.mask_frost_clue = mask_frost_clue
        self.form = form                      # 'mask' | 'true' | 'revealing' | 'disguising'
        self._t = 0.0
        self._tr_t = 0.0

        # --- истинный облик
        self.true_root = Entity(parent=self)
        self.true_specs = build_true_form()
        self.true = build_rig(self.true_specs, self.true_root, human=False)
        # --- маска
        self.mask_root = Entity(parent=self)
        self.mask_specs = build_human(palette=mask_palette)
        self.mask = build_rig(self.mask_specs, self.mask_root, human=True)
        bp = {p.name: p.body_pos for p in self.mask_specs}
        NodePath.set_shader_input(self.mask_root, 'throat_pos', Vec3(0, bp['neck'][1] + 0.05, 0.05))
        NodePath.set_shader_input(self.mask_root, 'hand_r_pos', Vec3(*bp['hand_R']) + Vec3(0, -0.1, 0))
        NodePath.set_shader_input(self.mask_root, 'hand_l_pos', Vec3(*bp['hand_L']) + Vec3(0, -0.1, 0))

        # тень-пятно под ногами
        self.shadow = Entity(parent=self, model='quad', texture='radial_gradient', rotation_x=90, y=0.003,
                             scale=1.3, color=Vec4(0, 0, 0, 0.55), shader=unlit_shader)
        self.shadow.set_depth_write(False)

        # состояние анимации
        self.voice = 0.0
        self._speak_t = -1.0
        self._speak_dur = 0.0
        self._goal = None
        self._speed = 0.0
        self.max_speed = 1.15
        self._phase = 0.0
        self._twitch_timer = random.uniform(3, 6)
        self._twitch = 0.0
        self._twitch_target = 0.0
        self._head_yaw = 0.0
        self._patch = None
        self.patches = []
        self.particles = []
        self.shards = []
        self._shard_models = [Mesh(**shard(size=random.uniform(0.012, 0.03)).to_ursina_args()) for _ in range(8)]
        self._shards_spawned = 0
        self.copy_amount = 0.0

        self._set_frost_state(frost=0.0, crack=0.0, shatter=0.0)
        if form == 'true':
            self._show_true(1.0)
        else:
            self._show_mask()

        self.mirror_cam = None
        if mirror and application.base.win is not None:
            self._setup_mirror()
        else:
            self.true['face'].set_shader_input('reflection', _fallback_texture())
            self._set_on_faces('has_reflection', 0.0)

    def _set_on_faces(self, name, value):
        self.true['face'].set_shader_input(name, value)

    def _setup_mirror(self):
        base = application.base
        self._mirror_buf = base.win.makeTextureBuffer('frost_mirror', 256, 320)
        self._mirror_buf.setClearColor(Vec4(*GLOBAL_DEFAULTS['fog_color'], 1))
        self._mirror_buf.setSort(-20)
        lens = PerspectiveLens()
        lens.setFov(34, 42)
        lens.setNear(0.05)
        lens.setFar(80)
        self.mirror_cam = base.makeCamera(self._mirror_buf, lens=lens)
        self.mirror_cam.reparentTo(scene)
        self.mirror_cam.node().setCameraMask(MIRROR_MASK)
        tex = self._mirror_buf.getTexture()
        tex.setMinfilter(Texture.FT_linear)
        tex.setMagfilter(Texture.FT_linear)
        self.true['face'].set_shader_input('reflection', tex)
        self._set_on_faces('has_reflection', 1.0)

    # ------------------------------------------------------------ публичное API
    def speak(self, seconds=2.5):
        """Существо говорит: светится трещина на горле, у маски губы двигаются с опозданием."""
        self._speak_t = 0.0
        self._speak_dur = seconds

    def glide_to(self, target):
        self._goal = Vec3(*target)
        self._goal.y = self.y

    def stop(self):
        self._goal = None

    def reveal(self):
        if self.form in ('mask', 'disguising'):
            self.form = 'revealing'
            self._tr_t = 0.0
            self._shards_spawned = 0
            self.true_root.enabled = True

    def disguise(self):
        if self.form in ('true', 'revealing'):
            self.form = 'disguising'
            self._tr_t = 0.0
            self.mask_root.enabled = True

    def toggle_form(self):
        if self.form in ('mask', 'disguising'):
            self.reveal()
        else:
            self.disguise()

    def copy_appearance(self, palette):
        """Маска «снимает» внешность: перекрашивает одежду/кожу в цвета жертвы."""
        for name, e in self.mask.items():
            key = _palette_key(name)
            if key and key in palette and e.model:
                e.set_shader_input('base_color', Vec3(*palette[key]))

    def set_environment(self, light_dir=None, light_color=None, fog_color=None, fog_density=None):
        set_environment(light_dir, light_color, fog_color, fog_density)
        if fog_color is not None and self.mirror_cam is not None:
            self._mirror_buf.setClearColor(Vec4(*fog_color, 1))

    # ------------------------------------------------------------ состояния формы
    def _set_frost_state(self, frost, crack, shatter):
        NodePath.set_shader_input(self.mask_root, 'frost', frost)
        NodePath.set_shader_input(self.mask_root, 'crack', crack)
        NodePath.set_shader_input(self.mask_root, 'shatter', shatter)

    def _show_true(self, materialize, stretch=1.0):
        NodePath.set_shader_input(self.true_root, 'materialize', materialize)
        sy = MASK_HEIGHT / TRUE_HEIGHT + (1 - MASK_HEIGHT / TRUE_HEIGHT) * stretch
        sxz = 0.75 + 0.25 * min(stretch, 1.0)
        self.true_root.scale = Vec3(sxz, sy, sxz)
        self.true_root.enabled = materialize > 0
        if self.form == 'true':
            self.mask_root.enabled = False

    def _show_mask(self):
        self.mask_root.enabled = True
        self.true_root.enabled = False
        NodePath.set_shader_input(self.true_root, 'materialize', 0.0)
        self._set_frost_state(0, 0, 0)

    def _update_transition(self, dt):
        self._tr_t += dt
        t = self._tr_t
        if self.form == 'revealing':
            frost = _smooth(0.0, 1.5, t)
            crack = _smooth(0.9, 2.0, t)
            shatter = _smooth(1.9, 2.9, t)
            self._set_frost_state(frost, crack, shatter)
            # маска мелко дрожит, пока трескается
            jit = 0.004 * frost * (1 - shatter)
            self.mask_root.position = Vec3(random.uniform(-jit, jit), 0, random.uniform(-jit, jit))
            # осколки
            want = int(90 * shatter)
            while self._shards_spawned < want:
                self._spawn_shard()
                self._shards_spawned += 1
            mat = _smooth(2.0, 3.1, t)
            stretch = _ease_out_back((t - 2.3) / 1.3) if t > 2.3 else 0.0
            if mat > 0:
                NodePath.set_shader_input(self.true_root, 'materialize', mat)
                self.true_root.enabled = True
                sy = MASK_HEIGHT / TRUE_HEIGHT + (1 - MASK_HEIGHT / TRUE_HEIGHT) * stretch
                sxz = 0.75 + 0.25 * min(stretch, 1.0)
                self.true_root.scale = Vec3(sxz, sy, sxz)
            if t > 2.95:
                self.mask_root.enabled = False
            if t >= 3.7:
                self.form = 'true'
                self._show_true(1.0, 1.0)
        elif self.form == 'disguising':
            k = t / 2.2
            stretch = 1 - _smooth(0.0, 0.6, k)
            mat = 1 - _smooth(0.2, 0.75, k)
            self._show_true(mat, stretch)
            self.mask_root.enabled = True
            self.mask_root.position = Vec3(0, 0, 0)
            # маска «намерзает» обратно: осколки возвращаются, трещины затягиваются, иней тает
            self._set_frost_state(1 - _smooth(0.65, 1.0, k), 1 - _smooth(0.5, 0.85, k), 1 - _smooth(0.25, 0.6, k))
            if k >= 1.0:
                self.form = 'mask'
                self._show_mask()

    # ------------------------------------------------------------ голос
    def _voice_env(self, t, freq=3.6, lag=0.0):
        t -= lag
        if t < 0 or t > self._speak_dur:
            return 0.0
        syll = abs(math.sin(t * 2 * math.pi * freq * 0.5 + 1.3 * math.sin(t * 1.7))) ** 1.6
        words = 0.55 + 0.45 * math.sin(t * 2 * math.pi * 0.9 + 0.5)
        fade = _smooth(0, 0.12, t) * (1 - _smooth(self._speak_dur - 0.2, self._speak_dur, t))
        return max(0.0, min(1.0, syll * words * fade * 1.25))

    # ------------------------------------------------------------ частицы
    def _spawn_breath(self, world_pos, forward):
        p = _Particle(model='quad', texture='radial_gradient', billboard=True, shader=unlit_shader,
                      position=world_pos, scale=0.03, color=Vec4(0.8, 0.9, 1.0, 0.0))
        p.setTransparency(TransparencyAttrib.M_alpha)
        p.set_depth_write(False)
        p.hide(MIRROR_MASK)
        p.vel = forward * random.uniform(0.15, 0.32) + Vec3(random.uniform(-.04, .04), -0.12, random.uniform(-.04, .04))
        p.life = 0.0
        p.max_life = random.uniform(1.1, 1.8)
        p.peak = random.uniform(0.07, 0.16)
        p.grow = random.uniform(0.03, 0.07)
        self.particles.append(p)

    def _spawn_mote(self):
        r = random.uniform(0.25, 0.7)
        a = random.uniform(0, 2 * math.pi)
        pos = self.world_position + Vec3(math.cos(a) * r, random.uniform(0.05, 2.4), math.sin(a) * r)
        p = _Particle(model='quad', texture='radial_gradient', billboard=True, shader=unlit_shader,
                      position=pos, scale=0.012, color=Vec4(0.85, 0.93, 1.0, 0.0))
        p.setTransparency(TransparencyAttrib.M_alpha)
        p.set_depth_write(False)
        p.vel = Vec3(-math.sin(a), 0, math.cos(a)) * 0.05 + Vec3(0, -0.03, 0)
        p.life = 0.0
        p.max_life = random.uniform(3, 5)
        p.peak = random.uniform(0.3, 0.7)
        p.grow = 0.0
        self.particles.append(p)

    def _spawn_shard(self):
        names = [n for n, e in self.mask.items() if e.model and n in
                 ('torso', 'neck', 'skull', 'upperarm_R', 'upperarm_L', 'forearm_R', 'forearm_L', 'hand_R', 'hand_L',
                  'thigh_R', 'thigh_L', 'shin_R', 'shin_L')]
        name = random.choice(names)
        part = self.mask[name]
        spec = next(s for s in self.mask_specs if s.name == name)
        v = spec.mesh.vertices[random.randrange(len(spec.mesh.vertices))]
        wp = scene.getRelativePoint(part, Point3(*map(float, v)))
        c = random.choice([(0.85, 0.92, 1.0), (0.75, 0.84, 0.95), tuple(np.array(spec.color) * 0.6 + 0.35)])
        s = Entity(model=random.choice(self._shard_models), position=Vec3(*wp), shader=unlit_shader,
                   color=Vec4(*c, 1), double_sided=True,
                   rotation=(random.uniform(0, 360), random.uniform(0, 360), random.uniform(0, 360)))
        s.setTransparency(TransparencyAttrib.M_alpha)
        out = Vec3(wp[0] - self.world_x, 0, wp[2] - self.world_z)
        out = out.normalized() if out.length() > 0 else Vec3(1, 0, 0)
        s.vel = out * random.uniform(0.2, 0.8) + Vec3(0, random.uniform(0.0, 0.8), 0)
        s.spin = Vec3(random.uniform(-400, 400), random.uniform(-400, 400), random.uniform(-400, 400))
        s.life = 0.0
        s.landed = False
        self.shards.append(s)

    def _update_particles(self, dt):
        alive = []
        for p in self.particles:
            p.life += dt
            k = p.life / p.max_life
            if k >= 1:
                destroy(p)
                continue
            p.position += p.vel * dt
            p.vel *= (1 - 0.6 * dt)
            p.scale = p.scale_x + p.grow * dt
            a = p.peak * _smooth(0, 0.15, k) * (1 - _smooth(0.5, 1.0, k))
            p.color = Vec4(p.color[0], p.color[1], p.color[2], a)
            alive.append(p)
        self.particles = alive

        alive = []
        for s in self.shards:
            s.life += dt
            if not s.landed:
                s.vel += Vec3(0, -6.0, 0) * dt
                s.position += s.vel * dt
                s.rotation += s.spin * dt
                if s.y <= self.world_y + 0.01:
                    s.y = self.world_y + 0.01
                    s.landed = True
                    s.land_t = s.life
            else:
                fade = 1 - (s.life - s.land_t) / 2.5
                if fade <= 0:
                    destroy(s)
                    continue
                c = s.color
                s.color = Vec4(c[0], c[1], c[2], fade)
            alive.append(s)
        self.shards = alive

    # ------------------------------------------------------------ кадр
    def update(self):
        dt = self.fixed_dt or min(utime.dt, 1 / 20)
        self._t += dt
        NodePath.set_shader_input(scene, 'time', self._t)
        NodePath.set_shader_input(scene, 'cam_pos', Vec3(*camera.world_position))

        if self.form in ('revealing', 'disguising'):
            self._update_transition(dt)

        is_true = self.form in ('true', 'revealing')
        rig = self.true if is_true else self.mask

        # --- голос
        if self._speak_t >= 0:
            self._speak_t += dt
            self.voice = self._voice_env(self._speak_t)
            lips = self._voice_env(self._speak_t, freq=3.1, lag=0.17)  # губы опаздывают и сбиваются с ритма
            if self._speak_t > self._speak_dur + 0.4:
                self._speak_t = -1
        else:
            self.voice = _approach(self.voice, 0, 10, dt)
            lips = 0.0
        self.true['throat_crack'].set_shader_input('voice', self.voice)
        self.true['throat_crack'].scale_x = 1 + self.voice * 1.4
        NodePath.set_shader_input(self.true_root, 'crack_glow', self.voice * 0.8)
        NodePath.set_shader_input(self.mask_root, 'voice', self.voice)
        self.mask['jaw'].rotation_x = lips * 13
        self.mask['mouth_dark'].scale_y = 1 + lips * 2.2

        if is_true and self.voice > 0.35 and random.random() < dt * 30:
            crack = self.true['throat_crack']
            fwd = Vec3(*scene.getRelativeVector(self.true['head'], Vec3(0, 0, 1))).normalized()
            self._spawn_breath(Vec3(*crack.world_position) + fwd * 0.03, fwd)
        if self.form == 'true' and random.random() < dt * 4:
            self._spawn_mote()

        # --- движение: плавное скольжение без покачиваний
        moving = False
        if self._goal is not None:
            to = self._goal - self.position
            to.y = 0
            dist = to.length()
            if dist < 0.05:
                self._goal = None
            else:
                moving = True
                want_yaw = math.degrees(math.atan2(to.x, to.z))
                turn = _angle_diff(self.rotation_y, want_yaw)
                self.rotation_y += max(-75 * dt, min(75 * dt, turn))
                facing = abs(turn) < 50
                target_speed = self.max_speed * min(1.0, dist / 1.2) * (1.0 if facing else 0.15)
                self._speed = _approach(self._speed, target_speed, 2.5, dt)
                self.position += to.normalized() * self._speed * dt
        if not moving:
            self._speed = _approach(self._speed, 0, 4, dt)

        sp = self._speed / self.max_speed
        self._phase += dt * (1.3 + 1.2 * sp) * sp * 2 * math.pi
        swing = math.sin(self._phase) * 9 * sp      # суставы почти не сгибаются
        for side, sgn in (('R', 1), ('L', -1)):
            if f'hip_{side}' in rig:
                rig[f'hip_{side}'].rotation_x = -swing * sgn
                rig[f'knee_{side}'].rotation_x = max(0, math.sin(self._phase + (0 if sgn > 0 else math.pi))) * 5 * sp
                rig[f'shoulder_{side}'].rotation_x = swing * sgn * 0.25
                base_z = -4 if rig is self.true else -5
                rig[f'shoulder_{side}'].rotation_z = sgn * base_z

        # --- голова: ведёт поворот раньше тела; редкие резкие подёргивания
        if self.look_target is not None:
            tp = self.look_target.world_position if hasattr(self.look_target, 'world_position') else Vec3(*self.look_target)
            d = Vec3(*tp) - self.world_position
            want = _angle_diff(self.world_rotation_y, math.degrees(math.atan2(d.x, d.z)))
            want = max(-105, min(105, want))      # чуть дальше, чем может человек
        else:
            want = 0
        self._head_yaw = _approach(self._head_yaw, want, 2.2, dt)
        self._twitch_timer -= dt
        if self._twitch_timer <= 0:
            self._twitch_target = random.choice((-1, 1)) * random.uniform(10, 22) if self._twitch_target == 0 else 0
            self._twitch_timer = random.uniform(0.8, 1.6) if self._twitch_target != 0 else random.uniform(4, 9)
        self._twitch = _approach(self._twitch, self._twitch_target, 25 if self._twitch_target else 1.5, dt)
        head = rig['head']
        head.rotation_y = self._head_yaw * 0.75
        rig['neck'].rotation_y = self._head_yaw * 0.25
        head.rotation_z = self._twitch if rig is self.true else self._twitch * 0.2

        # --- иней под ногами
        if self.form == 'true' and self._speed < 0.05:
            if self._patch is None:
                self._patch = FrostPatch(position=self.world_position + Vec3(0, 0.004 + len(self.patches) % 7 * 0.0006, 0))
                self.patches.append(self._patch)
        elif self.form == 'mask' and self.mask_frost_clue and self._speed < 0.05:
            if self._patch is None:
                self._patch = FrostPatch(max_radius=0.45, grow_time=20,
                                         position=self.world_position + Vec3(0, 0.004 + len(self.patches) % 7 * 0.0006, 0))
                self.patches.append(self._patch)
        elif self._patch is not None:
            self._patch.growing = False
            self._patch = None
        self.patches = [p for p in self.patches if p.tick(dt) or destroy(p)]

        self._update_particles(dt)

        # --- лицо-зеркало «снимает» смотрящего, когда тот близко
        if self.mirror_cam is not None and self.true_root.enabled:
            face = self.true['face']
            fwd = Vec3(*scene.getRelativeVector(self.true['head'], Vec3(0, 0, 1))).normalized()
            fp = Vec3(*scene.getRelativePoint(self.true['head'], Point3(0, 0.15, 0.12)))
            self.mirror_cam.setPos(scene, fp + fwd * 0.02)
            tgt = self.mirror_target
            tp = Vec3(*(tgt.world_position if hasattr(tgt, 'world_position') else tgt))
            # зеркало: смотрим туда, куда отражается взгляд смотрящего
            to_viewer = (tp - fp).normalized()
            refl = (to_viewer - fwd * 2 * to_viewer.dot(fwd)) * -1
            if fwd.dot(to_viewer) > 0:
                look = tp
            else:
                look = fp + refl
            self.mirror_cam.lookAt(scene, Point3(*look))
            dist = (tp - fp).length()
            near = _smooth(6.0, 2.0, dist) * max(0.0, fwd.dot(to_viewer))
            self.copy_amount = _approach(self.copy_amount, near, 0.8, dt)
            face.set_shader_input('copy_amount', self.copy_amount)
        else:
            self.true['face'].set_shader_input('copy_amount', 0.0)

    def on_destroy(self):
        for p in self.particles + self.shards + self.patches:
            destroy(p)
        if self.mirror_cam is not None:
            application.base.graphicsEngine.removeWindow(self._mirror_buf)
            self.mirror_cam.removeNode()
