grid = [
    ["#", "#", "#","#","#"],
    ["#", ".", ".",".","#"],
    ["#", ".", "#", ".", "#"],
    ["#", ".", ".",".","#"],
    ["#", "#", "#","#","#"],
]

def is_free(grid, row, col):
    return grid[row][col] == "."

for row in grid:
    print("".join(row))

print(is_free(grid, 1, 1))
print(is_free(grid, 0, 0))
print(is_free(grid, 2, 2))
player_row = 0
player_col = 0
for r in range(5):
    line = ""
    for c in range(5):
        if r == player_row and c == player_col:
            line = line + "@"
        else:
            line = line + grid[r][c]
    print(line)              # отступ 4 пробела: после цикла по клеткам