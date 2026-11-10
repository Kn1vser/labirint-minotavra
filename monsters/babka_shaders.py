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

VERT = '''#version 140
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelMatrix;
in vec4 p3d_Vertex;
in vec3 p3d_Normal;
in vec2 p3d_MultiTexCoord0;
uniform vec3 part_offset;
uniform float wind;          // колыхание ткани у края (подол, края покрывала)
uniform float time;
out vec3 v_obj; out vec3 v_local; out vec3 v_wpos; out vec3 v_wnrm; out vec3 v_onrm; out vec2 v_uv;
void main(){
    vec4 v = p3d_Vertex;
    vec3 w = (p3d_ModelMatrix * v).xyz;
    if(wind > 0.0){
        float edge = pow(clamp(1.0 - p3d_MultiTexCoord0.y, 0.0, 1.0), 2.0);
        float g = sin(time*1.3 + w.x*3.0 + w.z*2.0) * 0.6 + sin(time*2.9 + w.y*7.0 + w.x*5.0) * 0.4;
        v.xyz += vec3(g*0.6, 0.0, g) * edge * wind * 0.03;
    }
    gl_Position = p3d_ModelViewProjectionMatrix * v;
    v_local = p3d_Vertex.xyz;
    v_obj = p3d_Vertex.xyz + part_offset;
    v_wpos = (p3d_ModelMatrix * v).xyz;
    v_wnrm = normalize(mat3(p3d_ModelMatrix) * p3d_Normal);
    v_onrm = p3d_Normal;
    v_uv = p3d_MultiTexCoord0;
}
'''

LIGHT = '''
vec3 shade(vec3 alb, vec3 N, vec3 V, float gloss, float ao){
    float sc = snow_cover(N, g_wpos);
    alb = mix(alb, snow_albedo(g_wpos), sc);
    gloss = mix(gloss, 0.0, sc);
    vec3 L = normalize(light_dir);
    float diff = clamp(dot(N, L), 0.0, 1.0);
    vec3 amb = mix(vec3(0.05,0.05,0.05), vec3(0.11,0.12,0.14), N.y*0.5+0.5);
    vec3 H = normalize(L + V);
    float spec = pow(clamp(dot(N, H), 0.0, 1.0), mix(8.0, 70.0, gloss)) * gloss;
    vec3 lamp = lamp_light(g_wpos, N);
    vec3 Hl = normalize(normalize(lamp_pos - g_wpos) + V);
    float specl = pow(clamp(dot(N, Hl), 0.0, 1.0), mix(8.0, 70.0, gloss)) * gloss;
    return (alb * (light_color*diff + amb + lamp) + light_color*spec*0.4 + lamp*specl*0.6) * ao + alb * rim_light(N, V) * 1.4
         + (light_color + lamp) * snow_sparkle(g_wpos, V) * sc * 1.5;
}
'''

