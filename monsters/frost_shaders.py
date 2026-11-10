"""
GLSL-шейдеры «Ледяного двойника».

shell_shader   — тело: полупрозрачная оболочка из инея и заледеневшей бересты,
                 внутри темнота и медленно кружащий снег (parallax-слои).
face_shader    — гладкий овал льда, замёрзшее зеркало с отражением смотрящего.
crack_shader   — трещина на горле, светится и раскрывается, когда существо говорит.
mask_shader    — человеческая «кожа». Покрывается инеем, трескается и осыпается.
frost_shader   — иней на земле, растущий вокруг стоящего существа.

Общие uniform-ы (time, cam_pos, light_dir, fog_*) ставятся на корневой узел
и наследуются всеми частями.
"""
from ursina import Shader

NOISE = '''
float hash13(vec3 p){ p = fract(p*0.1031); p += dot(p, p.zyx+31.32); return fract((p.x+p.y)*p.z); }
vec3 hash33(vec3 p){ p = fract(p*vec3(.1031,.1030,.0973)); p += dot(p, p.yxz+33.33); return fract((p.xxy+p.yxx)*p.zyx); }
float vnoise(vec3 p){
    vec3 i = floor(p), f = fract(p); f = f*f*(3.0-2.0*f);
    return mix(mix(mix(hash13(i), hash13(i+vec3(1,0,0)), f.x), mix(hash13(i+vec3(0,1,0)), hash13(i+vec3(1,1,0)), f.x), f.y),
               mix(mix(hash13(i+vec3(0,0,1)), hash13(i+vec3(1,0,1)), f.x), mix(hash13(i+vec3(0,1,1)), hash13(i+vec3(1,1,1)), f.x), f.y), f.z);
}
float fbm(vec3 p){ float a=0.5, s=0.0; for(int i=0;i<5;i++){ s += a*vnoise(p); p = p*2.03 + vec3(1.7,9.2,3.1); a *= 0.5; } return s; }
float fbm3(vec3 p){ float a=0.5, s=0.0; for(int i=0;i<3;i++){ s += a*vnoise(p); p = p*2.03 + vec3(1.7,9.2,3.1); a *= 0.5; } return s; }
// x = расстояние до центра клетки, y = расстояние до границы (F2-F1), z = id клетки
vec3 voronoi(vec3 p){
    vec3 i = floor(p), f = fract(p);
    float d1 = 8.0, d2 = 8.0, id = 0.0;
    for(int z=-1; z<=1; z++) for(int y=-1; y<=1; y++) for(int x=-1; x<=1; x++){
        vec3 g = vec3(x,y,z);
        vec3 r = g + hash33(i+g) - f;
        float d = dot(r,r);
        if(d < d1){ d2 = d1; d1 = d; id = hash13(i+g+7.7); }
        else if(d < d2){ d2 = d; }
    }
    return vec3(sqrt(d1), sqrt(d2)-sqrt(d1), id);
}
'''

