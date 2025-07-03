def routine_a():
    for _ in range(10000):
        s = "abcdef".replace("abc", "123")


def routine_b():
    for _ in range(10000):
        x = 1 + 1


def routine_c():
    for _ in range(1000):
        routine_a()
        routine_b()


if __name__ == "__main__":
    routine_c()
