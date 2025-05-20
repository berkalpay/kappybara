import os
import random
import pytest

from kappybara.mixture import Mixture
from kappybara.system import System
import kappybara.kappa as kappa


def test_basic_system():
    # %init patterns used to initialize the mixture + their counts
    init_patterns = [("A(a[.], b[.])", 100)]

    rules = [
        "A(a[.]), A(a[.]) <-> A(a[1]), A(a[1]) @ 1.0 {2.0}, 1.0",
        "A(b[.]), A(b[.]) <-> A(b[1]), A(b[1]) @ 1.5, 1.0",
    ]

    observables = [
        kappa.component(o)
        for o in [
            "A(a[.])",
            "A(b[1]), A(b[1])",
            "A(a[1], b[.]), A(a[1], b[_])",
        ]
    ]

    mixture = Mixture()
    for pair in init_patterns:
        pattern_str, count = pair
        pattern = kappa.pattern(pattern_str)

        for _ in range(count):
            mixture.instantiate(pattern)

        # # TODO: If/when we implement isomorphic component tracking in a mixture,
        # # we can start using this version of the call.
        # mixture.instantiate(pattern, count)

    rules = [rule for rule_str in rules for rule in kappa.rules(rule_str)]
    system = System(mixture, rules, observables)

    counts = {obs: [] for obs in observables}

    for i in range(1000):
        system.update()

        for obs in observables:
            c = system.count_observable(obs)
            counts[obs].append(c)


@pytest.mark.parametrize("k_on, expected", [(2.5e8, 65), (2.5e9, 331)])
def test_heterodimerization(k_on, expected):
    random.seed(42)
    avogadro = 6.0221413e23
    volume = 2.25e-12  # mammalian cell volume
    n_a, n_b = 1000, 1000
    heterodimer = kappa.component("A(x[1]),B(x[1])")
    system = System(
        Mixture([kappa.pattern("A(x[.])")] * n_a + [kappa.pattern("B(x[.])")] * n_b),
        rules=[
            kappa.rule(
                f"A(x[.]), B(x[.]) -> A(x[1]), B(x[1]) @ {k_on / (avogadro * volume)}"
            ),
            kappa.rule(f"A(x[1]), B(x[1]) -> A(x[.]), B(x[.]) @ {2.5}"),
        ],
        observables=[heterodimer],
    )

    n_heterodimers = []
    while system.time < 2:
        system.update()
        if system.time > 1:
            n_heterodimers.append(system.count_observable(heterodimer))

    measured = sum(n_heterodimers) / len(n_heterodimers)
    assert abs(measured - expected) < expected / 5
