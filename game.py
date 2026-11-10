"""
ТАЙГА. БАБКА — хоррор от первого лица.

Зимняя ночь. В лесу разбросаны детские варежки — собери все и уйди через калитку.
На крыльце избы сидит Бабка. Она слышит бег, видит свет фонаря и с каждой варежкой становится быстрее.

Запуск:   python game.py                    (качество: --quality low | medium | high, по умолчанию medium)
          python game.py --fullscreen

  W A S D   ходить            Shift   бежать (тратит силы, она слышит издалека)
  Ctrl      красться (тихо)   F       фонарь (садит батарею; луч в лицо ослепляет её на пару секунд)
  Esc       пауза             R       заново (после конца игры)
"""
import math
import random
import sys

from panda3d.core import ColorBlendAttrib, NodePath, TransparencyAttrib
from ursina import (Audio, Entity, Mesh, Text, Ursina, Vec3, Vec4, application, camera, color, held_keys, mouse, scene,
                    time, window)
from ursina.shaders import unlit_shader

QUALITY = dict(low=1.3, medium=2.2, high=3.9)
quality = next((sys.argv[i + 1] for i, a in enumerate(sys.argv[:-1]) if a == '--quality'), 'medium')
SELFTEST = '--selftest' in sys.argv or '--screens' in sys.argv

app = Ursina(title='Тайга. Бабка', fullscreen='--fullscreen' in sys.argv, development_mode=False)
FOG = (0.045, 0.055, 0.08)
window.color = color.rgb(*FOG)
loading = Text('Загрузка…', origin=(0, 0), scale=2, color=color.rgb(0.8, 0.8, 0.85))
app.step()
app.step()

from monsters import babka_mesh  # noqa: E402
babka_mesh.set_detail(QUALITY.get(quality, 2.2))
from monsters.babka import Babka  # noqa: E402
from monsters.babka_shaders import KID_MITTENS, cloth_shader  # noqa: E402
from monsters.cinema import Atmosphere, FilmLook, KeroseneLamp  # noqa: E402
from monsters.frost_mesh import loft  # noqa: E402
from monsters.frost_mimic import set_environment  # noqa: E402
from monsters.kochkar_mesh import merge, tube_path  # noqa: E402
from monsters.porch import build_porch  # noqa: E402
from monsters.sfx import ensure_sounds  # noqa: E402
from taiga_demo import _nature, build_taiga  # noqa: E402

ARENA = 30.0
CABIN = Vec3(0, 0, 16)
START = Vec3(0, 0, -22)
GATE = Vec3(0, 0, -25.5)
N_MITTENS = 6
EYE, EYE_CROUCH = 1.65, 1.05

# ------------------------------------------------------------------ мир
ensure_sounds()
world = build_taiga(seed=11, radius=ARENA + 4, clear=5.0, winter=True, crown_start=0.34)   # кроны выше головы
window.color = color.rgb(*FOG)
build_porch(position=CABIN, rotation_y=180, icicles=True)
set_environment(light_dir=(0.5, 0.55, -0.55), light_color=(0.40, 0.47, 0.66), fog_color=FOG, fog_density=0.075, snow=1.0)
NodePath.set_shader_input(scene, 'rim_dir', Vec3(-0.5, 0.6, 0.7))
NodePath.set_shader_input(scene, 'rim_color', Vec3(0.26, 0.32, 0.48))
KeroseneLamp(position=CABIN + Vec3(-0.62, 0, -0.42), power=5.0)
atmo = Atmosphere(center=START, radius=9, motes=0, fog_puffs=14, snowfall=700)
film = FilmLook(grade='cinema', letterbox=False, aperture=0.35)
film.focus = 7.0

# препятствия: деревья и камни (круги), изба и крыльцо (прямоугольники x0, x1, z0, z1)
CIRCLES = list(world.obstacles)


def free_spot(x, z, need=2.6):
    """Ближайшая к (x, z) точка, вокруг которой нет деревьев."""
    for r in [i * 0.5 for i in range(30)]:
        for k in range(16):
            a = k / 16 * 2 * math.pi
            px, pz = x + math.cos(a) * r, z + math.sin(a) * r
            if math.hypot(px, pz) < ARENA - 1 and all(math.hypot(px - ox, pz - oz) > rr + need for ox, oz, rr in CIRCLES):
                return Vec3(px, 0, pz)
    return Vec3(x, 0, z)


