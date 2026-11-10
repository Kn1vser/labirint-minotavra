"""
Статичная модель Бабки со всех сторон: 8 видов по кругу + крупные планы. Без анимации.

    python tools/render_babka_turnaround.py     # docs/babka/turnaround.png, docs/babka/closeups.png
"""
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from panda3d.core import Filename, NodePath, PNMImage, Point3  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from ursina import Ursina, Vec3, application, camera, color, scene, window  # noqa: E402

OUT = ROOT / 'docs' / 'babka'
W, H = 500, 800
app = Ursina(size=(W, H), borderless=True, development_mode=False)

from monsters.babka import Babka  # noqa: E402
from monsters.cinema import FilmLook, KeroseneLamp  # noqa: E402
from monsters.frost_mimic import set_environment  # noqa: E402
from taiga_demo import build_taiga  # noqa: E402

FOG = (0.07, 0.085, 0.12)
build_taiga(clear=14.0, winter=True)
set_environment(light_dir=(0.35, 0.5, 0.8), light_color=(0.85, 0.92, 1.1), fog_color=FOG, fog_density=0.05, snow=1.0)
NodePath.set_shader_input(scene, 'rim_dir', Vec3(-0.5, 0.5, -0.8))
NodePath.set_shader_input(scene, 'rim_color', Vec3(0.55, 0.68, 1.0))
window.color = color.rgb(*FOG)
lamp = KeroseneLamp(position=(0.5, 0.0, 0.85), power=1.6)
film = FilmLook(grade='cinema', letterbox=False, aperture=0.0)
camera.fov = 30

b = Babka(target=None, sitting=False, scale=1.12)       # 2.4 м
# статичная поза: никакого «мозга» и жизни, только заданные значения
b._brain = lambda dt: None
b._life = lambda dt: None
b.state = 'caught'
b.unfold, b.reach, b.cover, b.eyes = 1.0, 0.55, 0.0, 0.0
b._tilt, b._yaw_head, b._pitch_head, b._lunge, b._speed = 24.0, 8.0, 6.0, 0.7, 0.0
for o in (b, lamp, film):
    o.fixed_dt = 1e-6


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


def grid(imgs, labels, path, title, cols):
    pad, top = 14, 58
    rows = (len(imgs) + cols - 1) // cols
    out = Image.new('RGB', (cols * W + (cols + 1) * pad, top + rows * (H + 40) + pad), (8, 9, 12))
    d = ImageDraw.Draw(out)
    d.text((pad, 12), title, fill=(235, 230, 220), font=font(30))
    for i, (im, lab) in enumerate(zip(imgs, labels)):
        x = pad + (i % cols) * (W + pad)
        y = top + (i // cols) * (H + 40)
        out.paste(im, (x, y))
        tw = d.textlength(lab, font=font(20))
        d.text((x + W / 2 - tw / 2, y + H + 8), lab, fill=(205, 200, 190), font=font(20))
    out = out.resize((out.width * 3 // 4, out.height * 3 // 4), Image.LANCZOS)
    out.save(path)
    print('saved', path)


if __name__ == '__main__':
    step(6)
    imgs, labels = [], []
    names = ['Спереди', '45°', 'Справа', '135°', 'Сзади', '225°', 'Слева', '315°']
    for i in range(8):
        cam(Vec3(0, 1.3, 0.1), 5.0, i * 45, 1.5)
        step(2)
        imgs.append(grab())
        labels.append(names[i])
    grid(imgs, labels, OUT / 'turnaround.png', 'Бабка — модель со всех сторон (2.4 м)', 4)

    hp = Vec3(*b.p['head'].world_position) + Vec3(0, 0.11, 0.0)
    fwd = Vec3(*scene.getRelativeVector(b.p['head'], Vec3(0, 0, 1)))
    fwd.y = 0
    fwd = fwd.normalized()
    right = Vec3(fwd.z, 0, -fwd.x)
    imgs, labels = [], []
    for ang, dist, dy, lab in ((0, 0.62, 0.0, 'Лицо'), (38, 0.62, 0.0, 'Лицо 3/4'), (-38, 0.62, -0.12, 'Снизу')):
        a = math.radians(ang)
        camera.position = hp + (fwd * math.cos(a) + right * math.sin(a)) * dist + Vec3(0, dy, 0)
        NodePath.lookAt(camera, Point3(*(hp - Vec3(0, 0.03, 0))), Vec3(0, 1, 0))
        step(2)
        imgs.append(grab())
        labels.append(lab)
    hand = Vec3(*b.p['hand_aim_R'].world_position)
    cam(hand - Vec3(0, 0.1, 0), 0.7, 60, hand.y + 0.05)
    step(2)
    imgs.append(grab())
    labels.append('Рука: обмороженные пальцы')
    sash = Vec3(*b.p['sash'].world_position)
    cam(sash + Vec3(-0.08, -0.15, 0.1), 1.1, -25, sash.y - 0.05)
    step(2)
    imgs.append(grab())
    labels.append('Детские варежки на кушаке')
    cam(Vec3(0, 1.9, 0), 2.3, 180, 2.2)
    step(2)
    imgs.append(grab())
    labels.append('Спина: снег и сосульки')
    grid(imgs, labels, OUT / 'closeups.png', 'Бабка — крупные планы', 3)
    application.quit()
