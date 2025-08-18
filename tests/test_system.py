import pytest
import os
import itertools

from kappybara.mixture import ComponentMixture
from kappybara.system import System
import kappybara.kappa as kappa
from kappybara.rule import AVOGADRO, DIFFUSION_RATE, kinetic_to_stochastic_on_rate
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

    mixture = ComponentMixture()
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


def test_system_from_kappa():
    system = kappa.system(
        """
    %def: "maxConsecutiveClash" "20"
    %def: "seed" "365457"

    // constants
    %var: 'x'     0.03
    %var: 'k_on'  'x' * 10
    %var: 'g_on'  'k_on' / 100

    %var: 'n' 3 * 100

    %init: 'n' A(a[1]{p}), B(b[1]{u})

    %obs: 'A_total'   |A()|
    %obs: 'A_u'       |A(a{u})|
    %obs: 'B_u'       |B(b{u})|
    %obs: 'A_p'       |A(a{p})|
    %obs: 'pairs'     |A(a[1]), B(b[1])|

    A(a{p}), B(b[_]) -> A(a{u}), B() @ 'g_on'
    """
    )
    n = system["n"]
    assert n == 300
    assert system["g_on"] == 0.003
    assert system["A_total"] == n

    for i in range(1, n):
        system.update()
        assert system["A_total"] == n
        assert system["A_u"] == i
        assert system["B_u"] == n
        assert system["A_p"] == n - i
        assert system["pairs"] == n


@pytest.mark.parametrize("k_on, expected", [(2.5e8, 65), (2.5e9, 331)])
def test_heterodimerization(k_on, expected):
    heterodimer = kappa.component("A(x[1]),B(x[1])")
    heterodimer_isomorphic = kappa.component("A(x[1]),B(x[1])")
    system = heterodimerization_system(k_on, heterodimer)

    n_heterodimers = []
    while system.time < 2:
        system.update()
        if system.time > 1:
            n_heterodimers.append(system.count_observable(heterodimer))
            assert n_heterodimers[-1] == system.count_observable(heterodimer_isomorphic)

    measured = sum(n_heterodimers) / len(n_heterodimers)
    assert abs(measured - expected) < expected / 5


@pytest.mark.skipif(os.getenv("GITHUB_ACTIONS") is not None, reason="requires KaSim")
@pytest.mark.parametrize("k_on, expected", [(2.5e8, 65), (2.5e9, 331)])
def test_heterodimerization_via_kasim(k_on, expected):
    heterodimer = kappa.component("A(x[1]),B(x[1])")
    heterodimer_isomorphic = kappa.component("A(x[1]),B(x[1])")
    system = heterodimerization_system(k_on, heterodimer)

    n_heterodimers = []
    system = system.updated_via_kasim(time=1)
    while system.time < 2:
        n_heterodimers.append(system.count_observable(heterodimer))
        assert n_heterodimers[-1] == system.count_observable(heterodimer_isomorphic)
        system = system.updated_via_kasim(time=0.1)

    measured = sum(n_heterodimers) / len(n_heterodimers)
    assert abs(measured - expected) < expected / 5


@pytest.mark.parametrize(
    "kd, a_init, b_init",
    itertools.product([10**-9], [2000], [2000, 3500]),
)
def test_equilibrium_matches_kd(kd, a_init, b_init):
    """
    Check that the input Kd matches what's observed empirically post-equilibrium
    within a relative margin of error.
    """
    volume = 10**-13
    on_rate = kinetic_to_stochastic_on_rate(volume=volume)
    kd = 10**-9
    off_rate = DIFFUSION_RATE * kd
    system = kappa.system(
        f"""
        %init: {a_init} A(x[.])
        %init: {b_init} B(x[.])
        %obs: 'A' |A(x[.])|
        %obs: 'B' |B(x[.])|
        %obs: 'AB' |B(x[_])|
        A(x[.]), B(x[.]) <-> A(x[1]), B(x[1]) @ {on_rate}, {off_rate}
        """
    )

    empirical_kds = []
    while system.time < 2:
        system.update()
        a_conc_eq = system["A"] / AVOGADRO / volume
        b_conc_eq = system["B"] / AVOGADRO / volume
        ab_conc_eq = system["AB"] / AVOGADRO / volume
        empirical_kds.append(a_conc_eq * b_conc_eq / ab_conc_eq)
    i = int(len(empirical_kds) * 0.5)  # an index post-equilibrium
    empirical_kd = sum(empirical_kds[i:]) / len(empirical_kds[i:])
    assert abs((empirical_kd - kd) / kd) < 0.1