START = free_spot(START.x, START.z)
GATE = free_spot(START.x, START.z - 4.0, need=1.6)
BOXES = [(-3.5, 3.5, CABIN.z + 0.45, CABIN.z + 1.2), (-1.2, 1.2, CABIN.z - 0.05, CABIN.z + 0.8)]


def push_out(pos, radius, boxes=True):
    """Выталкивает точку из препятствий и не даёт уйти за край мира."""
    for ox, oz, r in CIRCLES:
        dx, dz = pos.x - ox, pos.z - oz
        d = math.hypot(dx, dz)
        if d < r + radius and d > 1e-4:
            k = (r + radius) / d
            pos.x, pos.z = ox + dx * k, oz + dz * k
    if boxes:
        for x0, x1, z0, z1 in BOXES:
            if x0 - radius < pos.x < x1 + radius and z0 - radius < pos.z < z1 + radius:
                pen = [(pos.x - (x0 - radius), 'x', x0 - radius), ((x1 + radius) - pos.x, 'x', x1 + radius),
                       (pos.z - (z0 - radius), 'z', z0 - radius), ((z1 + radius) - pos.z, 'z', z1 + radius)]
                _, axis, val = min(pen)
                setattr(pos, axis, val)
    d = math.hypot(pos.x, pos.z)
    if d > ARENA:
        pos.x, pos.z = pos.x / d * ARENA, pos.z / d * ARENA
    return pos


# калитка — выход
gate = Entity(position=GATE)
for sx in (-1, 1):
    _nature(tube_path([(sx * 0.9, -0.2, 0), (sx * 0.9, 1.1, 0), (sx * 0.9, 2.3, 0)], [0.09, 0.08, 0.07], seg=10), 'wood', gate)
_nature(tube_path([(-1.1, 2.2, 0), (0, 2.25, 0), (1.1, 2.2, 0)], [0.06, 0.07, 0.06], seg=10), 'wood', gate)
gate_glow = Entity(parent=gate, model='quad', texture='radial_gradient', billboard=True, y=1.3, scale=1.2, shader=unlit_shader,
                   color=Vec4(1.0, 0.7, 0.35, 0.25))
gate_glow.setTransparency(TransparencyAttrib.M_alpha)
gate_glow.set_depth_write(False)
gate_glow.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.M_add, ColorBlendAttrib.O_incoming_alpha, ColorBlendAttrib.O_one))


# варежки
def mitten_mesh():
    mitt = loft([(-0.155, 0.012, 0.008, 0, 0), (-0.14, 0.036, 0.018, 0, 0), (-0.09, 0.042, 0.021, 0, 0), (-0.04, 0.04, 0.02, 0, 0),
                 (-0.02, 0.042, 0.022, 0, 0), (0.0, 0.04, 0.02, 0, 0)], rings=14, seg=16, round_start=0.02)
    thumb = tube_path([(0.035, -0.05, 0.0), (0.05, -0.08, 0.0), (0.05, -0.105, 0.0)], [0.012, 0.011, 0.008], seg=8)
    return merge([mitt, thumb])


MITT = mitten_mesh()


class Mitten(Entity):
    def __init__(self, pos, tint):
        super().__init__(position=pos + Vec3(0, 0.42, 0))
        self.body = Entity(parent=self, model=Mesh(**MITT.to_ursina_args()), shader=cloth_shader, scale=1.5, double_sided=True)
        for k, v in dict(material=14, fray=0.0, wind=0.0, hem_band=0.0, cold_flush=0.0, snow_mask=0.0).items():
            self.body.set_shader_input(k, v)
        self.body.set_shader_input('tint', Vec3(*tint))
        self.body.set_shader_input('part_offset', Vec3(0, 0, 0))
        self.glow = Entity(parent=self, model='quad', texture='radial_gradient', billboard=True, scale=0.9, shader=unlit_shader,
                           color=Vec4(*tint, 0.3))
        self.glow.setTransparency(TransparencyAttrib.M_alpha)
        self.glow.set_depth_write(False)
        self.glow.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.M_add, ColorBlendAttrib.O_incoming_alpha, ColorBlendAttrib.O_one))
        self.seed = random.uniform(0, 10)
        self.tint = tint

    def tick(self, t):
        self.body.rotation_y = t * 40 + self.seed * 36
        self.body.y = math.sin(t * 1.6 + self.seed) * 0.05
        self.glow.color = Vec4(*self.tint, 0.22 + 0.1 * math.sin(t * 2.2 + self.seed))


