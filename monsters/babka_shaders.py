"""
Шейдеры «Бабки». Один шейдер на ткани/кожу (uniform `material`) и отдельный — для очков.

material:
 0 кожа (бледная, морщинистая)    1 ватник (стёжка)        2 ситцевый халат в цветочек + фартук
 3 платок с розами и бахромой     4 вязка (base_color)     5 валенки (войлок)
 6 резина (галоши, оправа)        7 рот                    8 простой цвет с блеском (base_color, gloss)
 9 сетка авоськи                  10 стекло банки (полупрозрачное)
"""
from ursina import Shader

from .frost_shaders import COMMON_UNIFORMS, NOISE
from .kochkar_shaders import VERT

LIGHT = '''
uniform float face_shadow;     // тень от платка на лицо
vec3 shade(vec3 alb, vec3 N, vec3 V, float gloss, float ao){
    vec3 L = normalize(light_dir);
    float diff = clamp(dot(N, L)*0.8 + 0.2, 0.0, 1.0);
    vec3 amb = mix(vec3(0.03,0.03,0.04), vec3(0.08,0.10,0.15), N.y*0.5+0.5);
    vec3 H = normalize(L + V);
    float spec = pow(clamp(dot(N, H), 0.0, 1.0), mix(8.0, 90.0, gloss)) * gloss;
    return (alb * (light_color*diff + amb) + light_color*spec*0.6) * ao;
}
'''

