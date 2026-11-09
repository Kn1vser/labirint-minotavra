"""
Шейдеры «Бабки» (по фото-референсу: приглушённые, грязные, реалистичные).

material:
 0 кожа (бледная, морщинистая, в пятнах)
 1 лицо (то же + затенение глазниц и щёк из uv.x)
 2 лён (покрывало, платье: застиранный, грязный, рваный край)
 3 глаза (мутные, влажные)
 4 волосы (седые пряди)
 5 кожа ботинок

sepia_shader — постобработка камеры: сепия, зерно, виньетка, как на старой фотографии.
"""
from ursina import Shader

from .frost_shaders import COMMON_UNIFORMS, NOISE
from .kochkar_shaders import VERT

LIGHT = '''
vec3 shade(vec3 alb, vec3 N, vec3 V, float gloss, float ao){
    vec3 L = normalize(light_dir);
    float diff = clamp(dot(N, L), 0.0, 1.0);
    vec3 amb = mix(vec3(0.05,0.05,0.05), vec3(0.11,0.12,0.14), N.y*0.5+0.5);
    vec3 H = normalize(L + V);
    float spec = pow(clamp(dot(N, H), 0.0, 1.0), mix(8.0, 70.0, gloss)) * gloss;
    return (alb * (light_color*diff + amb) + light_color*spec*0.4) * ao;
}
'''

CLOTH_FRAG = '''#version 140
''' + NOISE + COMMON_UNIFORMS + LIGHT + '''
uniform int material;
uniform float fray;          // 1 — рвать край ткани по uv.y
in vec3 v_obj; in vec3 v_local; in vec3 v_wpos; in vec3 v_wnrm; in vec3 v_onrm; in vec2 v_uv;
out vec4 frag;

vec3 skin_albedo(vec3 p, vec3 lp, float forehead){
    float wr = vnoise(vec3(lp.x*40.0, lp.y*260.0, lp.z*40.0)) * (0.6 + 0.6*vnoise(p*30.0));
    float wrinkles = smoothstep(0.4, 0.8, wr) * (0.14 + 0.12*forehead);
    float crepe = vnoise(p*420.0) * 0.12;
    float spots = smoothstep(0.70, 0.80, vnoise(p*55.0)) * 0.22;
    float dirt = smoothstep(0.55, 0.8, fbm(p*14.0)) * 0.25;
    vec3 alb = vec3(0.60,0.55,0.48);
    alb = mix(alb, vec3(0.50,0.44,0.40), vnoise(p*12.0));      // неровный, сероватый тон
    alb *= 1.0 - wrinkles - crepe - spots;
    alb = mix(alb, vec3(0.28,0.24,0.19), dirt);
    return alb;
}

void main(){
    vec3 N = normalize(v_wnrm);
    bool inside = !gl_FrontFacing;
    if(inside) N = -N;
    vec3 V = normalize(cam_pos - v_wpos);
    float ndv = clamp(dot(N, V), 0.0, 1.0);
    vec3 p = v_obj;
    vec3 lp = v_local;
    vec3 col;

    if(material == 0 || material == 1){
        float forehead = material == 1 ? smoothstep(0.12, 0.17, lp.y) : 0.0;
        vec3 alb = skin_albedo(p, lp, forehead);
        float ao = material == 1 ? v_uv.x : 1.0;
        alb *= mix(0.35, 1.0, ao);                                   // глазницы и щёки в тени
        alb = mix(alb, alb*vec3(0.85,0.72,0.75), (1.0 - ao)*0.6);   // синюшность под глазами
        col = shade(alb, N, V, 0.25, mix(0.45, 1.0, ao));
        vec3 L = normalize(light_dir);
        col += alb * vec3(0.5,0.25,0.18) * pow(clamp(1.0 - abs(dot(N, L)), 0.0, 1.0), 3.0) * 0.12;
    }
    else if(material == 2){                        // лён
        if(fray > 0.5){                            // рваный, неровный край
            float edge = 0.035 + (vnoise(vec3(v_uv.x*60.0, 0.0, 1.0)) - 0.5)*0.05 + vnoise(vec3(v_uv.x*240.0, 0.0, 2.0))*0.03;
            if(v_uv.y < edge) discard;
        }
        float weave = 0.93 + 0.07*sin(lp.x*1400.0)*sin(lp.y*1400.0 + lp.z*900.0);
        vec3 alb = mix(vec3(0.36,0.32,0.27), vec3(0.47,0.43,0.36), fbm(p*6.0));
        alb = mix(alb, vec3(0.20,0.17,0.13), smoothstep(0.55, 0.78, fbm(p*3.0 + 5.0)) * 0.7);   // разводы
        float ground = clamp(1.0 - v_wpos.y / 0.6, 0.0, 1.0);
        alb = mix(alb, vec3(0.17,0.14,0.10), clamp(ground * fbm(p*9.0 + 2.0) * 1.2, 0.0, 0.8));  // грязь у подола
        alb = mix(alb, vec3(0.55,0.52,0.46), smoothstep(0.72, 0.85, fbm(p*20.0)) * 0.35);       // выгоревшие места
        alb *= weave;
        if(inside) alb *= 0.45;
        col = shade(alb, N, V, 0.03, 1.0);
        col += alb * light_color * pow(1.0 - ndv, 3.0) * 0.18;
    }
    else if(material == 3){                        // глаза
        vec3 q = normalize(lp);
        float r = length(q.xy);
        vec3 alb = mix(vec3(0.62,0.58,0.52), vec3(0.50,0.40,0.36), smoothstep(0.3, 1.0, r));   // желтоватые белки
        float iris = 1.0 - smoothstep(0.42, 0.48, r);
        vec3 irisCol = mix(vec3(0.22,0.20,0.18), vec3(0.42,0.42,0.40), vnoise(q*40.0));
        float ring = smoothstep(0.30, 0.44, r) * iris;                  // старческая дуга
        irisCol = mix(irisCol, vec3(0.62,0.62,0.60), ring*0.7);
        alb = mix(alb, irisCol, iris * step(0.0, q.z));
        alb = mix(alb, vec3(0.02), (1.0 - smoothstep(0.14, 0.2, r)) * step(0.0, q.z));
        col = shade(alb, N, V, 0.9, 0.85);
        vec3 H = normalize(normalize(light_dir) + V);
        col += vec3(1.0) * pow(clamp(dot(N, H), 0.0, 1.0), 300.0) * 1.5;   // влажный блик
    }
    else if(material == 4){                        // седые пряди
        vec3 alb = vec3(0.62,0.60,0.56) * (0.8 + 0.3*vnoise(p*300.0));
        col = shade(alb, N, V, 0.3, 0.9);
    }
    else {                                         // кожа ботинок
        vec3 alb = mix(vec3(0.10,0.08,0.06), vec3(0.20,0.16,0.12), fbm(p*20.0));
        alb = mix(alb, vec3(0.30,0.26,0.20), smoothstep(0.7, 0.85, fbm(p*40.0)) * 0.6);
        col = shade(alb, N, V, 0.35, 1.0);
    }
    frag = vec4(apply_fog(col, v_wpos), 1.0);
}
'''