def place_mittens():
    pts = []
    tries = 0
    while len(pts) < N_MITTENS and tries < 4000:
        tries += 1
        a, r = random.uniform(0, 2 * math.pi), random.uniform(8, ARENA - 3)
        p = Vec3(math.cos(a) * r, 0, math.sin(a) * r)
        if (p - CABIN).length() < 7 or (p - START).length() < 9:
            continue
        if any((p - q).length() < 8 for q in pts):
            continue
        if any(math.hypot(p.x - ox, p.z - oz) < rr + 0.8 for ox, oz, rr in CIRCLES):
            continue
        pts.append(p)
    return [Mitten(p, KID_MITTENS[i % len(KID_MITTENS)]) for i, p in enumerate(pts)]


# ------------------------------------------------------------------ игрок, Бабка, звук
player = Entity(position=START)
head = Entity(parent=player, y=EYE)
camera.parent = head
camera.position = Vec3(0, 0, 0)
camera.rotation = Vec3(0, 0, 0)
camera.fov = 78
babka = Babka(position=CABIN, rotation_y=180, target=head, sitting=True)
babka.lose_range = 17.0

snd = {n: Audio(n, autoplay=False, loop=n in ('wind', 'whisper')) for n in
       ('wind', 'whisper', 'heart', 'sting', 'pickup', 'caught', 'click', 'win', 'step0', 'step1', 'step2', 'step3')}

# ------------------------------------------------------------------ интерфейс
ui = camera.ui
hud_mittens = Text('', parent=ui, position=(-0.86, 0.46), scale=1.2, color=color.rgb(0.92, 0.88, 0.8))
hud_hint = Text('', parent=ui, origin=(0, 0), y=-0.30, scale=1.0, color=color.rgb(0.85, 0.87, 0.92))
subtitle = Text('', parent=ui, origin=(0, 0), y=-0.42, scale=1.3, color=color.rgb(0.95, 0.9, 0.8))
banner = Text('', parent=ui, origin=(0, 0), y=0.12, scale=2.6, color=color.rgb(0.9, 0.88, 0.82))
banner_sub = Text('', parent=ui, origin=(0, 0), y=-0.02, scale=1.1, color=color.rgb(0.75, 0.75, 0.78))


def bar(y, col):
    back = Entity(parent=ui, model='quad', color=color.rgba(0, 0, 0, 0.45), position=(-0.74, y), scale=(0.24, 0.012))
    fill = Entity(parent=ui, model='quad', color=col, position=(-0.86, y, -0.01), origin=(-0.5, 0), scale=(0.24, 0.008))
    return back, fill


stam_back, stam_fill = bar(-0.44, color.rgba(0.75, 0.8, 0.9, 0.85))
batt_back, batt_fill = bar(-0.465, color.rgba(1.0, 0.85, 0.45, 0.85))
dark = Entity(parent=ui, model='quad', color=color.rgba(0, 0, 0, 0), scale=(3, 2), z=0.5)

G = dict(mode='title', t=0.0, mittens=[], got=0, stamina=1.0, battery=1.0, flash=False, aim=0.0, flash_cd=0.0, sub_t=0.0,
         hint_t=0.0, step=0.0, bob=0.0, heart=0.0, fear=0.0, noise_cd=0.0, roam_cd=0.0, prev_state='sit', crouch=0.0,
         play_time=0.0)


def say(text):
    subtitle.text = f'«{text}»'
    G['sub_t'] = 3.2


def hint(text, sec=5.0):
    hud_hint.text = text
    G['hint_t'] = sec


def on_caught():
    G['mode'] = 'over'
    snd['caught'].play()
    banner.text = 'ОНА ТЕБЯ НАШЛА'
    banner.color = color.rgb(0.75, 0.12, 0.1)
    banner_sub.text = f'Варежек собрано: {G["got"]} из {N_MITTENS}.   R — заново'
    mouse.locked = False


babka.on_say = say
babka.on_catch = on_caught


def new_game():
    for m in G['mittens']:
        from ursina import destroy
        destroy(m)
    G.update(mittens=place_mittens(), got=0, stamina=1.0, battery=1.0, flash=False, aim=0.0, flash_cd=0.0, fear=0.0,
             prev_state='sit', play_time=0.0, mode='play')
    player.position = Vec3(*START)
    player.rotation_y = 0
    head.rotation_x = 0
    babka.reset(CABIN, 180, sitting=True)
    babka.chase_speed = 2.9
    banner.text = banner_sub.text = ''
    banner.color = color.rgb(0.9, 0.88, 0.82)
    gate_glow.color = Vec4(1.0, 0.7, 0.35, 0.25)
    hint('Найди детские варежки — они светятся в снегу. Потом вернись к калитке.', 8)
    mouse.locked = not SELFTEST


