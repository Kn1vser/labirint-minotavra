import random

secret = random.randint(1, 100)
attempts = 0

while True:
    guess = int(input("Ваш вариант: "))
    attempts = attempts + 1

    if guess > secret:
        print("Меньше")
    elif guess < secret:
        print("Больше")
    else:
        print("Угадал за", attempts, "попыток")
        break