COMMON_UNIFORMS = '''
uniform float time;
uniform vec3 cam_pos;
uniform vec3 light_dir;     // направление НА источник (мир)
uniform vec3 light_color;
uniform vec3 fog_color;
uniform float fog_density;
// керосиновая лампа (точечный тёплый свет) и холодный контровой свет
uniform vec3 lamp_pos;
uniform vec3 lamp_color;
uniform float lamp_power;
uniform vec3 rim_dir;
uniform vec3 rim_color;
vec3 g_wpos = vec3(0.0);
vec3 lamp_light(vec3 wpos, vec3 N){
    vec3 d = lamp_pos - wpos;
    float dist2 = max(dot(d, d), 0.04);
    float ndl = clamp(dot(N, normalize(d)) * 0.85 + 0.15, 0.0, 1.0);
    return lamp_color * lamp_power * ndl / (1.0 + dist2 * 0.9);
}
// снег: копится на поверхностях, обращённых вверх
uniform float snow;          // 0 — лето/осень, 1 — снежная тайга (на всю сцену)
uniform float snow_mask;     // на части: 1 — снег ложится, 0 — нет (глаза, лицо)
float snow_cover(vec3 N, vec3 wpos){
    float k = snow * snow_mask;
    if(k <= 0.0) return 0.0;
    float n = vnoise(wpos*6.0)*0.6 + vnoise(wpos*31.0)*0.4;
    return smoothstep(0.22, 0.6, N.y + (n - 0.5)*0.55) * k;
}
vec3 snow_albedo(vec3 wpos){
    return mix(vec3(0.74,0.79,0.88), vec3(0.95,0.97,1.0), vnoise(wpos*45.0)*0.6 + vnoise(wpos*7.0)*0.4);
}
float snow_sparkle(vec3 wpos, vec3 V){
    float h = fract(sin(dot(floor(wpos*260.0), vec3(12.9898,78.233,37.719))) * 43758.5453);
    float tw = 0.5 + 0.5*sin(dot(V, vec3(41.0,23.0,37.0)) + h*30.0);
    return step(0.985, h) * tw;
}
vec3 rim_light(vec3 N, vec3 V){
    float r = pow(1.0 - clamp(dot(N, V), 0.0, 1.0), 3.0) * clamp(dot(N, normalize(rim_dir)) * 0.5 + 0.5, 0.0, 1.0);
    return rim_color * r;
}
vec3 apply_fog(vec3 col, vec3 wpos){
    float f = 1.0 - exp(-fog_density * distance(wpos, cam_pos));
    return mix(col, fog_color, clamp(f, 0.0, 1.0));
}
'''

LIT_VERTEX = '''#version 140
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelMatrix;
in vec4 p3d_Vertex;
in vec3 p3d_Normal;
in vec2 p3d_MultiTexCoord0;
uniform vec3 part_offset;
out vec3 v_obj;
out vec3 v_local;
out vec3 v_wpos;
out vec3 v_wnrm;
out vec2 v_uv;
void main(){
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
    v_local = p3d_Vertex.xyz;
    v_obj = p3d_Vertex.xyz + part_offset;
    v_wpos = (p3d_ModelMatrix * p3d_Vertex).xyz;
    v_wnrm = normalize(mat3(p3d_ModelMatrix) * p3d_Normal);
    v_uv = p3d_MultiTexCoord0;
}
'''