CLOTH_FRAG = '''#version 140
''' + NOISE + COMMON_UNIFORMS + LIGHT + '''
uniform int material;
uniform float fray;          // 1 — рвать край ткани по uv.y
uniform float cold_flush;    // покраснение от мороза (нос, пальцы)
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
    g_wpos = v_wpos;
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
        alb = mix(alb, alb*vec3(1.28,0.78,0.78) + vec3(0.04,0.0,0.0), cold_flush * snow * 0.75);
        if(material == 1){
            // «гусиные лапки» у глаз и складки на переносице
            for(int k=0; k<2; k++){
                vec2 c = vec2(k == 0 ? 0.052 : -0.052, 0.112);
                vec2 q = lp.xy - c;
                float a = atan(q.y, q.x);
                float rr = length(q);
                float feet = smoothstep(0.6, 0.95, sin(a*14.0)) * smoothstep(0.004, 0.012, rr) * smoothstep(0.03, 0.012, rr);
                alb *= 1.0 - feet*0.35*step(0.0, (k == 0 ? q.x : -q.x));
            }
            alb *= 1.0 - smoothstep(0.7, 1.0, sin(lp.x*420.0)) * smoothstep(0.012, 0.0, abs(lp.x)) * smoothstep(0.1, 0.13, lp.y)*0.3;
        } else {
            // сухожилия и вены на тыльной стороне кисти, складки на суставах
            float tend = smoothstep(0.75, 1.0, sin(lp.x*190.0)) * step(lp.y, -0.02) * step(-0.09, lp.y);
            float vein = smoothstep(0.03, 0.0, abs(lp.x - 0.01 + sin(lp.y*60.0)*0.006)) * step(lp.y, 0.0) * step(-0.08, lp.y);
            alb = mix(alb, alb*1.12, tend*0.5);
            alb = mix(alb, alb*vec3(0.75,0.78,0.9), vein*0.45);
            alb *= 1.0 - smoothstep(0.85, 1.0, sin(lp.y*700.0)) * 0.05;
        }
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
        // заплатки со стежками
        vec3 pv = voronoi(p*vec3(5.0, 4.0, 5.0) + 11.0);
        float patchM = step(0.86, pv.z) * smoothstep(0.30, 0.26, pv.x);
        float seam = step(0.86, pv.z) * (smoothstep(0.24, 0.27, pv.x) - smoothstep(0.29, 0.32, pv.x));
        float stitch = seam * step(0.5, fract((p.x + p.y + p.z)*90.0));
        alb = mix(alb, mix(vec3(0.30,0.27,0.22), vec3(0.42,0.36,0.28), fbm(p*30.0)), patchM);
        alb = mix(alb, vec3(0.62,0.58,0.50), stitch*0.8);
        alb *= 1.0 - seam*0.25;
        alb *= weave;
        // иней по краю ткани и снег, налипший на подол
        float rime = smoothstep(0.22, 0.03, v_uv.y) * fray * (0.4 + 0.6*vnoise(p*90.0));
        float caked = smoothstep(0.45, 0.05, v_wpos.y) * (0.5 + 0.5*fbm(p*14.0));
        alb = mix(alb, vec3(0.86,0.9,0.96), clamp((rime*0.75 + caked*0.85) * snow, 0.0, 0.9));
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
        alb = mix(alb, vec3(0.92,0.95,1.0), snow * smoothstep(0.4, 0.8, vnoise(p*160.0)) * 0.8);   // иней
        col = shade(alb, N, V, 0.3, 0.9);
    }
    else if(material == 7){                        // пуховый платок: шерстяная вязка, пух
        if(fray > 0.5){
            float edge = 0.03 + vnoise(vec3(v_uv.x*120.0, 0.0, 4.0))*0.04;
            if(v_uv.y < edge) discard;
        }
        float rows = fract(lp.y*90.0 + abs(fract(atan(lp.x, lp.z)*16.0) - 0.5)*0.9);
        float knit = 0.82 + 0.18*smoothstep(0.1, 0.5, abs(rows - 0.5)*2.0);
        vec3 alb = mix(vec3(0.42,0.40,0.37), vec3(0.58,0.56,0.52), fbm(p*8.0)) * knit;
        alb = mix(alb, vec3(0.26,0.24,0.22), smoothstep(0.6, 0.8, fbm(p*4.0 + 3.0))*0.5);           // свалявшиеся места
        float rime = smoothstep(0.25, 0.03, v_uv.y) * fray;
        alb = mix(alb, vec3(0.86,0.9,0.96), rime * snow * 0.7);
        if(inside) alb *= 0.45;
        col = shade(alb, N, V, 0.0, 1.0);
        col += alb * (light_color + lamp_light(v_wpos, N)) * pow(1.0 - ndv, 2.0) * 0.55;          // пух светится по краю
    }
    else if(material == 8){                        // валенки
        vec3 alb = mix(vec3(0.24,0.23,0.22), vec3(0.36,0.35,0.33), fbm(p*50.0)) * (0.85 + 0.25*vnoise(p*260.0));
        alb = mix(alb, vec3(0.86,0.9,0.96), smoothstep(0.16, 0.02, v_wpos.y) * snow * (0.5 + 0.5*vnoise(p*40.0)));
        col = shade(alb, N, V, 0.0, 1.0);
        col += alb * light_color * pow(1.0 - ndv, 2.0) * 0.3;
    }
    else if(material == 6){                        // ногти: жёлтые, толстые, с бороздками
        vec3 alb = mix(vec3(0.55,0.50,0.38), vec3(0.68,0.62,0.48), smoothstep(0.3, 0.7, sin(lp.x*900.0)*0.5+0.5));
        col = shade(alb, N, V, 0.5, 1.0);
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

MATERIALS = dict(skin=0, face=1, linen=2, eye=3, hair=4, leather=5, nail=6, wool=7, felt=8)
FRAYED = ('skirt', 'shawl', 'hood', 'forearm_R', 'forearm_L')
NO_SNOW = ('eye', 'face', 'nail')
COLD = {'nose': 1.0, 'hand_R': 0.6, 'hand_L': 0.6}
WINDY = {'skirt': 1.0, 'shawl': 1.3, 'hood': 0.8, 'forearm_R': 0.6, 'forearm_L': 0.6}