CLOTH_FRAG = '''#version 140
''' + NOISE + COMMON_UNIFORMS + LIGHT + '''
uniform int material;
uniform vec3 base_color;
uniform float gloss;
in vec3 v_obj; in vec3 v_local; in vec3 v_wpos; in vec3 v_wnrm; in vec3 v_onrm; in vec2 v_uv;
out vec4 frag;

vec3 rose(vec2 q, float id){
    // роза: лепестки-кольца, вокруг зелёные листья
    float r = length(q);
    float a = atan(q.y, q.x);
    float petals = 0.5 + 0.5*sin(r*38.0 - a*2.0 + id*6.0);
    vec3 c1 = fract(id*7.3) > 0.66 ? vec3(0.95,0.80,0.25) : (fract(id*7.3) > 0.33 ? vec3(0.92,0.55,0.60) : vec3(0.97,0.92,0.85));
    vec3 col = mix(c1*0.6, c1, petals);
    return col;
}

void main(){
    vec3 N = normalize(v_wnrm);
    if(!gl_FrontFacing) N = -N;
    vec3 V = normalize(cam_pos - v_wpos);
    float ndv = clamp(dot(N, V), 0.0, 1.0);
    vec3 p = v_obj;
    vec3 lp = v_local;
    vec3 col;
    float alpha = 1.0;

    if(material == 0){                              // кожа
        float wr = vnoise(vec3(lp.x*30.0, lp.y*110.0, lp.z*30.0)) * vnoise(p*25.0);
        float wrinkles = smoothstep(0.35, 0.6, wr) * 0.22;
        float spots = smoothstep(0.72, 0.8, vnoise(p*60.0)) * 0.25;
        vec3 alb = vec3(0.72,0.66,0.58) * (1.0 - wrinkles - spots) * (0.9 + 0.2*vnoise(p*150.0));
        col = shade(alb, N, V, 0.15, 1.0 - face_shadow*(0.3 + 0.55*smoothstep(0.09, 0.17, lp.y)));   // тень от платка сверху
        vec3 L = normalize(light_dir);
        col += alb * vec3(0.6,0.25,0.18) * pow(clamp(1.0 - abs(dot(N, L)), 0.0, 1.0), 2.0) * 0.15;
    }
    else if(material == 1){                         // ватник
        float rows = abs(sin(lp.y*40.0));
        float stitch = (1.0 - smoothstep(0.0, 0.12, rows)) * step(0.5, fract(atan(lp.x, lp.z)*14.0));
        vec3 alb = mix(vec3(0.07,0.08,0.10), vec3(0.15,0.16,0.18), fbm(p*9.0));
        alb *= 0.7 + 0.3*smoothstep(0.0, 0.6, rows);                 // впадины между валиками
        alb = mix(alb, vec3(0.32,0.30,0.27), stitch*0.6);
        alb = mix(alb, vec3(0.22,0.20,0.17), smoothstep(0.66,0.74, fbm(p*4.0+2.0))*0.6);   // потёртости
        col = shade(alb, N, V, 0.05, 1.0);
    }
    else if(material == 2){                         // ситец в цветочек + фартук спереди
        vec3 cv = voronoi(p*22.0);
        float a = atan(cv.x, 0.03);
        vec3 alb = vec3(0.10,0.14,0.30);
        float flower = smoothstep(0.32, 0.22, cv.x) * step(0.35, cv.z);
        vec3 fcol = cv.z > 0.8 ? vec3(0.85,0.22,0.18) : (cv.z > 0.6 ? vec3(0.95,0.85,0.30) : vec3(0.92,0.92,0.88));
        alb = mix(alb, fcol, flower);
        alb = mix(alb, vec3(0.95,0.85,0.3), smoothstep(0.08, 0.04, cv.x) * step(0.35, cv.z));
        // фартук
        float apron = step(0.0, lp.z) * (1.0 - smoothstep(0.13, 0.15, abs(lp.x))) * step(lp.y, 0.06) * step(-0.62, lp.y);
        vec3 ap = mix(vec3(0.62,0.58,0.50), vec3(0.72,0.68,0.60), fbm(p*20.0));
        float pocket = (1.0 - smoothstep(0.0, 0.004, abs(abs(lp.x - 0.05) - 0.05))) * step(-0.35, lp.y) * step(lp.y, -0.22)
                     + (1.0 - smoothstep(0.0, 0.004, abs(lp.y + 0.35))) * step(abs(lp.x - 0.05), 0.05);
        ap = mix(ap, ap*0.6, clamp(pocket, 0.0, 1.0));
        alb = mix(alb, ap, apron);
        col = shade(alb*(0.85+0.15*fbm(p*40.0)), N, V, 0.05, 1.0);
    }
    else if(material == 3){                         // платок
        vec3 alb = vec3(0.55,0.04,0.05) * (0.85 + 0.2*fbm(p*30.0));
        vec3 cv = voronoi(p*44.0 + 3.0);
        vec2 q = vec2(cv.x, 0.0);
        float flower = smoothstep(0.42, 0.34, cv.x);
        float leaf = smoothstep(0.55, 0.45, cv.x) - flower;
        alb = mix(alb, vec3(0.10,0.30,0.12), leaf*step(0.4, cv.z)*0.9);
        alb = mix(alb, rose(vec2(cv.x*cos(cv.z*40.0), cv.x*sin(cv.z*40.0)), cv.z), flower*step(0.3, cv.z));
        // чёрная кайма с бахромой внизу
        float border = smoothstep(-0.10, -0.12, lp.y);
        alb = mix(alb, vec3(0.03,0.02,0.02), border);
        col = shade(alb, N, V, 0.2, 1.0);
    }
    else if(material == 4){                         // вязка
        float row = fract(lp.y*70.0);
        float col_ = fract(atan(lp.x, lp.z)*11.0 + lp.x*0.0);
        float v = abs(col_ - 0.5)*2.0;
        float st = smoothstep(0.1, 0.4, abs(row - v*0.5 - 0.25)*2.0);
        vec3 alb = base_color * (0.65 + 0.35*st) * (0.9 + 0.2*vnoise(p*120.0));
        col = shade(alb, N, V, 0.0, 1.0);
        col += alb * light_color * pow(1.0 - ndv, 2.0) * 0.3;           // пушистая шерсть
    }
    else if(material == 5){                         // валенки
        vec3 alb = mix(vec3(0.24,0.23,0.22), vec3(0.36,0.35,0.33), fbm(p*50.0)) * (0.85 + 0.25*vnoise(p*260.0));
        col = shade(alb, N, V, 0.0, 1.0);
        col += alb * light_color * pow(1.0 - ndv, 2.0) * 0.35;
    }
    else if(material == 6){                         // резина
        vec3 alb = vec3(0.025,0.025,0.03);
        col = shade(alb, N, V, 0.85, 1.0);
    }
    else if(material == 7){                         // рот
        col = vec3(0.04,0.0,0.0);
    }
    else if(material == 9){                         // сетка авоськи
        vec3 q = normalize(lp - vec3(0.0,-0.24,0.0));
        float a = atan(q.x, q.z) * 9.0 / 3.14159;
        float b = asin(clamp(q.y, -1.0, 1.0)) * 9.0 / 3.14159;
        vec2 g = vec2(a + b, a - b);
        vec2 f = abs(fract(g) - 0.5);
        float line = 1.0 - smoothstep(0.0, 0.06, min(f.x, f.y));
        if(line < 0.5) discard;
        col = shade(vec3(0.85,0.72,0.35), N, V, 0.0, 1.0);
    }
    else if(material == 10){                        // стекло банки
        float fres = pow(1.0 - ndv, 3.0);
        col = vec3(0.6,0.8,0.75)*0.2 + light_color * fres * 0.8;
        vec3 H = normalize(normalize(light_dir) + V);
        col += light_color * pow(clamp(dot(N, H), 0.0, 1.0), 120.0) * 1.5;
        alpha = 0.18 + fres*0.6;
    }
    else {                                          // простой цвет
        vec3 alb = base_color * (0.85 + 0.3*fbm(p*35.0));
        col = shade(alb, N, V, gloss, 1.0);
    }
    frag = vec4(apply_fog(col, v_wpos), alpha);
}
'''