# ------------------------------------------------------------------ тело
SHELL_FRAG = '''#version 140
''' + NOISE + COMMON_UNIFORMS + '''
uniform mat4 p3d_ModelMatrixInverse;
uniform float materialize;   // 0 — нет тела, 1 — тело полностью проявилось
uniform float inner_depth;   // толщина «полости» части (торс 1, пальцы ~0.2)
uniform float breach;        // 1 — у этой части пролом на спине
uniform float crack_glow;    // подсветка трещин (когда говорит / злится)
uniform float frost_boost;   // доп. иней (например, у ступней)
in vec3 v_obj; in vec3 v_local; in vec3 v_wpos; in vec3 v_wnrm; in vec2 v_uv;
out vec4 frag;

// слой кружащего снега внутри пустоты
float snow_layer(vec3 q, float t, float scale, float seed){
    float a = t*0.22 + q.y*1.6 + seed;
    float c = cos(a), s = sin(a);
    q.xz = mat2(c,-s,s,c) * q.xz;
    q.y += t*0.09;                       // снег медленно опускается
    q += vec3(sin(t*0.3+seed), 0.0, cos(t*0.27+seed))*0.05;
    vec3 v = voronoi(q*scale + seed*13.1);
    float flake = smoothstep(0.16, 0.02, v.x) * step(0.62, v.z);
    float tw = 0.6 + 0.4*sin(t*2.0 + v.z*40.0);
    return flake * tw;
}

void main(){
    vec3 N = normalize(v_wnrm);
    vec3 V = normalize(cam_pos - v_wpos);
    vec3 L = normalize(light_dir);
    float ndv = clamp(dot(N, V), 0.0, 1.0);
    float fres = pow(1.0 - ndv, 2.4);
    vec3 p = v_obj;

    // ---- проявление (растворение по шуму с ледяной кромкой)
    float dn = fbm3(p*6.0 + 2.0);
    float thr = materialize*1.25 - 0.05;
    if(dn > thr) discard;
    float edgeM = smoothstep(thr-0.07, thr, dn) * step(materialize, 0.999);

    // ---- береста: пятна коры, тёмные горизонтальные чечевички, отслоения
    float barkMask = smoothstep(0.43, 0.56, fbm(p*vec3(3.2,1.4,3.2) + 4.0));
    float lent = smoothstep(0.70, 0.86, vnoise(p*vec3(10.0,85.0,10.0)))
               * smoothstep(0.35, 0.75, vnoise(p*vec3(16.0,4.0,16.0)));
    float peel = fbm3(p*vec3(26.0,7.0,26.0));
    vec3 barkCol = mix(vec3(0.80,0.79,0.75), vec3(0.95,0.94,0.91), peel);
    barkCol = mix(barkCol, vec3(0.10,0.09,0.09), lent*0.9*barkMask);
    float barkEdge = smoothstep(0.39,0.43, fbm(p*vec3(3.2,1.4,3.2)+4.0)) - barkMask;

    // ---- лёд: крупные трещины, мелкая сетка, иней
    vec3 vor = voronoi(p*9.0);
    float cracks = 1.0 - smoothstep(0.0, 0.03, vor.y);
    vec3 vor2 = voronoi(p*31.0 + 3.0);
    float micro = 1.0 - smoothstep(0.0, 0.025, vor2.y);
    float frost = fbm(p*28.0);
    float frostCrust = smoothstep(0.60, 0.80, frost + frost_boost*0.3 + fres*0.15);

    // ---- пустота внутри: несколько слоёв снега на разной глубине
    vec3 Vo = normalize(mat3(p3d_ModelMatrixInverse) * V);
    vec3 interior = vec3(0.004, 0.007, 0.014);
    float depths[4] = float[](0.025, 0.05, 0.085, 0.13);
    float scales[4] = float[](16.0, 12.0, 9.0, 7.0);
    for(int k=0; k<4; k++){
        float d = depths[k] * mix(0.25, 1.0, inner_depth);
        vec3 q = p - Vo*d;
        float fl = snow_layer(q, time, scales[k], float(k)*1.7);
        float fade = 1.0 - float(k)*0.2;
        interior += vec3(0.62,0.70,0.85) * fl * fade * 0.9;
    }
    // слабый холодный «свет из глубины» у краёв полости
    interior += vec3(0.03,0.06,0.11) * pow(1.0-ndv, 1.5) * inner_depth;

    // ---- освещение оболочки
    float wrap = clamp((dot(N, L) + 0.35)/1.35, 0.0, 1.0);
    vec3 H = normalize(L + V);
    float spec = pow(clamp(dot(N, H), 0.0, 1.0), 60.0);
    float glint = step(0.993, hash13(floor(p*420.0))) * pow(clamp(dot(N, H), 0.0, 1.0), 6.0) * 3.0;

    vec3 iceCol = mix(vec3(0.30,0.44,0.62), vec3(0.86,0.93,1.0), frostCrust);
    vec3 shellCol = mix(iceCol, barkCol, barkMask);
    shellCol = mix(shellCol, vec3(0.95,0.97,1.0), micro*0.25 + barkEdge*0.6);

    float opacity = 0.05 + fres*0.85 + barkMask*0.75 + frostCrust*0.25 + micro*0.10 + cracks*0.20;

    // ---- пролом на спине (как на референсе): кора выломана, видно пустоту
    if(breach > 0.5){
        vec2 bp = vec2(p.x*1.15, (p.y - 1.86)*0.7);
        vec2 dir = bp / max(length(bp), 1e-4);
        float holeR = 0.065 + (fbm(vec3(dir*2.5, 1.0)) - 0.5)*0.09 + (vnoise(vec3(dir*9.0, 3.0)) - 0.5)*0.03;
        float back = smoothstep(0.0, -0.04, p.z);
        float hole = (1.0 - smoothstep(holeR-0.01, holeR, length(bp))) * back;
        float rim = (smoothstep(holeR-0.03, holeR, length(bp)) - smoothstep(holeR, holeR+0.025, length(bp))) * back;
        opacity = mix(opacity, 0.0, hole);
        shellCol = mix(shellCol, vec3(0.97,0.98,1.0), rim);
        opacity = max(opacity, rim*0.9);
    }
    opacity = clamp(opacity, 0.0, 1.0);

    vec3 lit = shellCol * (light_color*wrap*0.85 + vec3(0.10,0.13,0.18));
    lit += light_color * (spec*0.55 + glint);
    vec3 col = mix(interior, lit, opacity);

    // светящиеся трещины и холодная кайма
    col += vec3(0.45,0.75,1.0) * cracks * (0.05 + crack_glow*0.55) * (1.0-barkMask*0.7);
    col += vec3(0.55,0.75,1.0) * fres * 0.30;
    col += vec3(0.65,0.88,1.0) * edgeM * 2.0;

    float alpha = clamp(0.80 + fres*0.25 + barkMask*0.2, 0.0, 1.0);
    col = apply_fog(col, v_wpos);
    frag = vec4(col, alpha);
}
'''

