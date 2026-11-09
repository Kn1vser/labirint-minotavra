"""
Шейдеры «Кочкаря» и таёжного окружения.

nature_shader — один шейдер на все природные материалы, выбирается uniform `material`:
    0 мох (кочка: сфагнум, кладония, брусника, торф снизу)
    1 коряга (выбеленное дерево, волокна, трещины, пятна лишайника)
    2 хвоя        3 бородатый лишайник
    4 простой цвет (base_color)   5 берёзовая кора   6 шляпка гриба
eye_shader    — капля светящейся смолы с горизонтальным зрачком.
ground_shader — лесная подстилка: мох, хвоя, брусничник.

Общие uniform-ы (time, cam_pos, light_dir, light_color, fog_*) — как у Ледяного двойника,
стоят на корне сцены.
"""
from ursina import Shader

from .frost_shaders import COMMON_UNIFORMS, NOISE

VERT = '''#version 140
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelMatrix;
in vec4 p3d_Vertex;
in vec3 p3d_Normal;
in vec2 p3d_MultiTexCoord0;
uniform vec3 part_offset;
uniform float sway;         // качание на ветру (хвоя, лишайник, корешки)
uniform float time;
out vec3 v_obj; out vec3 v_local; out vec3 v_wpos; out vec3 v_wnrm; out vec3 v_onrm; out vec2 v_uv;
void main(){
    vec4 v = p3d_Vertex;
    if(sway > 0.0){
        float h = max(0.0, abs(v.y) + length(v.xz)*0.3);
        v.x += sin(time*1.3 + part_offset.x*3.0 + v.y*2.0) * sway * h * 0.06;
        v.z += cos(time*1.1 + part_offset.z*3.0 + v.y*1.7) * sway * h * 0.05;
    }
    gl_Position = p3d_ModelViewProjectionMatrix * v;
    v_local = v.xyz;
    v_obj = v.xyz + part_offset;
    v_wpos = (p3d_ModelMatrix * v).xyz;
    v_wnrm = normalize(mat3(p3d_ModelMatrix) * p3d_Normal);
    v_onrm = p3d_Normal;
    v_uv = p3d_MultiTexCoord0;
}
'''

LIGHT = '''
vec3 shade(vec3 alb, vec3 N, vec3 V, float rough, float ao){
    vec3 L = normalize(light_dir);
    float diff = clamp(dot(N, L), 0.0, 1.0);
    // небо сверху голубоватое, снизу отражённый тёплый свет земли
    vec3 amb = mix(vec3(0.10,0.09,0.07), vec3(0.20,0.25,0.33), N.y*0.5+0.5);
    vec3 H = normalize(L + V);
    float spec = pow(clamp(dot(N, H), 0.0, 1.0), mix(80.0, 8.0, rough)) * (1.0 - rough) * 0.5;
    return alb * (light_color * diff + amb + lamp_light(g_wpos, N)) * ao + light_color * spec * ao + alb * rim_light(N, V);
}
'''

