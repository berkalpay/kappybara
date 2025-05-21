import pytest

from kappybara.mixture import Mixture
from kappybara.system import System
import kappybara.kappa as kappa
from kappybara.examples import heterodimerization_system


def test_basic_system():
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
    rules = [rule for rule_str in rules for rule in kappa.rules(rule_str)]
    system = System(mixture, rules, observables)

    counts = {obs: [] for obs in observables}
    for _ in range(1000):
        system.update()
        for obs in observables:
            c = system.count_observable(obs)
            counts[obs].append(c)


@pytest.mark.parametrize("k_on, expected", [(2.5e8, 65), (2.5e9, 331)])
def test_heterodimerization(k_on, expected):
    heterodimer = kappa.component("A(x[1]),B(x[1])")
    system = heterodimerization_system(k_on, heterodimer)

    n_heterodimers = []
    while system.time < 2:
        system.update()
        if system.time > 1:
            n_heterodimers.append(system.count_observable(heterodimer))

    measured = sum(n_heterodimers) / len(n_heterodimers)
    assert abs(measured - expected) < expected / 5