# ------------------------------------------------------------------ лицо-зеркало
FACE_FRAG = '''#version 140
''' + NOISE + COMMON_UNIFORMS + '''
uniform sampler2D reflection;
uniform float has_reflection;
uniform float copy_amount;   // 0 — мутный лёд, 1 — чёткое «снятое» лицо
uniform float materialize;
in vec3 v_obj; in vec3 v_local; in vec3 v_wpos; in vec3 v_wnrm; in vec2 v_uv;
out vec4 frag;

void main(){
    vec3 p = v_obj;
    if(fbm3(p*6.0 + 2.0) > materialize*1.25 - 0.05) discard;

    vec3 N = normalize(v_wnrm);
    vec3 V = normalize(cam_pos - v_wpos);
    vec3 L = normalize(light_dir);
    float ndv = clamp(dot(N, V), 0.0, 1.0);
    float fres = pow(1.0 - ndv, 3.0);
    vec2 uv = v_uv;
    float r = length(uv*2.0 - 1.0);

    // замёрзшее зеркало: подо льдом отражение «плывёт» и размыто
    float clarity = mix(0.25, 1.0, copy_amount);
    vec2 warp = (vec2(fbm3(vec3(uv*5.0, 1.0)), fbm3(vec3(uv*5.0, 7.0))) - 0.5) * 0.07 * (1.0 - clarity*0.8);
    warp += vec2(sin(uv.y*30.0 + time*0.6), 0.0) * 0.0015;
    vec2 ruv = vec2(1.0 - uv.x, uv.y) + warp;       // зеркальное отражение
    ruv = (ruv - 0.5) * 0.92 + 0.5;
    float blur = mix(0.02, 0.003, clarity);
    vec3 refl = vec3(0.0);
    if(has_reflection > 0.5){
        refl += texture(reflection, ruv).rgb * 0.28;
        refl += texture(reflection, ruv + vec2( blur, 0.0)).rgb * 0.18;
        refl += texture(reflection, ruv + vec2(-blur, 0.0)).rgb * 0.18;
        refl += texture(reflection, ruv + vec2(0.0,  blur)).rgb * 0.18;
        refl += texture(reflection, ruv + vec2(0.0, -blur)).rgb * 0.18;
    } else {
        refl = mix(vec3(0.03,0.04,0.06), vec3(0.25,0.32,0.42), smoothstep(0.1, 0.9, uv.y));
    }
    float lum = dot(refl, vec3(0.299,0.587,0.114));
    refl = mix(vec3(lum)*vec3(0.80,0.90,1.05), refl, 0.45 + copy_amount*0.35);  // лёд «выпивает» цвет
    refl = refl * 1.25 + vec3(0.02,0.03,0.05);

    // иней по краям овала
    float edgeN = fbm(vec3(uv*9.0, 3.0));
    float frostMask = smoothstep(0.58, 1.0, r + (edgeN - 0.5)*0.55);
    float frostFine = fbm(vec3(uv*40.0, 9.0));
    vec3 frostCol = mix(vec3(0.70,0.80,0.92), vec3(0.97,0.99,1.0), frostFine);

    // несколько длинных трещин во льду
    vec3 cv = voronoi(vec3(uv*3.4, 0.37));
    float crack = (1.0 - smoothstep(0.0, 0.018, cv.y)) * step(0.45, cv.z) * smoothstep(0.2, 0.6, r);

    vec3 H = normalize(L + V);
    float spec = pow(clamp(dot(N, H), 0.0, 1.0), 120.0) * 1.4 + pow(clamp(dot(N, H), 0.0, 1.0), 12.0)*0.12;

    vec3 col = refl;
    col = mix(col, frostCol * (0.55 + 0.45*clamp(dot(N,L),0.0,1.0)), frostMask*0.9);
    col += vec3(0.8,0.9,1.0) * crack * 0.35;
    col += light_color * spec;
    col += vec3(0.6,0.8,1.0) * fres * 0.45;
    col = apply_fog(col, v_wpos);
    frag = vec4(col, 1.0);
}
'''