NATURE_FRAG = '''#version 140
''' + NOISE + COMMON_UNIFORMS + LIGHT + '''
uniform int material;
uniform vec3 base_color;
in vec3 v_obj; in vec3 v_local; in vec3 v_wpos; in vec3 v_wnrm; in vec3 v_onrm; in vec2 v_uv;
out vec4 frag;

void main(){
    g_wpos = v_wpos;
    vec3 N = normalize(v_wnrm);
    if(!gl_FrontFacing) N = -N;
    vec3 V = normalize(cam_pos - v_wpos);
    float ndv = clamp(dot(N, V), 0.0, 1.0);
    vec3 p = v_obj;
    vec3 col;

    if(material == 0){                       // ---- мох
        vec3 on = normalize(v_onrm);
        float top = smoothstep(-0.35, 0.35, on.y);
        float big = fbm(p*1.7);
        float mid = fbm(p*6.0 + 3.0);
        float fine = vnoise(p*90.0)*0.5 + vnoise(p*170.0)*0.5;
        vec3 sphag = mix(vec3(0.36,0.46,0.13), vec3(0.55,0.58,0.20), mid);
        vec3 dark  = vec3(0.12,0.20,0.06);
        vec3 red   = vec3(0.46,0.22,0.12);
        vec3 moss = mix(dark, sphag, smoothstep(0.35, 0.65, big));
        moss = mix(moss, red, smoothstep(0.62, 0.75, fbm(p*2.3 + 9.0)) * 0.7);
        // кладония — светлые серо-зелёные подушки
        float clad = smoothstep(0.60, 0.68, fbm(p*3.1 + 17.0)) * top;
        moss = mix(moss, vec3(0.70,0.73,0.62) * (0.8 + 0.3*fine), clad);
        moss *= 0.75 + 0.45*fine;
        // брусника: редкие красные ягоды на верхушке
        vec3 bv = voronoi(p*26.0);
        float berry = smoothstep(0.22, 0.12, bv.x) * step(0.9, bv.z) * top * (1.0 - clad);
        vec3 leaf = voronoi(p*26.0 + 0.3).x < 0.35 && bv.z > 0.75 ? vec3(0.10,0.22,0.08) : moss;
        moss = mix(moss, leaf, top*0.5*step(0.75, bv.z));
        // торф и корни снизу
        vec3 peat = mix(vec3(0.10,0.07,0.045), vec3(0.22,0.15,0.09), fbm(p*vec3(14.0,3.0,14.0)));
        vec3 alb = mix(peat, moss, smoothstep(-0.55, -0.1, on.y + (big-0.5)*0.4));
        float ao = mix(0.55, 1.0, mid) * (0.8 + 0.2*fine);
        col = shade(alb, N, V, 1.0, ao);
        // мягкий «ворс» мха по краю силуэта
        col += alb * light_color * pow(1.0 - ndv, 2.5) * 0.6 * top;
        vec3 bcol = mix(vec3(0.55,0.03,0.05), vec3(0.85,0.10,0.10), clamp(1.0 - bv.x*5.0, 0.0, 1.0));
        col = mix(col, shade(bcol, N, V, 0.2, 1.0) + vec3(0.25)*pow(clamp(1.0-bv.x*6.0, 0.0, 1.0), 8.0), berry);
    }
    else if(material == 1 || material == 5){ // ---- коряга / береста
        vec3 lp = v_local;
        float grain = fbm(vec3(lp.x*28.0, lp.y*2.5, lp.z*28.0) + p*0.5);
        float cracks = smoothstep(0.47, 0.50, vnoise(vec3(lp.x*55.0, lp.y*5.0, lp.z*55.0)))
                     - smoothstep(0.50, 0.53, vnoise(vec3(lp.x*55.0, lp.y*5.0, lp.z*55.0)));
        vec3 alb;
        if(material == 1){
            alb = mix(vec3(0.40,0.37,0.33), vec3(0.66,0.63,0.58), grain);
            alb = mix(alb, vec3(0.16,0.13,0.11), cracks*0.8);
            // лишайник пятнами: серо-зелёный и оранжевый
            vec3 lv = voronoi(p*13.0);
            float lich = smoothstep(0.42, 0.30, lv.x + (fbm(p*40.0)-0.5)*0.3);
            alb = mix(alb, lv.z > 0.8 ? vec3(0.85,0.52,0.16) : vec3(0.60,0.68,0.50), lich*step(0.55, lv.z));
            // мох в низинах
            alb = mix(alb, vec3(0.25,0.33,0.10), smoothstep(0.62, 0.75, fbm(p*5.0 + 2.0))*0.8);
        } else {
            alb = mix(vec3(0.82,0.80,0.76), vec3(0.95,0.94,0.91), grain);
            float lent = smoothstep(0.70, 0.85, vnoise(vec3(lp.x*12.0, lp.y*70.0, lp.z*12.0)))
                       * smoothstep(0.3, 0.7, vnoise(lp*vec3(18.0,3.0,18.0)));
            float patchD = smoothstep(0.6, 0.7, fbm(lp*vec3(6.0,1.5,6.0))) + smoothstep(1.2, 0.0, lp.y)*0.7;
            alb = mix(alb, vec3(0.08,0.07,0.06), clamp(lent + patchD*0.8, 0.0, 1.0));
        }
        float ao = 0.7 + 0.3*grain;
        col = shade(alb, N, V, 0.85, ao);
    }
    else if(material == 2){                  // ---- хвоя
        float n = vnoise(p*120.0)*0.6 + vnoise(p*40.0)*0.4;
        vec3 alb = mix(vec3(0.05,0.13,0.07), vec3(0.15,0.27,0.12), n);
        float inner = clamp(length(v_local.xz) * 3.0, 0.25, 1.0);
        col = shade(alb, N, V, 0.9, inner * (0.7 + 0.3*n));
        col += alb * light_color * pow(1.0 - ndv, 3.0) * 0.5;      // просвет кончиков хвои
    }
    else if(material == 3){                  // ---- бородатый лишайник
        vec3 alb = vec3(0.62,0.68,0.52) * (0.85 + 0.3*vnoise(p*200.0));
        col = shade(alb, N, V, 1.0, 1.0) + alb * light_color * 0.25;
    }
    else if(material == 6){                  // ---- шляпка подосиновика
        vec3 alb = mix(vec3(0.62,0.22,0.06), vec3(0.80,0.36,0.10), fbm(p*20.0));
        alb *= 0.85 + 0.25*smoothstep(0.0, 0.05, v_local.y - 0.1);
        col = shade(alb, N, V, 0.45, 1.0);
    }
    else {                                   // ---- просто цвет
        vec3 alb = base_color * (0.85 + 0.3*fbm(p*25.0));
        col = shade(alb, N, V, 0.9, 1.0);
    }
    frag = vec4(apply_fog(col, v_wpos), 1.0);
}
'''

