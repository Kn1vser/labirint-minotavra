"""
Кинематографичность: плёночная постобработка, керосиновая лампа, пыль в воздухе, низовой туман.

    from monsters.cinema import FilmLook, KeroseneLamp, Atmosphere
    film = FilmLook(grade='cinema')      # или 'sepia' — старая фотография
    film.focus_on(babka)                 # глубина резкости следит за целью
    lamp = KeroseneLamp(position=(0.55, 0.47, 0.2))
    Atmosphere(center=(0, 0, 0))
"""
import math
import random

from panda3d.core import NodePath, TransparencyAttrib
from ursina import Entity, Shader, Vec3, Vec4, camera, scene, time as utime
from ursina.shaders import unlit_shader

from .frost_mimic import init_scene_uniforms

FILM_FRAG = '''#version 140
uniform sampler2D tex;
uniform sampler2D dtex;
uniform float time;
uniform float near;
uniform float far;
uniform float focus_dist;     // м
uniform float aperture;       // сила размытия вне фокуса
uniform float letterbox;      // 0..1 — чёрные полосы 2.35:1
uniform float grade;          // 0 — кино (холод/тепло), 1 — сепия-фото
uniform float aspect;
in vec2 uv;
out vec4 color;
float h(vec2 p){ return fract(sin(dot(p, vec2(12.9898,78.233))) * 43758.5453); }
float lin(float d){ return near*far / (far - d*(far - near)); }
const vec2 PO[12] = vec2[](vec2(-0.326,-0.406), vec2(-0.840,-0.074), vec2(-0.696,0.457), vec2(-0.203,0.621),
    vec2(0.962,-0.195), vec2(0.473,-0.480), vec2(0.519,0.767), vec2(0.185,-0.893), vec2(0.507,0.064),
    vec2(0.896,0.412), vec2(-0.322,-0.933), vec2(-0.792,-0.598));
void main(){
    float z = lin(texture(dtex, uv).r);
    float coc = clamp(abs(z - focus_dist) / max(focus_dist, 0.5), 0.0, 1.0);
    coc = coc * coc * aperture;
    vec2 r = vec2(coc * 0.010 / aspect, coc * 0.010);
    // хроматическая аберрация к краям кадра
    vec2 d = uv - 0.5;
    float ca = dot(d, d) * 0.006;
    vec3 c;
    c.r = texture(tex, uv + d*ca).r;
    c.g = texture(tex, uv).g;
    c.b = texture(tex, uv - d*ca).b;
    if(coc > 0.02){
        vec3 acc = c; float wsum = 1.0;
        for(int i=0; i<12; i++){
            vec2 o = uv + PO[i]*r;
            float zi = lin(texture(dtex, o).r);
            float w = zi < z ? 1.0 : clamp(abs(zi - focus_dist)/max(focus_dist,0.5)*3.0, 0.0, 1.0);
            acc += texture(tex, o).rgb * w; wsum += w;
        }
        c = acc / wsum;
    }
    // цветокоррекция
    float g = dot(c, vec3(0.299,0.587,0.114));
    vec3 cine = mix(vec3(g), c, 0.72);                                  // приглушённые цвета
    cine = mix(cine * vec3(0.86,0.97,1.08), cine * vec3(1.10,0.98,0.84), smoothstep(0.12, 0.6, g));  // тени холодные, света тёплые
    cine = cine*1.08 + vec3(0.012,0.016,0.022);
    float gs = pow(g, 0.8) * 1.15;
    vec3 sep = vec3(gs*1.07 + 0.03, gs*0.95 + 0.02, gs*0.78);
    c = mix(cine, sep, grade);
    // плёнка: зерно, редкие пылинки и царапины, лёгкое мерцание
    float fr = floor(time * 18.0);
    c += (h(uv*vec2(1300.0, 800.0) + fr) - 0.5) * 0.06;
    float scratch = step(0.9985, h(vec2(floor(uv.x*700.0), fr))) * step(0.6, h(vec2(fr, 3.0)));
    c = mix(c, c*0.6 + 0.1, scratch);
    float dust = step(0.99995, h(floor(uv*vec2(500.0, 300.0)) + fr*7.0));
    c *= 1.0 - dust*0.8;
    c *= 0.97 + 0.03 * h(vec2(fr, 1.0));
    // виньетка
    float vig = smoothstep(0.95, 0.30, length(d*vec2(1.15, 1.0)));
    c *= mix(1.0, vig, 0.65);
    // кинорамка
    float bar = (1.0 - 1.0/2.35*aspect) * 0.5 * letterbox;
    if(uv.y < bar || uv.y > 1.0 - bar) c = vec3(0.0);
    color = vec4(c, 1.0);
}
'''
film_shader = Shader(name='film_look', language=Shader.GLSL, fragment=FILM_FRAG,
                     default_input=dict(time=0.0, near=0.1, far=10000.0, focus_dist=4.0, aperture=1.0,
                                        letterbox=1.0, grade=0.0, aspect=16 / 9))


