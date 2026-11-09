"""
Рендер листов «Ледяного двойника» в PNG (как референс: спереди/сбоку/3-4/сзади),
кадры превращения и крупный план лица.

    python tools/render_frost_mimic.py            # всё в docs/frost_mimic/
    python tools/render_frost_mimic.py turnaround

На сервере без экрана: xvfb-run -s "-screen 0 1920x1080x24" python tools/render_frost_mimic.py
"""
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw, ImageFont, ImageOps
from panda3d.core import Filename, NodePath, PNMImage, Point3
from ursina import Ursina, Vec3, camera, color, destroy, window, application

OUT = ROOT / 'docs' / 'frost_mimic'
OUT.mkdir(parents=True, exist_ok=True)
FLIP = False  # включить, если ваш драйвер отдаёт кадр вверх ногами
W, H = 540, 720

app = Ursina(size=(W, H), borderless=True, development_mode=False)
window.color = color.rgb32(14, 18, 26)

from monsters.frost_mimic import FrostMimic, make_human  # noqa: E402
from frost_mimic_demo import build_environment            # noqa: E402

FOG = (0.055, 0.07, 0.10)
env = build_environment(fog_color=FOG, simple=True)
camera.fov = 32


def grab(path=None):
    img = PNMImage()
    application.base.win.getScreenshot(img)
    tmp = OUT / '_tmp.png'
    img.write(Filename(tmp.as_posix()))
    im = Image.open(tmp).convert('RGB')
    if FLIP:
        im = ImageOps.flip(im)
    tmp.unlink()
    if path:
        im.save(path)
    return im


def steps(n, mimic=None):
    for _ in range(n):
        app.step()


def place_cam(target, dist, yaw_deg, height):
    a = math.radians(yaw_deg)
    camera.position = Vec3(target.x + math.sin(a) * dist, height, target.z + math.cos(a) * dist)
    NodePath.lookAt(camera, Point3(*target), Vec3(0, 1, 0))


def font(size):
    for p in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', '/usr/share/fonts/TTF/DejaVuSans.ttf'):
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def sheet(images, labels, path, title=None):
    pad = 24
    top = 70 if title else 30
    w = sum(i.width for i in images) + pad * (len(images) + 1)
    h = images[0].height + top + 50
    out = Image.new('RGB', (w, h), (14, 18, 26))
    d = ImageDraw.Draw(out)
    if title:
        d.text((pad, 18), title, fill=(220, 230, 240), font=font(28))
    x = pad
    for im, lab in zip(images, labels):
        out.paste(im, (x, top))
        tw = d.textlength(lab, font=font(22))
        d.text((x + im.width / 2 - tw / 2, top + im.height + 12), lab, fill=(200, 212, 225), font=font(22))
        x += im.width + pad
    out.save(path)
    print('saved', path)


def turnaround():
    m = FrostMimic(form='true', mirror=True)
    m.fixed_dt = 1 / 30
    m.set_environment(fog_color=FOG, fog_density=0.02)
    observer = make_human(position=(0.3, 0, 3.2), rotation_y=180,
                          palette=dict(coat=(0.18, 0.28, 0.22), hair=(0.35, 0.22, 0.12)))
    observer.enabled = False
    m.mirror_target = camera
    target = Vec3(0, 1.4, 0)
    imgs = []
    for yaw in (0, 90, 35, 180):
        place_cam(target, 5.6, yaw, 1.5)
        steps(4)
        imgs.append(grab())
    sheet(imgs, ['Front', 'Side', '3/4', 'Back'], OUT / 'turnaround.png', 'Ледяной двойник — истинный облик (2.8 м)')
    return m, observer


def closeups(m, observer):
    m.enable()
    observer.enabled = True
    m.look_target = None
    m.mirror_target = observer.parts['head']
    # лицо-зеркало: смотрит на наблюдателя
    place_cam(Vec3(0, 2.6, 0), 1.25, 20, 2.62)
    camera.fov = 30
    steps(40)
    face = grab()
    # трещина на горле во время речи
    m.speak(6)
    place_cam(Vec3(0, 2.36, 0.02), 0.7, 25, 2.42)
    steps(14)
    throat = grab()
    # торс крупно: снег внутри
    place_cam(Vec3(0, 1.85, 0), 1.6, 15, 1.95)
    steps(3)
    torso = grab()
    # спина: пролом
    place_cam(Vec3(0, 1.85, 0), 1.6, 180, 1.95)
    steps(3)
    back = grab()
    sheet([face, throat, torso, back], ['Лицо-зеркало', 'Голос из трещины', 'Пустота и снег', 'Пролом на спине'],
          OUT / 'details.png', 'Детали')
    destroy(m)
    destroy(observer)
    camera.fov = 32


def transform():
    m = FrostMimic(form='mask', mirror=True, x=0)
    m.fixed_dt = 1 / 30
    m.set_environment(fog_color=FOG, fog_density=0.02)
    target = Vec3(0, 1.35, 0)
    place_cam(target, 4.6, 20, 1.5)
    steps(3)
    frames = [grab()]
    m.reveal()
    marks = [0.9, 1.7, 2.25, 2.6, 3.0, 4.0]
    t = 0.0
    for mk in marks:
        while t < mk:
            app.step()
            t += 1 / 30
        frames.append(grab())
    labels = ['Маска', 'Иней', 'Трещины', 'Пустота', 'Осыпается', 'Вытягивается', 'Истинный облик']
    small = [f.crop((60, 0, W - 60, H)) for f in frames]
    sheet(small, labels, OUT / 'transformation.png', 'Переход из маски в истинную форму')
    # крупно: губы маски опаздывают за голосом, на горле вспыхивает трещинка
    m2 = FrostMimic(form='mask', mirror=False, x=0)
    m2.fixed_dt = 1 / 30
    destroy(m)
    m2.speak(5)
    place_cam(Vec3(0, 1.62, 0), 0.75, 15, 1.66)
    steps(20)
    a = grab()
    place_cam(Vec3(0, 1.3, 0), 3.2, 30, 1.5)
    steps(2)
    b = grab()
    sheet([b, a], ['Маска (человек 1.8 м)', 'Говорит: губы невпопад, трещинка на горле'], OUT / 'mask.png', 'Маска')
    destroy(m2)


def frost():
    m = FrostMimic(form='true', mirror=False)
    m.fixed_dt = 1 / 10
    m.set_environment(fog_color=FOG, fog_density=0.02)
    place_cam(Vec3(0, 0.6, 0), 5.5, 30, 3.6)
    steps(40)
    grab(OUT / 'frost_ground.png')
    print('saved frost_ground')
    destroy(m)


if __name__ == '__main__':
    what = sys.argv[1:] or ['turnaround', 'details', 'transform', 'frost']
    m = obs = None
    if 'turnaround' in what or 'details' in what:
        m, obs = turnaround()
    if 'details' in what:
        closeups(m, obs)
    elif m is not None:
        destroy(m)
        destroy(obs)
    if 'transform' in what:
        transform()
    if 'frost' in what:
        frost()
    application.quit()
