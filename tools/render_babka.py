"""
Рендер листов Бабки в docs/babka/.

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
W, H = 600, 720

app = Ursina(size=(W, H), borderless=True, development_mode=False)
from monsters.babka import Babka  # noqa: E402
from monsters.frost_mimic import set_environment  # noqa: E402
from taiga_demo import build_taiga  # noqa: E402

DUSK_FOG = (0.13, 0.15, 0.21)
build_taiga(clear=12.0)
set_environment(light_dir=(0.35, 0.55, 0.75), light_color=(0.95, 0.90, 0.95), fog_color=DUSK_FOG, fog_density=0.045)
window.color = color.rgb(*DUSK_FOG)
camera.fov = 38


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
    out = Image.new('RGB', (w, images[0].height + top + 48), (20, 20, 24))
    d = ImageDraw.Draw(out)
    d.text((pad, 16), title, fill=(232, 226, 214), font=font(28))
    x = pad
    for im, lab in zip(images, labels):
        out.paste(im, (x, top))
        tw = d.textlength(lab, font=font(22))
        d.text((x + im.width / 2 - tw / 2, top + im.height + 10), lab, fill=(215, 208, 196), font=font(22))
        x += im.width + pad
    out.save(path)
    print('saved', path)


if __name__ == '__main__':
    victim = Entity(position=(0, 1.6, 40))
    b = Babka(target=victim)
    b.fixed_dt = 1 / 30
    b.detect_range = 0
    steps(10)
    imgs = []
    for yaw in (0, 90, 35, 180):
        place_cam(Vec3(0, 1.15, 0), 5.2, yaw, 1.5)
        steps(2)
        imgs.append(grab())
    sheet(imgs, ['Спереди', 'Сбоку', '3/4', 'Сзади'], OUT / 'turnaround.png', 'Бабка — патруль (сгорблена, 1.9 м)')

    # состояния
    victim.position = Vec3(0, 1.6, 4)
    shots = []
    place_cam(Vec3(0, 1.5, 0), 6.0, 30, 1.7)
    steps(2)
    shots.append(grab())
    b.alert()
    steps(70)
    shots.append(grab())
    b._set('chase')
    victim.position = Vec3(0, 1.6, 30)
    steps(25)
    place_cam(Vec3(*b.world_position) + Vec3(0, 1.4, 0), 6.0, 30, 1.8)
    steps(1)
    shots.append(grab())
    victim.position = Vec3(*b.world_position) + b.forward * 1.2 + Vec3(0, 1.6, 0)
    b._set('grab')
    steps(12)
    place_cam(Vec3(*b.world_position) + Vec3(0, 1.5, 0), 5.0, 50, 1.9)
    steps(1)
    shots.append(grab())
    b.flash()
    steps(20)
    shots.append(grab())
    sheet(shots, ['Шаркает', 'Заметила: шея вытянулась', 'Погоня', 'Хватает', 'Фонарь: слепнет'],
          OUT / 'states.png', 'Поведение')

    # лицо крупно (заметила)
    destroy(b)
    b = Babka(target=Entity(position=(0, 2.4, 5)))
    b.fixed_dt = 1 / 30
    b.alert()
    steps(48)
    head = Vec3(*b.p['head'].world_position) + Vec3(0, 0.1, 0)
    place_cam(head, 0.75, 15, head.y + 0.03)
    steps(2)
    a = grab()
    place_cam(Vec3(*b.world_position) + Vec3(0, 0.75, 0), 2.2, 35, 1.2)
    steps(2)
    c = grab()
    sheet([a, c], ['Лицо: очки, улыбка, золотой зуб', 'Авоська, вязание, валенки'], OUT / 'details.png', 'Детали')
    application.quit()
