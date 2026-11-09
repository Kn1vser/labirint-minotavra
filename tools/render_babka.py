"""
Рендер листов Бабки в docs/babka/ (по фото-референсу: сепия, крыльцо).

    python tools/render_babka.py
    (без экрана: xvfb-run -s "-screen 0 1920x1080x24" python tools/render_babka.py)
"""
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from panda3d.core import Filename, NodePath, PNMImage, Point3  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from ursina import Entity, Ursina, Vec3, application, camera, color, destroy, window  # noqa: E402

OUT = ROOT / 'docs' / 'babka'
OUT.mkdir(parents=True, exist_ok=True)
W, H = 560, 760

app = Ursina(size=(W, H), borderless=True, development_mode=False)
from monsters.babka import Babka  # noqa: E402
from monsters.babka_shaders import sepia_shader  # noqa: E402
from monsters.frost_mimic import set_environment  # noqa: E402
from monsters.porch import build_porch  # noqa: E402
from taiga_demo import build_taiga  # noqa: E402

FOG = (0.10, 0.10, 0.11)
build_taiga(clear=10.0)
build_porch(position=(0, 0, 0))
set_environment(light_dir=(0.45, 0.65, 0.6), light_color=(0.95, 0.92, 0.85), fog_color=FOG, fog_density=0.05)
window.color = color.rgb(*FOG)
camera.fov = 36


def grab():
    img = PNMImage()
    application.base.win.getScreenshot(img)
    tmp = OUT / '_tmp.png'
    img.write(Filename(tmp.as_posix()))
    im = Image.open(tmp).convert('RGB')
    tmp.unlink()
    return im


def steps(n):
    for _ in range(n):
        app.step()


def place_cam(target, dist, yaw, height):
    a = math.radians(yaw)
    camera.position = Vec3(target.x + math.sin(a) * dist, height, target.z + math.cos(a) * dist)
    NodePath.lookAt(camera, Point3(*target), Vec3(0, 1, 0))


def font(size):
    p = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    return ImageFont.truetype(p, size) if Path(p).exists() else ImageFont.load_default()


def sheet(images, labels, path, title):
    pad, top = 20, 64
    w = sum(i.width for i in images) + pad * (len(images) + 1)
    out = Image.new('RGB', (w, images[0].height + top + 48), (22, 20, 18))
    d = ImageDraw.Draw(out)
    d.text((pad, 16), title, fill=(232, 222, 204), font=font(28))
    x = pad
    for im, lab in zip(images, labels):
        out.paste(im, (x, top))
        tw = d.textlength(lab, font=font(22))
        d.text((x + im.width / 2 - tw / 2, top + im.height + 10), lab, fill=(215, 204, 186), font=font(22))
        x += im.width + pad
    out.save(path)
    print('saved', path)


def sepia(on):
    if on:
        camera.shader = sepia_shader
        camera.set_shader_input('strength', 1.0)
        camera.set_shader_input('time', 0.0)
    else:
        camera.set_shader_input('strength', 0.0)


if __name__ == '__main__':
    viewer = Entity(position=(0.4, 1.6, 30))
    b = Babka(target=viewer, sitting=True)
    b.fixed_dt = 1 / 30
    b.detect_range = 0
    viewer.position = Vec3(0.5, 1.6, 4)
    steps(40)

    # главный кадр, как на фото
    sepia(True)
    place_cam(Vec3(0.05, 1.05, 0.2), 3.3, 8, 1.25)
    steps(2)
    hero = grab()
    sepia(False)
    steps(1)
    hero_c = grab()
    place_cam(Vec3(0.0, 1.32, 0.15), 1.0, 10, 1.42)
    sepia(True)
    steps(2)
    face = grab()
    sheet([hero, hero_c, face], ['Как на фото', 'В цвете', 'Лицо'], OUT / 'hero.png', 'Бабка — сидит на крыльце')

    # поведение
    shots = []
    sepia(True)
    place_cam(Vec3(0, 1.1, 1.0), 5.2, 25, 1.5)
    steps(2)
    shots.append(grab())
    b.alert()
    steps(40)
    shots.append(grab())
    steps(50)
    shots.append(grab())
    b.state = 'chase'
    viewer.position = Vec3(*b.world_position) + b.forward * 1.3 + Vec3(0, 1.6, 0)
    b._set('grab')
    steps(14)
    place_cam(Vec3(*b.world_position) + Vec3(0, 1.4, 0), 3.4, 30, 1.7)
    steps(1)
    shots.append(grab())
    b.flash()
    steps(25)
    shots.append(grab())
    sheet(shots, ['Сидит', 'Встаёт', 'Встала (2.1 м)', 'Хватает: рта нет', 'Фонарь: закрывает глаза'],
          OUT / 'states.png', 'Поведение')

    # стоя, виды
    destroy(b)
    b2 = Babka(target=None, sitting=False, x=0, z=4)
    b2.fixed_dt = 1 / 30
    steps(10)
    imgs = []
    for yaw in (0, 90, 35, 180):
        place_cam(Vec3(0, 1.1, 4), 4.8, yaw, 1.4)
        steps(2)
        imgs.append(grab())
    sheet(imgs, ['Спереди', 'Сбоку', '3/4', 'Сзади'], OUT / 'turnaround.png', 'Бабка — бродит, закрыв рот ладонями')
    application.quit()