class FilmLook(Entity):
    """Вешает постобработку на камеру и каждый кадр обновляет фокус и время."""

    def __init__(self, grade='cinema', letterbox=True, aperture=1.0):
        super().__init__()
        camera.shader = film_shader
        self.grade = 1.0 if grade == 'sepia' else 0.0
        self.letterbox = 1.0 if letterbox else 0.0
        self.aperture = aperture
        self.focus_target = None
        self.focus = 4.0
        self._t = 0.0
        self.fixed_dt = None

    def focus_on(self, target):
        self.focus_target = target

    def toggle_grade(self):
        self.grade = 1.0 - self.grade

    def update(self):
        dt = self.fixed_dt or utime.dt
        self._t += dt
        if self.focus_target is not None:
            tp = self.focus_target.world_position if hasattr(self.focus_target, 'world_position') else Vec3(*self.focus_target)
            want = max(0.3, (Vec3(*tp) - camera.world_position).length())
            self.focus += (want - self.focus) * min(1, dt * 4)
        from ursina import window
        for k, v in dict(time=self._t, near=float(camera.clip_plane_near), far=float(camera.clip_plane_far),
                         focus_dist=self.focus, aperture=self.aperture, letterbox=self.letterbox, grade=self.grade,
                         aspect=float(window.aspect_ratio)).items():
            camera.set_shader_input(k, v)


class KeroseneLamp(Entity):
    """Керосинка: жестяное основание, стеклянная колба, живое пламя. Даёт тёплый мерцающий свет сцене."""

    def __init__(self, power=1.6, **kwargs):
        super().__init__(**kwargs)
        init_scene_uniforms()
        from .frost_mesh import ellipsoid, loft
        from .babka_shaders import cloth_shader
        tin = loft([(0.0, 0.07, 0.07, 0, 0), (0.05, 0.075, 0.075, 0, 0), (0.09, 0.06, 0.06, 0, 0), (0.11, 0.03, 0.03, 0, 0),
                    (0.13, 0.035, 0.035, 0, 0)], rings=10, seg=24)
        self.base = Entity(parent=self, model=_mesh(tin), shader=cloth_shader)
        self.base.set_shader_input('material', 5)
        self.base.set_shader_input('fray', 0.0)
        self.base.set_shader_input('wind', 0.0)
        self.base.set_shader_input('part_offset', Vec3(0, 0, 0))
        glass = loft([(0.12, 0.03, 0.03, 0, 0), (0.17, 0.05, 0.05, 0, 0), (0.22, 0.045, 0.045, 0, 0), (0.29, 0.025, 0.025, 0, 0),
                      (0.31, 0.024, 0.024, 0, 0)], rings=10, seg=24)
        self.glass = Entity(parent=self, model=_mesh(glass), shader=unlit_shader, color=Vec4(1.0, 0.75, 0.42, 0.35))
        self.glass.setTransparency(TransparencyAttrib.M_alpha)
        self.flame = Entity(parent=self, model='quad', texture='radial_gradient', billboard=True, y=0.18, scale=(0.035, 0.07),
                            shader=unlit_shader, color=Vec4(1.0, 0.75, 0.35, 1.0))
        self.halo = Entity(parent=self, model='quad', texture='radial_gradient', billboard=True, y=0.18, scale=0.6,
                           shader=unlit_shader, color=Vec4(1.0, 0.6, 0.25, 0.22))
        for e in (self.flame, self.halo):
            e.setTransparency(TransparencyAttrib.M_alpha)
            e.set_depth_write(False)
            from panda3d.core import ColorBlendAttrib
            e.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.M_add, ColorBlendAttrib.O_incoming_alpha, ColorBlendAttrib.O_one))
        self.handle = Entity(parent=self, model=_mesh(ellipsoid(0.07, 0.07, 0.004, rings=8, seg=24)), y=0.2,
                             shader=unlit_shader, color=Vec4(0.08, 0.07, 0.06, 1))
        self.power = power
        self._t = random.uniform(0, 10)
        self.fixed_dt = None

    def update(self):
        dt = self.fixed_dt or utime.dt
        self._t += dt
        t = self._t
        flick = 0.85 + 0.08 * math.sin(t * 13.0) + 0.05 * math.sin(t * 31.0 + 1.3) + 0.04 * math.sin(t * 7.3)
        if random.random() < dt * 0.6:
            flick *= 0.7                                    # редкие провалы, как от сквозняка
        self.flame.scale = (0.035 * (0.9 + 0.2 * flick), 0.07 * flick)
        self.flame.x = math.sin(t * 5.0) * 0.003
        self.halo.color = Vec4(1.0, 0.6, 0.25, 0.18 * flick)
        wp = Vec3(*self.flame.world_position)
        NodePath.set_shader_input(scene, 'lamp_pos', wp)
        NodePath.set_shader_input(scene, 'lamp_power', self.power * flick)


