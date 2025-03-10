import kappybara  # Just testing that the import works


def loop_a():
    for i in range(10):
        for i in range(200000):
            pass
        loop_b()


def loop_b():
    for i in range(10):
        for i in range(20000):
            pass

        loop_c()


def loop_c():
    for i in range(50000):
        pass


if __name__ == "__main__":
    loop_a()