SEPIA_FRAG = '''#version 140
uniform sampler2D tex;
uniform float time;
uniform float strength;     // 0 — обычные цвета, 1 — старая фотография
in vec2 uv;
out vec4 color;
float h(vec2 p){ return fract(sin(dot(p, vec2(12.9898,78.233))) * 43758.5453); }
void main(){
    vec3 c = texture(tex, uv).rgb;
    float g = dot(c, vec3(0.299,0.587,0.114));
    g = pow(g, 0.8) * 1.15;
    vec3 sep = vec3(g*1.07 + 0.03, g*0.95 + 0.02, g*0.78);
    float grain = (h(uv*vec2(1200.0, 700.0) + time*13.0) - 0.5) * 0.08;
    vec2 d = uv - 0.5;
    float vig = smoothstep(0.85, 0.25, length(d*vec2(1.1, 1.0)));
    vec3 outc = mix(c, sep + grain, strength) * mix(1.0, vig, 0.55 + 0.25*strength);
    color = vec4(outc, 1.0);
}
'''

cloth_shader = Shader(name='babka_cloth', language=Shader.GLSL, vertex=VERT, fragment=CLOTH_FRAG)
sepia_shader = Shader(name='sepia_photo', language=Shader.GLSL, fragment=SEPIA_FRAG,
                      default_input=dict(strength=1.0, time=0.0))

MATERIALS = dict(skin=0, face=1, linen=2, eye=3, hair=4, leather=5)
FRAYED = ('skirt', 'shawl', 'hood', 'forearm_R', 'forearm_L')
