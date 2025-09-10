import random

from kappybara.pattern import Component
from kappybara.system import System


def heterodimerization_system(k_on: float = 2.5e9) -> System:
    random.seed(42)
    avogadro = 6.0221413e23
    volume = 2.25e-12  # mammalian cell volume
    n_a, n_b = 1000, 1000
    return System.from_kappa(
        {"A(x[.])": n_a, "B(x[.])": n_b},
        rules=[
            f"A(x[.]), B(x[.]) -> A(x[1]), B(x[1]) @ {k_on / (avogadro * volume)}",
            "A(x[1]), B(x[1]) -> A(x[.]), B(x[.]) @ 2.5",
        ],
        observables=[f"|A(x[1]),B(x[1])|"],
    )
