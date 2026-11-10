"""
Звуки, синтезированные кодом (numpy -> wav). Файлы создаются при первом запуске в папке sounds/.

    from monsters.sfx import ensure_sounds
    ensure_sounds()            # вернёт папку; дальше Audio('wind', loop=True) и т.д.
"""
import wave
from pathlib import Path

import numpy as np

SR = 22050
FOLDER = Path(__file__).resolve().parent.parent / 'sounds'


def _save(name, x):
    x = np.clip(x, -1, 1)
    with wave.open(str(FOLDER / f'{name}.wav'), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype(np.int16).tobytes())


def _lowpass(x, k):
    """Простейший фильтр: скользящее среднее длиной k (несколько проходов — мягче)."""
    ker = np.ones(k) / k
    return np.convolve(np.convolve(x, ker, 'same'), ker, 'same')


def _loopable(x, fade):
    """Сшивает конец с началом, чтобы зацикленный звук не щёлкал."""
    n = len(x) - fade
    k = np.linspace(0, 1, fade)
    out = x[:n].copy()
    out[:fade] = x[:fade] * k + x[n:n + fade] * (1 - k)
    return out


def _t(sec):
    return np.arange(int(SR * sec)) / SR


def make_all(rng=None):
    rng = rng or np.random.default_rng(7)
    # ветер: шум, медленно «дышащий» по громкости и тембру
    t = _t(9.0)
    n = rng.normal(0, 1, len(t))
    low, mid = _lowpass(n, 180), _lowpass(n, 40)
    gust = 0.55 + 0.45 * np.sin(2 * np.pi * t / 4.5 + 1.0) * np.sin(2 * np.pi * t / 9.0)
    wind = (low * 5.0 + mid * 1.6 * gust) * (0.5 + 0.5 * gust)
    _save('wind', _loopable(wind / np.abs(wind).max() * 0.6, SR))
    # шаги по снегу: короткий хруст
    for i in range(4):
        t = _t(0.22)
        n = rng.normal(0, 1, len(t))
        crunch = (n - _lowpass(n, 6)) * np.exp(-t * 22) + _lowpass(n, 30) * np.exp(-t * 40) * 3
        grains = (rng.random(len(t)) > 0.985) * rng.normal(0, 3, len(t)) * np.exp(-t * 15)
        x = crunch * 0.5 + _lowpass(grains, 3)
        _save(f'step{i}', x / np.abs(x).max() * 0.5)
    # сердцебиение: два глухих удара
    t = _t(0.9)
    beat = lambda t0, f: np.sin(2 * np.pi * f * (t - t0)) * np.exp(-np.clip(t - t0, 0, None) * 28) * (t >= t0)  # noqa: E731
    hb = beat(0.02, 52) + 0.75 * beat(0.27, 46)
    _save('heart', hb / np.abs(hb).max() * 0.9)
    # её шёпот/дыхание: шипящий шум с «слогами»
    t = _t(4.0)
    n = rng.normal(0, 1, len(t))
    hiss = n - _lowpass(n, 5)
    syll = np.clip(np.sin(2 * np.pi * 2.3 * t + 1.5 * np.sin(2 * np.pi * 0.7 * t)), 0, 1) ** 2
    wh = _lowpass(hiss, 3) * syll * (0.6 + 0.4 * np.sin(2 * np.pi * 0.25 * t))
    _save('whisper', _loopable(wh / np.abs(wh).max() * 0.5, SR // 2))
    # «заметила»: низкий нарастающий диссонанс
    t = _t(2.4)
    st = sum(np.sin(2 * np.pi * f * t * (1 + 0.02 * t)) for f in (55, 58.3, 82.4, 87.3)) * np.minimum(t / 1.6, 1) ** 2 * np.exp(-np.clip(t - 1.8, 0, None) * 5)
    st += _lowpass(rng.normal(0, 1, len(t)), 60) * 4 * (t / 2.4) ** 3
    _save('sting', st / np.abs(st).max() * 0.8)
    # подобрал варежку: тихий колокольчик
    t = _t(1.2)
    bell = sum(np.sin(2 * np.pi * f * t) * np.exp(-t * d) for f, d in ((880, 4), (1320, 6), (1760, 9), (2640, 12)))
    _save('pickup', bell / np.abs(bell).max() * 0.45)
    # поймала: глухой удар и провал
    t = _t(1.6)
    hit = np.sin(2 * np.pi * 40 * t * np.exp(-t * 1.2)) * np.exp(-t * 3) + _lowpass(rng.normal(0, 1, len(t)), 25) * 3 * np.exp(-t * 9)
    _save('caught', hit / np.abs(hit).max() * 0.95)
    # щелчок фонаря
    t = _t(0.05)
    _save('click', rng.normal(0, 1, len(t)) * np.exp(-t * 160) * 0.5)
    # победа: тёплый аккорд
    t = _t(3.0)
    ch = sum(np.sin(2 * np.pi * f * t) for f in (261.6, 329.6, 392.0, 523.3)) * np.minimum(t / 0.3, 1) * np.exp(-t * 1.1)
    _save('win', ch / np.abs(ch).max() * 0.5)


NAMES = ['wind', 'step0', 'step1', 'step2', 'step3', 'heart', 'whisper', 'sting', 'pickup', 'caught', 'click', 'win']


def ensure_sounds():
    FOLDER.mkdir(exist_ok=True)
    if not all((FOLDER / f'{n}.wav').exists() for n in NAMES):
        make_all()
    return FOLDER