# ------------------------------------------------------------------ трещина на горле
CRACK_FRAG = '''#version 140
''' + NOISE + COMMON_UNIFORMS + '''
uniform float voice;        // 0..1 громкость голоса прямо сейчас
uniform float materialize;
in vec3 v_obj; in vec3 v_local; in vec3 v_wpos; in vec3 v_wnrm; in vec2 v_uv;
out vec4 frag;
void main(){
    if(materialize < 0.6) discard;
    float across = abs(v_uv.x*2.0 - 1.0);          // 0 — середина трещины
    float core = 1.0 - smoothstep(0.0, 0.55 - voice*0.35, across);
    float flick = 0.75 + 0.25*vnoise(vec3(v_uv.y*20.0, time*9.0, 0.0));
    vec3 deep = vec3(0.0, 0.0, 0.01);
    vec3 glow = vec3(0.55, 0.82, 1.0) * (0.08 + voice*2.2) * flick;
    vec3 col = mix(glow, deep, core*(1.0 - voice*0.4));
    float alpha = clamp(0.55 + core*0.45, 0.0, 1.0);
    frag = vec4(apply_fog(col, v_wpos), alpha);
}
'''

# ------------------------------------------------------------------ человеческая маска
MASK_FRAG = '''#version 140
''' + NOISE + COMMON_UNIFORMS + '''
uniform vec3 base_color;
uniform float is_skin;       // 1 — кожа (подповерхностное рассеяние), 0 — ткань
uniform float frost;         // 0..1 иней ползёт от горла и кистей
uniform float crack;         // 0..1 трещины
uniform float shatter;       // 0..1 куски осыпаются, под ними пустота
uniform float voice;         // подсказка: на горле маски мерцает трещинка
uniform vec3 throat_pos;     // в пространстве тела
uniform vec3 hand_r_pos;
uniform vec3 hand_l_pos;
in vec3 v_obj; in vec3 v_local; in vec3 v_wpos; in vec3 v_wnrm; in vec2 v_uv;
out vec4 frag;

vec3 void_col(vec3 p){
    vec3 v = voronoi(p*14.0 + vec3(0.0, time*0.8, 0.0));
    float fl = smoothstep(0.15, 0.02, v.x) * step(0.7, v.z);
    return vec3(0.004,0.006,0.012) + vec3(0.6,0.7,0.85)*fl*0.6;
}

void main(){
    vec3 p = v_obj;
    vec3 N = normalize(v_wnrm);
    vec3 V = normalize(cam_pos - v_wpos);
    vec3 L = normalize(light_dir);

    // изнанка маски — пустота
    if(!gl_FrontFacing){
        if(shatter <= 0.0 && crack <= 0.0) discard;
        frag = vec4(apply_fog(void_col(p), v_wpos), 1.0);
        return;
    }

    // ---- распространение инея
    float dS = min(distance(p, throat_pos), min(distance(p, hand_r_pos), distance(p, hand_l_pos)));
    float n = fbm(p*6.0);
    float front = frost*2.4 - dS - n*0.45;
    float fmask = smoothstep(0.0, 0.18, front);

    // ---- осколки: клетки вороного
    vec3 vor = voronoi(p*11.0);
    float cellT = vor.z*0.85 + clamp(dS, 0.0, 1.0)*0.15;
    if(shatter > 0.0 && cellT < shatter*1.15 - 0.1) discard;
    float aboutToFall = smoothstep(shatter*1.15 - 0.1 + 0.12, shatter*1.15 - 0.1, cellT) * step(0.001, shatter);

    // ---- обычный вид
    float diff = clamp(dot(N, L), 0.0, 1.0);
    float wrapd = clamp((dot(N, L) + 0.5)/1.5, 0.0, 1.0);
    vec3 albedo = base_color * (0.92 + 0.16*vnoise(p*60.0));
    vec3 col;
    if(is_skin > 0.5){
        vec3 sss = vec3(0.9, 0.35, 0.25) * (wrapd - diff) * 0.6;
        col = albedo * (light_color*diff + vec3(0.10,0.11,0.14)) + albedo*sss*light_color;
        vec3 H = normalize(L+V);
        col += light_color * pow(clamp(dot(N,H),0.0,1.0), 30.0) * 0.12;
    } else {
        float weave = 0.94 + 0.06*sin(p.x*900.0)*sin(p.y*900.0);
        col = albedo * weave * (light_color*wrapd*0.9 + vec3(0.08,0.09,0.12));
    }
    float rimL = pow(1.0 - clamp(dot(N,V),0.0,1.0), 3.0);
    col += vec3(0.25,0.32,0.45) * rimL * 0.25;

    // ---- иней поверх кожи
    float crystals = fbm(p*45.0);
    vec3 frostCol = mix(vec3(0.70,0.80,0.92), vec3(0.97,0.99,1.0), crystals);
    vec3 H = normalize(L+V);
    float glint = step(0.99, hash13(floor(p*500.0))) * pow(clamp(dot(N,H),0.0,1.0), 5.0) * 2.5;
    vec3 frosted = frostCol * (light_color*wrapd*0.9 + vec3(0.18,0.22,0.3)) + glint*light_color;
    col = mix(col, frosted, fmask * (0.55 + 0.45*smoothstep(0.4, 0.7, crystals + fmask*0.3)));
    // синеватый край фронта инея
    col += vec3(0.4,0.7,1.0) * (smoothstep(0.0,0.05,front) - smoothstep(0.05,0.2,front)) * 0.5 * step(0.001, frost);

    // ---- трещины: сквозь них видно пустоту
    float cw = 0.012 + crack*0.035;
    float edge = 1.0 - smoothstep(0.0, cw, vor.y);
    float crackAmt = edge * smoothstep(0.0, 0.4, crack) * fmask;
    col = mix(col, void_col(p), crackAmt);
    col += vec3(0.6,0.85,1.0) * (1.0 - smoothstep(cw, cw*1.8, vor.y)) * (1.0-edge) * crack * fmask * 0.45;
    col += vec3(0.7,0.9,1.0) * aboutToFall * 0.6;

    // ---- улика: тонкая трещинка на горле вспыхивает, когда «человек» говорит
    float lx = abs(p.x - throat_pos.x + (vnoise(vec3(p.y*90.0, 0.0, 0.0))-0.5)*0.008);
    float line = (1.0 - smoothstep(0.0, 0.0022, lx)) * (1.0 - smoothstep(0.02, 0.034, abs(p.y - throat_pos.y)))
               * step(throat_pos.z - 0.03, p.z);
    col = mix(col, vec3(0.6,0.85,1.0)*1.6, line * voice * 0.8);

    frag = vec4(apply_fog(col, v_wpos), 1.0);
}
'''

