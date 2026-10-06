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