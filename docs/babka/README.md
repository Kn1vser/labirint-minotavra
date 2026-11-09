# Бабка

Враг по фото-референсу: измождённая старуха в длинном грязном покрывале сидит на ступеньке
крыльца у тёмной двери, закрыв рот ладонями, и смотрит на тебя поверх пальцев.

- Подойдёшь ближе 9 м — медленно встаёт. Она выше человека (2.1 м), руки и пальцы длинные.
- Идёт следом, не отнимая ладоней от лица. Голос глухой, из-под ладоней: «…тише…», «Посиди со мной…».
- Когда хватает — опускает руки. Рта под ними нет, только гладкая кожа.
- Свет фонаря: закрывает глаза ладонями и замирает на пару секунд.
- В демо включена постобработка «старая фотография»: сепия, зерно, виньетка (P — выкл).

![hero](hero.png)
![states](states.png)
![turnaround](turnaround.png)

## Запуск

```bash
pip install ursina
python babka_demo.py            # от первого лица: WASD, Shift — бег, F — фонарь, P — сепия, Tab — свободная камера
python tools/render_babka.py    # перерисовать картинки
```

## В игре

```python
from monsters.babka import Babka
from monsters.porch import build_porch

build_porch(position=(0, 0, 9), rotation_y=180)
b = Babka(position=(0, 0, 9), rotation_y=180, target=player_head, sitting=True)
b.on_say = show_subtitle
b.on_catch = game_over
b.flash()                       # игрок посветил фонарём
b.state                         # sit / rise / patrol / notice / chase / grab / caught / stunned / search
```

| Файл | Что внутри |
|---|---|
| `monsters/babka_mesh.py` | худое лицо (впалые щёки, глазницы), покрывало, платье (сидя/стоя), длинные руки |
| `monsters/babka_shaders.py` | лён с грязью и рваным краем, старая кожа, мутные глаза, сепия-постобработка |
| `monsters/babka.py` | поведение, IK рук (ладони на лицо), посадка/подъём |
| `monsters/porch.py` | крыльцо избы с тёмным проёмом |