LENS_FRAG = '''#version 140
''' + NOISE + COMMON_UNIFORMS + '''
uniform float glow;         // 0 — тусклые, 1 — горят (заметила), 2 — вспышка
uniform float blind;        // ослеплена фонарём
in vec3 v_obj; in vec3 v_local; in vec3 v_wpos; in vec3 v_wnrm; in vec3 v_onrm; in vec2 v_uv;
out vec4 frag;
void main(){
    vec3 N = normalize(v_wnrm);
    vec3 V = normalize(cam_pos - v_wpos);
    float ndv = clamp(dot(N, V), 0.0, 1.0);
    vec2 q = v_local.xy / 0.026;
    float r = length(q);
    // толстое стекло: внутри мутное свечение, по краю — кольца «бутылочного» стекла
    float rings = 0.5 + 0.5*sin(r*18.0);
    vec3 cold = vec3(0.92,0.90,0.74);
    vec3 col = cold * (0.10 + glow*1.25) * (1.0 - r*0.35) + cold * rings * 0.08 * (1.0 + glow);
    // зрачок-точка в глубине — смотрит на тебя
    float pupil = smoothstep(0.09, 0.04, length(q - vec2(0.0, -0.05))) * (1.0 - blind);   // крошечная точка
    col = mix(col, vec3(0.0), pupil * min(glow, 1.0) * 0.9);
    col += vec3(1.0) * pow(1.0 - ndv, 3.0) * 0.4;
    col += vec3(1.0,0.97,0.9) * blind * 1.5;
    frag = vec4(apply_fog(col, v_wpos), 1.0);
}
'''

cloth_shader = Shader(name='babka_cloth', language=Shader.GLSL, vertex=VERT, fragment=CLOTH_FRAG)
lens_shader = Shader(name='babka_lens', language=Shader.GLSL, vertex=VERT, fragment=LENS_FRAG)

# kind -> (material, base_color, gloss)
MATERIALS = dict(
    skin=(0, (0, 0, 0), 0), vatnik=(1, (0, 0, 0), 0), dress=(2, (0, 0, 0), 0), platok=(3, (0, 0, 0), 0),
    knit_grey=(4, (0.45, 0.43, 0.40), 0), knit_red=(4, (0.60, 0.10, 0.10), 0), stocking=(4, (0.42, 0.33, 0.26), 0),
    felt=(5, (0, 0, 0), 0), rubber=(6, (0, 0, 0), 0), mouth=(7, (0, 0, 0), 0),
    gold=(8, (0.95, 0.70, 0.25), 0.9), tin=(8, (0.62, 0.62, 0.60), 0.8), pickle=(8, (0.20, 0.32, 0.10), 0.4),
    bread=(8, (0.62, 0.42, 0.20), 0.1), string=(8, (0.85, 0.72, 0.35), 0.0), net=(9, (0, 0, 0), 0),
    jar=(10, (0, 0, 0), 0),
)
