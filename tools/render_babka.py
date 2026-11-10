"""
Кинокадры и GIF-трейлер Бабки в docs/babka/.

    python tools/render_babka.py            # shots.png + trailer.gif + hero.png
    (без экрана: xvfb-run -s "-screen 0 1920x1080x24" python tools/render_babka.py)
"""
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from panda3d.core import Filename, NodePath, PNMImage, Point3  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from ursina import Entity, Ursina, Vec3, application, camera, color, window  # noqa: E402

OUT = ROOT / 'docs' / 'babka'
OUT.mkdir(parents=True, exist_ok=True)
W, H = 940, 400                     # 2.35 : 1

app = Ursina(size=(W, H), borderless=True, development_mode=False)
from monsters.babka import Babka  # noqa: E402
from monsters.cinema import Atmosphere, FilmLook, KeroseneLamp  # noqa: E402
from monsters.frost_mimic import set_environment  # noqa: E402
from monsters.porch import build_porch  # noqa: E402
from panda3d.core import NodePath as NP  # noqa: E402
from ursina import scene  # noqa: E402
from taiga_demo import build_taiga  # noqa: E402

FOG = (0.06, 0.07, 0.095)
random.seed(3)
build_taiga(clear=10.0, winter=True)
build_porch(position=(0, 0, 0), icicles=True)
set_environment(light_dir=(0.5, 0.55, 0.55), light_color=(0.52, 0.60, 0.80), fog_color=FOG, fog_density=0.055)
NP.set_shader_input(scene, 'rim_dir', Vec3(-0.5, 0.6, -0.7))
NP.set_shader_input(scene, 'rim_color', Vec3(0.30, 0.36, 0.52))
window.color = color.rgb(*FOG)
lamp = KeroseneLamp(position=(0.62, 0.0, 0.42), power=5.0)
atmo = Atmosphere(center=(0, 0, 0.8), radius=5, motes=30, snowfall=650)
film = FilmLook(grade='cinema', letterbox=False, aperture=1.2)
camera.fov = 32

viewer = Entity(position=(0.3, 1.6, 30))
b = Babka(target=viewer, sitting=True)
b.detect_range = 0
STEP = 1 / 12
for o in (b, lamp, atmo, film):
    o.fixed_dt = STEP


def grab():
    img = PNMImage()
    application.base.win.getScreenshot(img)
    tmp = OUT / '_tmp.png'
    img.write(Filename(tmp.as_posix()))
    im = Image.open(tmp).convert('RGB')
    tmp.unlink()
    return im


def step(n=1):
    for _ in range(n):
        app.step()


def cam(pos, look, shake=0.0, t=0.0):
    p = Vec3(*pos) + Vec3(math.sin(t * 1.7) * 0.6 + math.sin(t * 3.1) * 0.3, math.sin(t * 2.3) * 0.5, 0) * shake * 0.02
    camera.position = p
    NodePath.lookAt(camera, Point3(*look), Vec3(0, 1, 0))


def hfwd():
    v = Vec3(*scene.getRelativeVector(b.p['head'], Vec3(0, 0, 1)))
    v.y = 0
    return v.normalized()


def head():
    return Vec3(*b.p['head'].world_position) + Vec3(0, 0.1, 0.05)


def font(size):
    p = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    return ImageFont.truetype(p, size) if Path(p).exists() else ImageFont.load_default()


def grid(images, labels, path, title, cols=2):
    pad, top = 16, 60
    rows = (len(images) + cols - 1) // cols
    w = cols * images[0].width + pad * (cols + 1)
    h = top + rows * (images[0].height + 40) + pad
    out = Image.new('RGB', (w, h), (8, 8, 9))
    d = ImageDraw.Draw(out)
    d.text((pad, 14), title, fill=(230, 222, 205), font=font(28))
    for i, (im, lab) in enumerate(zip(images, labels)):
        x = pad + (i % cols) * (im.width + pad)
        y = top + (i // cols) * (im.height + 40)
        out.paste(im, (x, y))
        d.text((x + 4, y + im.height + 6), lab, fill=(200, 190, 172), font=font(20))
    out.save(path)
    print('saved', path)


if __name__ == '__main__':
    viewer.position = Vec3(0.4, 1.6, 4.5)
    step(30)
    # главный кадр как на фото (сепия) — для сравнения с референсом
    film.grade = 0.0
    film.focus_on(b)
    cam(Vec3(2.2, 1.9, 7.8), Vec3(0.0, 1.0, 0.0))
    step(3)
    grab().save(OUT / 'hero.png')
    print('saved', OUT / 'hero.png')
    film.grade = 0.0
    frames = []
    t = 0.0

    def rec(n, pos_fn, look_fn, focus):
        global t
        film.focus_on(focus)
        for i in range(n):
            k = i / max(n - 1, 1)
            cam(pos_fn(k), look_fn(k), shake=1.0, t=t)
            step()
            t += STEP
            frames.append(grab().resize((480, 204), Image.LANCZOS))

    shots, labels = [], []
    # 1. общий план: наезд из темноты
    rec(30, lambda k: Vec3(2.6 - 1.6 * k, 2.0 - 0.5 * k, 10.0 - 4.0 * k), lambda k: Vec3(0, 1.0, 0), b)
    shots.append(frames[-1]); labels.append('1. Снежная ночь у избы')
    # 2. крупно: глаза поверх пальцев
    rec(26, lambda k: head() + Vec3(0.25 - 0.1 * k, 0.0, 1.05 - 0.25 * k), lambda k: head() - Vec3(0, 0.03, 0),
        b.p['eye_1'])
    shots.append(frames[-1]); labels.append('2. Глаза поверх пальцев (фокус на глазах)')
    # 3. руки
    rec(14, lambda k: head() + Vec3(-0.35 + 0.1 * k, -0.08, 0.5), lambda k: head() - Vec3(0, 0.08, -0.06),
        b.p['hand_R'])
    shots.append(frames[-1]); labels.append('3. Руки: суставы, ногти, вены')
    # 4. встаёт — нижний ракурс
    viewer.position = Vec3(0.4, 1.6, 6.0)
    b.detect_range = 9
    rec(34, lambda k: Vec3(1.1, 0.5, 3.6), lambda k: head() - Vec3(0, 0.25, 0), b.p['head'])
    shots.append(frames[-1]); labels.append('4. Заметила — встаёт (2.1 м)')
    # 5. хватает: рта нет
    viewer.position = Vec3(*b.world_position) + b.forward * 1.2 + Vec3(0, 1.6, 0)
    b._set('grab')
    rec(22, lambda k: head() + hfwd() * (1.25 - 0.3 * k) + Vec3(0.12, -0.42, 0), lambda k: head() - Vec3(0, 0.02, 0),
        b.p['head'])
    shots.append(frames[-1]); labels.append('5. Опускает руки — рта нет')
    # 6. фонарь
    b.flash()
    rec(16, lambda k: head() + hfwd() * 1.6 + Vec3(-0.3, -0.2, 0), lambda k: head() - Vec3(0, 0.1, 0), b.p['head'])
    shots.append(frames[-1]); labels.append('6. Свет фонаря — закрывает глаза')

    grid(shots, labels, OUT / 'shots.png', 'Бабка — кинокадры')
    frames[0].save(OUT / 'trailer.gif', save_all=True, append_images=frames[1::2], duration=int(STEP * 2000), loop=0,
                   optimize=True)
    print('saved', OUT / 'trailer.gif', len(frames[::2]), 'кадров')

    application.quit()
