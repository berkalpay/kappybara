import kappybara.kappa as kappa
from kappybara.examples import heterodimerization_system


def heterodimerization() -> None:
    system = heterodimerization_system(2.5e9, kappa.component("A(x[1]),B(x[1])"))
    while system.time < 2:
        system.update()


if __name__ == "__main__":
    system = heterodimerization_system(2.5e9, kappa.component("A(x[1]),B(x[1])"))
    while system.time < 2:
        system.update()
