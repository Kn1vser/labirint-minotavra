"""
Лист модели Бабки: она одна на снегу, при хорошем свете — чтобы читались цвета и снег на ней.

    python tools/render_babka_model.py      # docs/babka/model.png
"""
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from panda3d.core import Filename, NodePath, PNMImage, Point3  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from ursina import Entity, Ursina, Vec3, application, camera, color, scene, window  # noqa: E402

OUT = ROOT / 'docs' / 'babka'
W, H = 520, 760
app = Ursina(size=(W, H), borderless=True, development_mode=False)

from monsters.babka import Babka  # noqa: E402
from monsters.cinema import Atmosphere, FilmLook, KeroseneLamp  # noqa: E402
from monsters.frost_mimic import set_environment  # noqa: E402
from taiga_demo import build_taiga  # noqa: E402

FOG = (0.20, 0.23, 0.30)
build_taiga(clear=14.0, winter=True)
set_environment(light_dir=(0.45, 0.6, 0.65), light_color=(0.85, 0.90, 1.05), fog_color=FOG, fog_density=0.035, snow=1.0)
NodePath.set_shader_input(scene, 'rim_dir', Vec3(-0.5, 0.5, -0.8))
NodePath.set_shader_input(scene, 'rim_color', Vec3(0.45, 0.55, 0.8))
window.color = color.rgb(*FOG)
lamp = KeroseneLamp(position=(0.55, 0.0, 0.55), power=2.5)
atmo = Atmosphere(center=(0, 0, 0), radius=4, motes=0, fog_puffs=10, snowfall=250)
film = FilmLook(grade='cinema', letterbox=False, aperture=0.35)
camera.fov = 30
STEP = 1 / 30

b = Babka(target=Entity(position=(0, 1.6, 40)), sitting=False)
b.detect_range = 0
for o in (b, lamp, atmo, film):
    o.fixed_dt = STEP
film.focus_on(b.p['head'])


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


def cam(target, dist, yaw, height):
    a = math.radians(yaw)
    camera.position = Vec3(target.x + math.sin(a) * dist, height, target.z + math.cos(a) * dist)
    NodePath.lookAt(camera, Point3(*target), Vec3(0, 1, 0))


def font(size):
    p = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    return ImageFont.truetype(p, size) if Path(p).exists() else ImageFont.load_default()


if __name__ == '__main__':
    step(40)
    imgs, labels = [], []
    for yaw, lab in ((0, 'Спереди'), (35, '3/4'), (90, 'Сбоку'), (180, 'Сзади')):
        cam(Vec3(0, 1.05, 0), 5.0, yaw, 1.35)
        step(2)
        imgs.append(grab())
        labels.append(lab)
    hp = Vec3(*b.p['head'].world_position) + Vec3(0, 0.1, 0.05)
    film.aperture = 0.0
    cam(hp, 0.85, 18, hp.y + 0.03)
    step(2)
    imgs.append(grab())
    labels.append('Лицо: иней, ледяные глаза')
    cam(hp - Vec3(0, 0.05, 0), 0.6, -30, hp.y - 0.02)
    step(2)
    imgs.append(grab())
    labels.append('Руки: красные от мороза')

    pad, top, cols = 16, 60, 6
    out = Image.new('RGB', (cols * W + (cols + 1) * pad, H + top + 46), (10, 11, 14))
    d = ImageDraw.Draw(out)
    d.text((pad, 14), 'Бабка — снежная модель', fill=(235, 230, 220), font=font(30))
    for i, (im, lab) in enumerate(zip(imgs, labels)):
        x = pad + i * (W + pad)
        out.paste(im, (x, top))
        tw = d.textlength(lab, font=font(22))
        d.text((x + W / 2 - tw / 2, top + H + 10), lab, fill=(210, 205, 195), font=font(22))
    out = out.resize((out.width * 2 // 3, out.height * 2 // 3), Image.LANCZOS)
    out.save(OUT / 'model.png')
    print('saved', OUT / 'model.png')
    application.quit()