# ------------------------------------------------------------------ иней на земле
FROST_GROUND_VERT = '''#version 140
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelMatrix;
in vec4 p3d_Vertex;
in vec2 p3d_MultiTexCoord0;
out vec2 v_uv;
out vec3 v_wpos;
void main(){
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
    v_uv = p3d_MultiTexCoord0;
    v_wpos = (p3d_ModelMatrix * p3d_Vertex).xyz;
}
'''
FROST_GROUND_FRAG = '''#version 140
''' + NOISE + COMMON_UNIFORMS + '''
uniform float radius;       // текущий радиус инея (м)
uniform float decal_size;   // размер квадрата (м)
uniform float fade;         // 1 — свежий, 0 — растаял
uniform float seed;
in vec2 v_uv; in vec3 v_wpos;
out vec4 frag;
void main(){
    vec2 p = (v_uv - 0.5) * decal_size;
    float d = length(p);
    vec3 P = vec3(p, seed);
    float edgeN = fbm(P*1.4);
    float grow = radius - d + (edgeN - 0.5) * 0.9 * clamp(radius, 0.2, 1.5);
    float mask = smoothstep(0.0, 0.25, grow);
    if(mask <= 0.001) discard;

    // ветвистые «папоротники» инея, расходящиеся от центра
    vec2 dir = p / max(d, 1e-3);
    float fern = vnoise(vec3(dir*7.0, d*2.2 + seed));
    fern = pow(1.0 - abs(fern*2.0 - 1.0), 7.0);
    float fern2 = pow(1.0 - abs(vnoise(vec3(dir*19.0 + 3.0, d*5.0))*2.0 - 1.0), 9.0);
    vec3 cv = voronoi(vec3(p*5.0, seed));
    float plates = 1.0 - smoothstep(0.0, 0.04, cv.y);
    float haze = fbm(vec3(p*9.0, seed + 4.0));
    float crystal = clamp(fern*0.7 + fern2*0.5 + plates*0.45 + haze*0.35, 0.0, 1.0);

    float freshRim = smoothstep(0.0, 0.08, grow) - smoothstep(0.08, 0.35, grow);
    vec3 col = mix(vec3(0.55,0.68,0.85), vec3(0.95,0.98,1.0), crystal) * (light_color*0.55 + vec3(0.25,0.3,0.4));
    float spark = step(0.992, hash13(floor(vec3(p*160.0, seed)))) * (0.5 + 0.5*sin(time*3.0 + p.x*50.0));
    col += vec3(1.0) * spark * 1.2;
    col += vec3(0.5,0.75,1.0) * freshRim * 0.4;
    float alpha = mask * (0.22 + crystal*0.7) * fade;
    alpha *= smoothstep(decal_size*0.5, decal_size*0.42, d);
    frag = vec4(apply_fog(col, v_wpos), alpha);
}
'''


def _make(name, vert, frag):
    return Shader(name=name, language=Shader.GLSL, vertex=vert, fragment=frag)


shell_shader = _make('frost_shell', LIT_VERTEX, SHELL_FRAG)
face_shader = _make('frost_face', LIT_VERTEX, FACE_FRAG)
crack_shader = _make('frost_crack', LIT_VERTEX, CRACK_FRAG)
mask_shader = _make('frost_mask', LIT_VERTEX, MASK_FRAG)
frost_ground_shader = _make('frost_ground', FROST_GROUND_VERT, FROST_GROUND_FRAG)

GLOBAL_DEFAULTS = dict(
    time=0.0,
    cam_pos=(0, 1.6, 5),
    light_dir=(0.45, 0.8, 0.35),
    light_color=(0.80, 0.88, 1.0),
    fog_color=(0.02, 0.025, 0.04),
    fog_density=0.0,
    lamp_pos=(0, -100, 0),
    lamp_color=(1.0, 0.62, 0.28),
    lamp_power=0.0,
    rim_dir=(0, 0.3, -1),
    rim_color=(0, 0, 0),
    snow=0.0,
    snow_mask=1.0,
    cold_flush=0.0,
)
