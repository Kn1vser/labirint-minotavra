"""
Демо: «Ледяной двойник» в коридоре лабиринта.

Запуск:  python frost_mimic_demo.py

Управление:
  ПКМ + мышь  — вращать камеру,  колесо — приблизить
  R           — сбросить маску / снова надеть
  Пробел      — существо говорит (смотри на трещину на горле и на губы маски)
  G           — скользить к случайной точке (постоит — вокруг вырастет иней)
  C           — маска копирует внешность наблюдателя
  1 2 3 4     — вид спереди / сбоку / 3/4 / сзади
"""
import random
import sys

from ursina import (EditorCamera, Entity, Shader, Text, Ursina, Vec3, color,
                    window)

from monsters.frost_shaders import COMMON_UNIFORMS, LIT_VERTEX, NOISE

STONE_FRAG = '''#version 140
''' + NOISE + COMMON_UNIFORMS + '''
uniform float tile;
in vec3 v_obj; in vec3 v_local; in vec3 v_wpos; in vec3 v_wnrm; in vec2 v_uv;
out vec4 frag;
void main(){
    vec3 N = normalize(v_wnrm);
    vec3 p = v_wpos;
    // плоскость плитки зависит от ориентации грани
    vec2 q = abs(N.y) > 0.5 ? p.xz : (abs(N.x) > 0.5 ? p.zy : p.xy);
    q.x += step(1.0, mod(floor(q.y/tile), 2.0)) * tile*0.5;
    vec2 g = fract(q/tile);
    float seam = smoothstep(0.0, 0.03, min(min(g.x, 1.0-g.x), min(g.y, 1.0-g.y)));
    float n = fbm(vec3(q*2.0, 0.0));
    vec3 alb = mix(vec3(0.07,0.075,0.085), vec3(0.16,0.165,0.18), n) * mix(0.35, 1.0, seam);
    alb *= 0.85 + 0.3*hash13(vec3(floor(q/tile), 1.0));
    vec3 L = normalize(light_dir);
    float diff = clamp(dot(N, L)*0.5+0.5, 0.0, 1.0);
    vec3 V = normalize(cam_pos - p);
    float wet = pow(clamp(dot(N, normalize(L+V)), 0.0, 1.0), 40.0) * (0.3 + 0.7*n) * step(0.5, N.y);
    vec3 col = alb * (light_color*diff*0.9 + vec3(0.05,0.06,0.08)) + light_color*wet*0.25;
    frag = vec4(apply_fog(col, p), 1.0);
}
'''
stone_shader = Shader(name='stone', language=Shader.GLSL, vertex=LIT_VERTEX, fragment=STONE_FRAG)


def build_environment(fog_color=(0.02, 0.025, 0.04), fog_density=0.06, simple=False):
    """Пол и стены коридора. simple=True — только пол (для листов-рендеров)."""
    from monsters.frost_mimic import set_environment
    set_environment(fog_color=fog_color, fog_density=0.02 if simple else fog_density)
    root = Entity()
    root.set_shader_input('part_offset', Vec3(0, 0, 0))
    root.set_shader_input('tile', 0.9)
    Entity(parent=root, model='plane', scale=60, shader=stone_shader)
    if not simple:
        for side in (-1, 1):
            for i in range(-6, 7):
                Entity(parent=root, model='cube', shader=stone_shader, position=(side * 3.2, 2.2, i * 4),
                       scale=(1, 4.4, 4))
        for i, (x, z) in enumerate(((-1.2, -9), (1.4, -9))):
            Entity(parent=root, model='cube', shader=stone_shader, position=(x, 2.2, z), scale=(2.2, 4.4, 1))
    return root


if __name__ == '__main__':
    from monsters.frost_mimic import FrostMimic, make_human

    app = Ursina(title='Ледяной двойник', development_mode=False)
    FOG = (0.02, 0.025, 0.04)
    window.color = color.rgb(*FOG)
    env = build_environment(fog_color=FOG)

    observer_palette = dict(coat=(0.17, 0.27, 0.21), pants=(0.2, 0.18, 0.15), hair=(0.36, 0.23, 0.12),
                            eyes=(0.28, 0.2, 0.12))
    observer = make_human(position=(0.5, 0, 3.0), rotation_y=180, palette=observer_palette)

    mimic = FrostMimic(form='mask', mirror_target=observer.parts['head'])
    mimic.set_environment(fog_color=FOG, fog_density=0.06)
    mimic.look_target = observer.parts['head']

    ec = EditorCamera(rotation=(8, 200, 0))
    ec.target_z = -6
    ec.y = 1.5

    help_text = Text(
        'R — маска/истинный облик   Пробел — говорит   G — идти   C — скопировать наблюдателя   1-4 — виды\n'
        'ПКМ — вращать камеру, колесо — зум', position=window.top_left + Vec3(0.02, -0.02, 0), scale=0.8,
        color=color.rgb(0.75, 0.82, 0.9))
    subtitle = Text('', origin=(0, 0), y=-0.42, scale=1.1, color=color.rgb(0.85, 0.9, 1.0))
    LINES = ['Ты заблудился? Я тоже здесь… давно.', 'Подойди ближе. Я тебя знаю.', 'Выход там. Иди за мной.']

    def input(key):
        if key == 'r':
            mimic.toggle_form()
        elif key == 'space':
            line = random.choice(LINES)
            subtitle.text = line
            mimic.speak(0.07 * len(line))
        elif key == 'g':
            mimic.glide_to((random.uniform(-2, 2), 0, random.uniform(-6, 2)))
        elif key == 'c':
            mimic.copy_appearance(observer_palette)
        elif key in ('1', '2', '3', '4'):
            ec.rotation_y = {'1': 180, '2': 270, '3': 215, '4': 0}[key]
            ec.rotation_x = 8

    def update():
        ec.position = ec.position * 0.9 + (mimic.world_position + Vec3(0, 1.5, 0)) * 0.1
        if mimic._speak_t < 0 and subtitle.text:
            subtitle.text = ''

    if '--selftest' in sys.argv:          # прогон без человека: нажимает клавиши и выходит
        script = {5: 'space', 30: 'r', 90: 'g', 100: 'c', 115: 'r', 125: '3'}
        for i in range(160):
            if i in script:
                input(script[i])
            app.step()
        print('SELFTEST OK form =', mimic.form, 'frost patches =', len(mimic.patches))
    else:
        app.run()