def title():
    G['mode'] = 'title'
    banner.text = 'ТАЙГА. БАБКА'
    banner_sub.text = ('Собери детские варежки и уйди через калитку.\n\n'
                       'WASD — ходить   Shift — бежать   Ctrl — красться   F — фонарь   Esc — пауза\n\n'
                       'Enter — начать')
    mouse.locked = False


def input(key):
    if G['mode'] == 'title' and key in ('enter', 'left mouse down', 'space'):
        new_game()
    elif G['mode'] in ('over', 'win') and key == 'r':
        new_game()
    elif key == 'escape':
        if G['mode'] == 'play':
            G['mode'] = 'pause'
            banner.text, banner_sub.text = 'ПАУЗА', 'Esc — продолжить     Q — выйти'
            mouse.locked = False
        elif G['mode'] == 'pause':
            G['mode'] = 'play'
            banner.text = banner_sub.text = ''
            mouse.locked = True
    elif key == 'q' and G['mode'] == 'pause':
        application.quit()
    elif key == 'f' and G['mode'] == 'play':
        if G['battery'] > 0:
            G['flash'] = not G['flash']
            snd['click'].play()
        else:
            hint('Батарея села.', 2)


def update_player(dt):
    if mouse.locked:
        player.rotation_y += mouse.velocity[0] * 110
        head.rotation_x = max(-80, min(80, head.rotation_x - mouse.velocity[1] * 110))
    move = player.forward * (held_keys['w'] - held_keys['s']) + player.right * (held_keys['d'] - held_keys['a'])
    moving = move.length() > 0.01
    crouch = bool(held_keys['left control'] or held_keys['control'])
    run = bool(held_keys['left shift'] or held_keys['shift']) and moving and not crouch and G['stamina'] > 0.02
    speed = 1.2 if crouch else 5.2 if run else 2.5
    if moving:
        player.position += move.normalized() * speed * dt
        push_out(player.position, 0.35)
        player.y = 0
    G['stamina'] = max(0.0, G['stamina'] - dt / 5.5) if run else min(1.0, G['stamina'] + dt / (7.0 if moving else 4.0))
    # приседание, покачивание головы, шаги
    G['crouch'] += ((1.0 if crouch else 0.0) - G['crouch']) * min(1, dt * 8)
    if moving:
        G['bob'] += dt * speed * 2.4
        G['step'] += dt * speed
        if G['step'] > (1.5 if run else 1.25):
            G['step'] = 0
            s = snd[f'step{random.randrange(4)}']
            s.volume = 0.15 if crouch else 0.75 if run else 0.4
            s.pitch = random.uniform(0.9, 1.1)
            s.play()
    amp = 0.012 if crouch else 0.05 if run else 0.028
    head.y = EYE + (EYE_CROUCH - EYE) * G['crouch'] + math.sin(G['bob']) * amp * (1 if moving else 0)
    camera.fov += ((84 if run else 78) - camera.fov) * min(1, dt * 5)
    return moving, run, crouch


def update_babka_senses(dt, moving, run, crouch):
    d = babka.world_position - player.world_position
    d.y = 0
    dist = d.length()
    # зрение: фонарь выдаёт издалека, крадущегося видно хуже
    babka.detect_range = (6.0 if crouch else 10.0) + (7.0 if G['flash'] else 0.0)
    # слух
    noise = 0.0 if not moving else 3.0 if crouch else 16.0 if run else 7.0
    G['noise_cd'] -= dt
    if noise > dist and G['noise_cd'] <= 0 and babka.state in ('sit', 'patrol', 'search'):
        babka.investigate(player.world_position)
        G['noise_cd'] = 2.0
    # бродит между оставшимися варежками, если ей нечего делать
    G['roam_cd'] -= dt
    if babka.state == 'patrol' and G['roam_cd'] <= 0:
        G['roam_cd'] = 9.0
        if not babka.waypoints or (babka.waypoints[babka._wp] - babka.world_position).length() < 1.0:
            left = [m.position for m in G['mittens']]
            random.shuffle(left)
            babka.waypoints = [Vec3(p.x, 0, p.z) for p in left[:3]] + [Vec3(CABIN.x, 0, CABIN.z - 3)]
            babka._wp = 0
    # не ходит сквозь деревья
    if babka.sit < 0.02:
        push_out(babka.position, 0.45, boxes=babka.state not in ('rise',))
        babka.y = 0
    # «заметила» — резкий звук
    st = babka.state
    if st != G['prev_state']:
        if st in ('notice', 'rise') or (st == 'chase' and G['prev_state'] == 'search'):
            snd['sting'].play()
        G['prev_state'] = st
    return dist