EYE_FRAG = '''#version 140
''' + NOISE + COMMON_UNIFORMS + '''
uniform float glow;          // яркость свечения
in vec3 v_obj; in vec3 v_local; in vec3 v_wpos; in vec3 v_wnrm; in vec3 v_onrm; in vec2 v_uv;
out vec4 frag;
void main(){
    vec3 N = normalize(v_wnrm);
    vec3 V = normalize(cam_pos - v_wpos);
    vec3 L = normalize(light_dir);
    float ndv = clamp(dot(N, V), 0.0, 1.0);
    vec3 lp = v_local / vec3(0.042, 0.036, 0.04);    // единичная сфера
    // смола: тёмно-медовая по краю, светлая и тёплая в глубине
    float depth = ndv;
    vec3 resin = mix(vec3(0.35,0.12,0.02), vec3(1.0,0.62,0.16), pow(depth, 1.5));
    resin *= 0.75 + 0.35*fbm(lp*3.0 + vec3(0.0, time*0.05, 0.0));
    // пузырьки воздуха внутри
    vec3 b = voronoi(lp*4.0 + 1.3);
    resin += vec3(1.0,0.85,0.5) * smoothstep(0.12, 0.04, b.x) * step(0.8, b.z) * 0.5;
    // спокойный горизонтальный зрачок, как у лося
    float pupil = (1.0 - smoothstep(0.07, 0.12, abs(lp.y))) * (1.0 - smoothstep(0.42, 0.55, abs(lp.x)))
                * smoothstep(0.55, 0.8, lp.z);
    vec3 col = resin * (0.35 + glow*0.9);
    col = mix(col, vec3(0.03,0.015,0.0), pupil*0.92);
    vec3 H = normalize(L + V);
    col += light_color * pow(clamp(dot(N, H), 0.0, 1.0), 200.0) * 2.0;
    col += vec3(1.0,0.8,0.5) * pow(1.0 - ndv, 4.0) * 0.3;
    frag = vec4(apply_fog(col, v_wpos), 1.0);
}
'''

GROUND_FRAG = '''#version 140
''' + NOISE + COMMON_UNIFORMS + LIGHT + '''
in vec3 v_obj; in vec3 v_local; in vec3 v_wpos; in vec3 v_wnrm; in vec3 v_onrm; in vec2 v_uv;
out vec4 frag;
void main(){
    g_wpos = v_wpos;
    vec3 p = v_wpos;
    vec3 N = normalize(v_wnrm);
    vec3 V = normalize(cam_pos - p);
    float big = fbm(vec3(p.xz*0.25, 0.0));
    float mid = fbm(vec3(p.xz*1.3, 4.0));
    float fine = vnoise(vec3(p.xz*40.0, 1.0))*0.5 + vnoise(vec3(p.xz*90.0, 2.0))*0.5;
    vec3 moss = mix(vec3(0.13,0.20,0.06), vec3(0.38,0.44,0.14), mid);
    vec3 needles = mix(vec3(0.30,0.20,0.10), vec3(0.48,0.33,0.17), fine);
    vec3 clad = vec3(0.66,0.69,0.58);
    vec3 alb = mix(needles, moss, smoothstep(0.28, 0.48, big));
    alb = mix(alb, clad*(0.8+0.3*fine), smoothstep(0.66, 0.72, fbm(vec3(p.xz*0.9, 9.0))));
    // хвоинки — тонкие штрихи
    float nd = vnoise(vec3(p.x*60.0 + p.z*20.0, p.z*8.0, 3.0));
    alb = mix(alb, vec3(0.55,0.38,0.18), smoothstep(0.82, 0.9, nd) * 0.6);
    // брусничник
    vec3 bv = voronoi(vec3(p.xz*9.0, 7.0));
    alb = mix(alb, vec3(0.08,0.2,0.06), smoothstep(0.35, 0.2, bv.x) * step(0.8, bv.z));
    float berry = smoothstep(0.08, 0.04, voronoi(vec3(p.xz*30.0, 2.0)).x) * step(0.8, bv.z) * smoothstep(0.4, 0.2, bv.x);
    alb = mix(alb, vec3(0.7,0.06,0.08), berry);
    alb *= 0.7 + 0.45*fine;
    vec3 col = shade(alb, N, V, 1.0, 0.8 + 0.2*mid);
    frag = vec4(apply_fog(col, p), 1.0);
}
'''


def _make(name, frag):
    return Shader(name=name, language=Shader.GLSL, vertex=VERT, fragment=frag)


nature_shader = _make('kochkar_nature', NATURE_FRAG)
eye_shader = _make('kochkar_eye', EYE_FRAG)
ground_shader = _make('taiga_ground', GROUND_FRAG)

MATERIAL = dict(moss=0, wood=1, roots=1, needles=2, lichen=3, plain=4, stem=4, birch=5, cap=6)
SWAY = dict(needles=0.5, lichen=1.0, roots=0.6)
