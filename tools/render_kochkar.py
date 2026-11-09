"""
Рендер листов Кочкаря в docs/kochkar/.

    python tools/render_kochkar.py
    (на сервере без экрана: xvfb-run -s "-screen 0 1920x1080x24" python tools/render_kochkar.py)
"""
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from panda3d.core import Filename, NodePath, PNMImage, Point3  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from ursina import Ursina, Vec3, application, camera, destroy  # noqa: E402

OUT = ROOT / 'docs' / 'kochkar'
OUT.mkdir(parents=True, exist_ok=True)
W, H = 640, 640

app = Ursina(size=(W, H), borderless=True, development_mode=False)
from monsters.kochkar import Kochkar  # noqa: E402
from taiga_demo import build_taiga  # noqa: E402

env = build_taiga(clear=12.0)
camera.fov = 40


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
    out = Image.new('RGB', (w, images[0].height + top + 48), (24, 28, 26))
    d = ImageDraw.Draw(out)
    d.text((pad, 16), title, fill=(232, 228, 214), font=font(28))
    x = pad
    for im, lab in zip(images, labels):
        out.paste(im, (x, top))
        tw = d.textlength(lab, font=font(22))
        d.text((x + im.width / 2 - tw / 2, top + im.height + 10), lab, fill=(215, 210, 196), font=font(22))
        x += im.width + pad
    out.save(path)
    print('saved', path)


if __name__ == '__main__':
    k = Kochkar()
    k.fixed_dt = 1 / 30
    steps(10)
    tgt = Vec3(0, 1.9, 0)
    imgs = []
    for yaw in (0, 90, 35, 180):
        place_cam(tgt, 9.0, yaw, 2.4)
        steps(2)
        imgs.append(grab())
    sheet(imgs, ['Спереди', 'Сбоку', '3/4', 'Сзади'], OUT / 'turnaround.png', 'Кочкарь — ходячая кочка (≈4 м с ёлкой)')

    # голова крупно
    head = Vec3(*k.p['head'].world_position) + Vec3(0, 0.0, 0.25)
    place_cam(head, 1.5, 30, head.y + 0.25)
    steps(2)
    a = grab()
    # спина: мох, брусника, ёлка, грибы
    place_cam(Vec3(0, 2.6, 0), 2.8, 60, 3.9)
    steps(2)
    b = grab()
    # гудит
    k.hum(10)
    place_cam(Vec3(0, 2.4, 0.5), 5.0, 25, 2.6)
    steps(60)
    c = grab()
    # идёт
    k.walk_to((0, 0, 6))
    steps(45)
    place_cam(Vec3(*k.world_position) + Vec3(0, 1.8, 0), 8.0, 70, 2.2)
    steps(1)
    d = grab()
    sheet([a, b, c, d], ['Голова: коряга и янтарь', 'Спина: мох, брусника, ёлка', 'Гудит: споры из мха', 'Идёт'],
          OUT / 'details.png', 'Детали')

    # ложится и становится кочкой
    k.stop()
    steps(30)
    frames = []
    pos = Vec3(*k.world_position)
    place_cam(pos + Vec3(0, 1.4, 0), 8.0, 40, 2.6)
    steps(2)
    frames.append(grab())
    k.rest()
    for n in (25, 30, 40, 90):
        steps(n)
        frames.append(grab())
    sheet([f.crop((80, 60, W - 80, H - 60)) for f in frames], ['Стоит', 'Опускается', 'Поджимает ноги', 'Прячет голову', 'Просто кочка'],
          OUT / 'rest.png', 'Ложится и становится кочкой')
    destroy(k)
    application.quit()