def update_flashlight(dt, dist):
    on = G['flash'] and G['battery'] > 0
    if on:
        G['battery'] = max(0.0, G['battery'] - dt / 55.0)
        if G['battery'] <= 0:
            G['flash'] = False
            hint('Батарея села.', 3)
    flick = 1.0 if G['battery'] > 0.15 else (0.55 + 0.45 * math.sin(G['t'] * 37) * math.sin(G['t'] * 11))
    NodePath.set_shader_input(scene, 'flash_pos', Vec3(*camera.world_position) + camera.right * 0.18 - camera.up * 0.15)
    NodePath.set_shader_input(scene, 'flash_dir', Vec3(*camera.forward))
    NodePath.set_shader_input(scene, 'flash_power', 1.15 * flick if on else 0.0)
    # луч в лицо — ослепляет
    G['flash_cd'] -= dt
    to = Vec3(*babka.p['head'].world_position) - Vec3(*camera.world_position)
    aimed = on and to.length() < 10 and to.normalized().dot(camera.forward) > 0.965 and babka.state not in ('sit', 'stunned', 'caught')
    G['aim'] = G['aim'] + dt if aimed else 0.0
    if G['aim'] > 0.45 and G['flash_cd'] <= 0:
        babka.flash()
        G['flash_cd'] = 6.0
        G['battery'] = max(0.0, G['battery'] - 0.10)


def update_pickups(dt):
    for m in list(G['mittens']):
        m.tick(G['t'])
        if (Vec3(m.x, 0, m.z) - player.position).length() < 1.2:
            from ursina import destroy
            G['mittens'].remove(m)
            destroy(m)
            G['got'] += 1
            snd['pickup'].play()
            babka.chase_speed = 2.9 + 0.24 * G['got']
            if G['got'] == 1:
                hint('Она услышала. Беги тихо: Ctrl — красться.', 5)
                babka.investigate(player.world_position)
            elif G['got'] == N_MITTENS:
                hint('Все варежки у тебя. К калитке — на юг, там свет!', 8)
                gate_glow.color = Vec4(1.0, 0.75, 0.4, 0.9)
                gate_glow.scale = 3.0
            else:
                babka.investigate(player.world_position)
    if G['got'] == N_MITTENS and (player.position - GATE).length() < 2.2:
        G['mode'] = 'win'
        snd['win'].play()
        mm, ss = divmod(int(G['play_time']), 60)
        banner.text = 'ТЫ УШЁЛ'
        banner_sub.text = f'Варежки вернутся домой.   Время: {mm}:{ss:02d}   R — ещё раз'
        mouse.locked = False


def update_mood(dt, dist):
    active = babka.state in ('chase', 'grab', 'notice', 'rise')
    target = max(0.0, 1 - dist / (15.0 if active else 7.0)) * (1.0 if active else 0.45)
    G['fear'] += (target - G['fear']) * min(1, dt * 2.5)
    film.fear = G['fear'] if G['mode'] == 'play' else (1.0 if G['mode'] == 'over' else 0.0)
    snd['whisper'].volume = max(0.0, 1 - dist / 12.0) * 0.8
    G['heart'] -= dt
    if G['fear'] > 0.12 and G['heart'] <= 0:
        snd['heart'].volume = min(1.0, 0.25 + G['fear'])
        snd['heart'].play()
        G['heart'] = 1.15 - 0.7 * G['fear']
    if G['fear'] > 0.5:                                    # дрожь камеры
        camera.rotation_z = math.sin(G['t'] * 31) * 0.5 * (G['fear'] - 0.5)
    else:
        camera.rotation_z = 0