class Atmosphere(Entity):
    """Пыль, плавающая в свете, и полосы низового тумана."""

    def __init__(self, center=(0, 0, 0), radius=5.0, motes=90, fog_puffs=26, **kwargs):
        super().__init__(position=center, **kwargs)
        self.radius = radius
        self.motes = []
        for _ in range(motes):
            e = Entity(parent=self, model='quad', texture='radial_gradient', billboard=True, shader=unlit_shader,
                       position=(random.uniform(-radius, radius) * 0.5, random.uniform(0.2, 2.6), random.uniform(-radius, radius) * 0.5),
                       scale=random.uniform(0.008, 0.02), color=Vec4(1.0, 0.92, 0.8, random.uniform(0.15, 0.5)))
            e.setTransparency(TransparencyAttrib.M_alpha)
            e.set_depth_write(False)
            e.seed = random.uniform(0, 100)
            self.motes.append(e)
        self.fog = []
        for _ in range(fog_puffs):
            a = random.uniform(0, 2 * math.pi)
            r = random.uniform(0.5, radius)
            e = Entity(parent=self, model='quad', texture='radial_gradient', billboard=True, shader=unlit_shader,
                       position=(math.cos(a) * r, random.uniform(0.1, 0.45), math.sin(a) * r),
                       scale=(random.uniform(2.5, 5.0), random.uniform(0.5, 0.9)), color=Vec4(0.7, 0.72, 0.75, random.uniform(0.05, 0.12)))
            e.setTransparency(TransparencyAttrib.M_alpha)
            e.set_depth_write(False)
            e.seed = random.uniform(0, 100)
            self.fog.append(e)
        self._t = 0.0
        self.fixed_dt = None

    def update(self):
        dt = self.fixed_dt or utime.dt
        self._t += dt
        t = self._t
        for e in self.motes:
            s = e.seed
            e.position += Vec3(math.sin(t * 0.3 + s) * 0.02, math.sin(t * 0.21 + s * 2) * 0.012 - 0.002, math.cos(t * 0.27 + s) * 0.02) * dt * 4
            if e.y < 0.1:
                e.y = 2.6
        for e in self.fog:
            e.x += math.sin(t * 0.05 + e.seed) * dt * 0.08


def _mesh(md):
    from ursina import Mesh
    return Mesh(**md.to_ursina_args())
