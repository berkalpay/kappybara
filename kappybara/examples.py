import random

from kappybara.pattern import Component
from kappybara.mixture import Mixture
from kappybara.system import System
import kappybara.kappa as kappa


def heterodimerization_system(k_on: float, observable: Component) -> System:
    random.seed(42)
    avogadro = 6.0221413e23
    volume = 2.25e-12  # mammalian cell volume
    n_a, n_b = 1000, 1000
    return System(
        Mixture([kappa.pattern("A(x[.])")] * n_a + [kappa.pattern("B(x[.])")] * n_b),
        rules=[
            kappa.rule(
                f"A(x[.]), B(x[.]) -> A(x[1]), B(x[1]) @ {k_on / (avogadro * volume)}"
            ),
            kappa.rule(f"A(x[1]), B(x[1]) -> A(x[.]), B(x[.]) @ {2.5}"),
        ],
        observables=[observable],
    )
