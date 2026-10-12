grid = [
    ["#", "#", "#", "#", "#"],
    ["#", ".", ".", ".", "#"],
    ["#", ".", "#", "E", "#"],
    ["#", ".", ".", ".", "#"],
    ["#", "#", "#", "#", "#"],
]

def is_free(grid, row, col):
    if row < 0 or col < 0 or row >= len(grid) or col >= len(grid[0]):
        return False
    return grid[row][col] in (".", "E")

player_row = 1
player_col = 1

while True:
    # 1. Рисуем карту
    for r in range(5):
        line = ""
        for c in range(5):
            if r == player_row and c == player_col:
                line = line + "@"
            else:
                line = line + grid[r][c]
        print(line)

    # 2. Спрашиваем ход
    move = input("Ход (w/a/s/d, q - выход): ")
    if move == "q":
        break

    # 3. Считаем, куда шагнуть
    new_row = player_row
    new_col = player_col
    if move == "w":
        new_row = player_row - 1
    elif move == "s":
        new_row = player_row + 1
    elif move == "a":
        new_col = player_col - 1
    elif move == "d":
        new_col = player_col + 1

    # 4. Шагаем, если свободно
    if is_free(grid, new_row, new_col):
        player_row = new_row
        player_col = new_col

        if grid[player_row][player_col] == "E":
            print("Вы достигли выхода! Поздравляем!")
            break
    else:
        print("Там стена!")