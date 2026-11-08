# Монстр «Таёжный Двойник»
# Картинка: assets/monsters/taezhny_dvoynik.png
#
# Живёт в глухой тайге. Носит куртку и ушанку, снятые с пропавшего охотника.
# Повторяет каждый шаг человека и зовёт его голосами людей, которых тот знает.
# Если откликнуться и подойти — Двойник занимает твоё место.
#
# Правила: Двойник делает тот же ход, что и ты (если там не стена).
# Используй стены, чтобы оторваться от него, и дойди до выхода E.
import random

grid = [
    ["#", "#", "#", "#", "#", "#", "#"],
    ["#", ".", ".", ".", "#", ".", "#"],
    ["#", ".", "#", ".", ".", ".", "#"],
    ["#", ".", "#", "#", "#", ".", "#"],
    ["#", ".", ".", ".", "#", ".", "#"],
    ["#", "#", "#", ".", ".", "E", "#"],
    ["#", "#", "#", "#", "#", "#", "#"],
]

monster = {
    "name": "Таёжный Двойник",
    "symbol": "M",
    "image": "assets/monsters/taezhny_dvoynik.png",
    "phrases": [
        "Эй! Ты где? Иди сюда!",
        "Это я... помоги мне...",
        "Не уходи, тут тропинка!",
        "Ау-у-у!",
    ],
}

DIRECTIONS = {"w": (-1, 0), "s": (1, 0), "a": (0, -1), "d": (0, 1)}


def is_free(grid, row, col):
    if row < 0 or col < 0 or row >= len(grid) or col >= len(grid[0]):
        return False
    return grid[row][col] in (".", "E")


player_row, player_col = 1, 1
monster_row, monster_col = 1, 5

print("Ночь. Тайга. Где-то рядом бродит " + monster["name"] + ".")
print("Он повторяет каждый твой шаг. Не дай ему подойти!\n")

while True:
    # 1. Рисуем карту
    for r in range(len(grid)):
        line = ""
        for c in range(len(grid[0])):
            if r == player_row and c == player_col:
                line = line + "@"
            elif r == monster_row and c == monster_col:
                line = line + monster["symbol"]
            else:
                line = line + grid[r][c]
        print(line)

    # 2. Спрашиваем ход
    move = input("Ход (w/a/s/d, q - выход): ")
    if move == "q":
        break
    if move not in DIRECTIONS:
        print("Не понимаю такой ход.")
        continue

    dr, dc = DIRECTIONS[move]

    # 3. Шагает игрок
    if is_free(grid, player_row + dr, player_col + dc):
        player_row += dr
        player_col += dc
    else:
        print("Там стена!")

    if grid[player_row][player_col] == "E":
        print("Ты выбрался из тайги! Двойник остался среди деревьев...")
        break

    # 4. Двойник копирует твой ход
    if is_free(grid, monster_row + dr, monster_col + dc):
        monster_row += dr
        monster_col += dc

    # 5. Поймал?
    if monster_row == player_row and monster_col == player_col:
        print("Перед тобой стоит кто-то в твоей куртке... и улыбается твоим лицом.")
        print("Двойник поймал тебя. Игра окончена.")
        break

    # 6. Иногда зовёт человеческим голосом
    if random.random() < 0.3:
        print('Из темноты: "' + random.choice(monster["phrases"]) + '"')