def update():
    dt = min(time.dt, 1 / 15)
    G['t'] += dt
    atmo.position = Vec3(player.x, 0, player.z)
    hud_mittens.text = f'Варежки: {G["got"]} / {N_MITTENS}' if G['mode'] != 'title' else ''
    stam_fill.scale_x = 0.24 * G['stamina']
    batt_fill.scale_x = 0.24 * G['battery']
    for e in (stam_back, stam_fill, batt_back, batt_fill):
        e.enabled = G['mode'] in ('play', 'pause')
    dark.color = color.rgba(0, 0, 0, 0.55 if G['mode'] in ('title', 'pause', 'over', 'win') else 0.0)
    G['sub_t'] -= dt
    G['hint_t'] -= dt
    if G['sub_t'] <= 0:
        subtitle.text = ''
    if G['hint_t'] <= 0:
        hud_hint.text = ''
    babka.ignore = G['mode'] in ('title', 'pause')          # на паузе она замирает
    if G['mode'] != 'play':
        NodePath.set_shader_input(scene, 'flash_power', 0.0)
        if G['mode'] == 'over':
            film.fear = 1.0
        return
    G['play_time'] += dt
    moving, run, crouch = update_player(dt)
    dist = update_babka_senses(dt, moving, run, crouch)
    update_flashlight(dt, dist)
    update_pickups(dt)
    update_mood(dt, dist)


loading.enabled = False
snd['wind'].volume = 0.5
snd['wind'].play()
snd['whisper'].volume = 0.0
snd['whisper'].play()
title()

if '--screens' in sys.argv:
    # кадры для README: меню, варежка в луче фонаря, Бабка на крыльце, погоня
    from pathlib import Path
    from panda3d.core import Filename, PNMImage
    out = Path(__file__).resolve().parent / 'docs' / 'game'
    out.mkdir(parents=True, exist_ok=True)

    def shot(name, n=6):
        for _ in range(n):
            app.step()
        img = PNMImage()
        application.base.win.getScreenshot(img)
        img.write(Filename((out / name).as_posix()))
        print('saved', out / name)

    def look_from(pos, at):
        player.position = free_spot(pos[0], pos[2], need=1.2)
        pos = player.position
        d = Vec3(*at) - Vec3(pos[0], head.y, pos[2])
        player.rotation_y = math.degrees(math.atan2(d.x, d.z))
        head.rotation_x = -math.degrees(math.atan2(d.y, math.hypot(d.x, d.z)))

    shot('1_title.png')
    input('enter')
    input('f')
    m = G['mittens'][0]
    look_from(m.position + Vec3(1.2, 0, -2.6), m.position + Vec3(0, 0.4, 0))
    babka.detect_range = 0
    shot('2_mitten.png')
    look_from(CABIN + Vec3(1.5, 0, -6.5), CABIN + Vec3(0, 1.2, 0))
    shot('3_porch.png')
    babka.alert()
    for _ in range(90):
        app.step()
    look_from(babka.world_position + babka.forward * 3.2, babka.world_position + Vec3(0, 1.9, 0))
    G['fear'] = 0.8
    shot('4_chase.png', 2)
elif SELFTEST:
    # автопрогон: старт, сбор всех варежек, победа; потом рестарт и поимка
    input('enter')
    assert G['mode'] == 'play' and len(G['mittens']) == N_MITTENS, 'варежки не расставлены'
    babka_states = set()
    for target_i in range(N_MITTENS):
        tgt = G['mittens'][0].position
        for _ in range(400):
            to = Vec3(tgt.x, 0, tgt.z) - player.position
            if G['got'] > target_i:
                break
            player.position += to.normalized() * min(0.6, to.length())
            babka.position = Vec3(*CABIN) if babka.sit > 0.5 else babka.position      # в тесте она не мешает
            babka.chase_speed = 0.0
            app.step()
            babka_states.add(babka.state)
            if G['mode'] != 'play':
                break
    assert G['got'] == N_MITTENS, f'собрано {G["got"]}'
    for _ in range(200):
        to = GATE - player.position
        player.position += to.normalized() * min(0.6, to.length())
        app.step()
        if G['mode'] == 'win':
            break
    assert G['mode'] == 'win', G['mode']
    input('r')
    assert G['mode'] == 'play' and G['got'] == 0 and babka.state == 'sit'
    input('f')
    for _ in range(300):                                   # идём прямо к ней — должна поймать
        to = babka.world_position - player.position
        player.position += Vec3(to.x, 0, to.z).normalized() * min(0.4, max(to.length() - 1.0, 0))
        app.step()
        if G['mode'] == 'over':
            break
    assert G['mode'] == 'over', G['mode']
    input('r')
    input('escape')
    assert G['mode'] == 'pause'
    input('escape')
    print('SELFTEST OK: победа, поражение, рестарт, пауза; состояния Бабки:', sorted(babka_states))
else:
    app.run()
