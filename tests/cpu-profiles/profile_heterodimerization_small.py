from kappybara.pattern import Component
from kappybara.examples import heterodimerization_system


if __name__ == "__main__":
    system = heterodimerization_system(2.5e9, Component.from_kappa("A(x[1]),B(x[1])"))
    while system.time < 2:
        system.update()
