from kappybara.examples import heterodimerization_system


if __name__ == "__main__":
    system = heterodimerization_system(2.5e9)
    while system.time < 2:
        system.update()
