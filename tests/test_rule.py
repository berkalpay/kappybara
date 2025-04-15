import pytest

from kappybara.pattern import Pattern, ComponentPattern
from kappybara.mixture import Mixture
from kappybara.rule import KappaRule, KappaRuleUnimolecular, KappaRuleBimolecular
from kappybara.system import System


@pytest.mark.parametrize(
    "test_case",
    [
        ("A(), B()", 10, "B(), A()", 100),
        ("A()", 10, "A(), A()", 100),  # No automorphism checks currently
        ("A(a[1]), B(b[1]), C()", 10, "A(a[1]), B(b[1]), C()", 100),
        ("A(a[1]), B(b[1]), C()", 10, "A(), B(), C()", 1000),
    ],
)
def test_basic_rule_n_embeddings(test_case):
    """
    Test embeddings of a basic KappaRule into a mixture
    """

    mixture_pattern_str, n_copies, rule_pattern_str, n_embeddings_expected = test_case
    mixture_pattern = Pattern.from_kappa(mixture_pattern_str)

    mixture = Mixture()
    for _ in range(n_copies):
        mixture.instantiate(mixture_pattern)
    # mixture.instantiate(mixture_pattern, n_copies) # This call won't work as intended right now

    rule_pattern = Pattern.from_kappa(rule_pattern_str)
    rule = KappaRule(rule_pattern, rule_pattern, 1.0)

    system = System()
    system.mixture = mixture

    system.add_rule(rule)

    assert rule.n_embeddings(system.mixture) == n_embeddings_expected


@pytest.mark.parametrize(
    "test_case",
    [
        ("A(), B()", 10, "B(), A()", 0),
        ("A(a[1]), B(b[1])", 10, "B(), A()", 10),
        ("A(a1[1]), B(b1[1], b2[2]), B(b1[2], b2[3]) A(a2[3])", 10, "B(), A()", 40),
    ],
)
def test_unimolecular_rule_n_embeddings(test_case):
    """
    Test embeddings of a basic KappaRule into a mixture
    """

    mixture_pattern_str, n_copies, rule_pattern_str, n_embeddings_expected = test_case
    mixture_pattern = Pattern.from_kappa(mixture_pattern_str)

    mixture = Mixture()
    for _ in range(n_copies):
        mixture.instantiate(mixture_pattern)
    # mixture.instantiate(mixture_pattern, n_copies) # This call won't work as intended right now

    rule_pattern = Pattern.from_kappa(rule_pattern_str)
    rule = KappaRuleUnimolecular(rule_pattern, rule_pattern, 1.0)

    system = System()
    system.mixture = mixture

    system.add_rule(rule)

    assert rule.n_embeddings(system.mixture) == n_embeddings_expected


@pytest.mark.parametrize(
    "test_case",
    [
        ("A(), B()", 10, "B(), A()", 100),
        ("A(a[1]), B(b[1])", 10, "B(), A()", 90),
    ],
)
def test_bimolecular_rule_n_embeddings(test_case):
    """
    Test embeddings of a basic KappaRule into a mixture
    """

    mixture_pattern_str, n_copies, rule_pattern_str, n_embeddings_expected = test_case
    mixture_pattern = Pattern.from_kappa(mixture_pattern_str)

    mixture = Mixture()
    for _ in range(n_copies):
        mixture.instantiate(mixture_pattern)
    # mixture.instantiate(mixture_pattern, n_copies) # This call won't work as intended right now

    rule_pattern = Pattern.from_kappa(rule_pattern_str)
    rule = KappaRuleBimolecular(rule_pattern, rule_pattern, 1.0)

    system = System()
    system.mixture = mixture

    system.add_rule(rule)

    assert rule.n_embeddings(system.mixture) == n_embeddings_expected


def test_simple_rule_application():
    """
    Test selection/application of a simple KappaRule in a mixture.
    """
    mixture_pattern_str = "A(a[1]), B(b[1])"
    n_copies = 10

    rule_left_str = "A(a[1]), B(b[1])"
    rule_right_str = "A(a[.]), B(b[.])"

    # observables_str = [rule_left_str, "A(a[.])", "B(b[#])"]
    observables_str = [rule_left_str, "A(a[.])", "B(b[#])"]

    mixture_pattern = Pattern.from_kappa(mixture_pattern_str)
    rule_left = Pattern.from_kappa(rule_left_str)
    rule_right = Pattern.from_kappa(rule_right_str)
    observables = [ComponentPattern.from_kappa(s) for s in observables_str]

    mixture = Mixture()
    for _ in range(n_copies):
        mixture.instantiate(mixture_pattern)
    # mixture.instantiate(mixture_pattern, n_copies) # This call won't work as intended right now

    rule = KappaRule(rule_left, rule_right, 1.0)

    system = System()
    system.mixture = mixture

    system.add_rule(rule)
    system.add_observables(observables)

    assert rule.n_embeddings(system.mixture) == n_copies
    assert system.count_observable(observables[0]) == n_copies
    assert system.count_observable(observables[1]) == 0

    update = rule.select(system.mixture)

    assert len(update.edges_to_remove) == 1

    for i in range(1, n_copies + 1):
        update = rule.select(system.mixture)
        system.mixture.apply_update(update)

        assert system.count_observable(observables[0]) == n_copies - i
        assert system.count_observable(observables[1]) == i
        assert system.count_observable(observables[2]) == n_copies


def test_rule_application():
    """
    Test selection/application of a simple KappaRule in a mixture.

    TODO: Checks on statistical uniformity of rule.select over valid embeddings (i.e. sample
    rule.select a bunch of times and check that the distribution is properly uniform over all
    possible embeddings).

    TODO: Support for empty slots (".") in pattern strings when instantiating from Lark.
    TODO: Supporting agent interfaces so we know a master list of sites for agents to be able to initialize defaults.
    """
    mixture_pattern_str = "A(a[1]), B(b[1], x[3]), C(c[2]{p}), D(d[2]{p}, x[3])"
    n_copies = 100

    rule_left_str = "A(a[1]), B(b[1], x[3]), C(c[2]{p}), D(d[2]{p}, x[3])"
    rule_right_str = "A(a[1]), B(b[.], x[3]), C(c[1]{u}), D(d[.]{p}, x[3])"

    observables_str = [rule_left_str, "A(a[1]), C(c[1])", "B(b[_])", "C(c{u})"]

    mixture_pattern = Pattern.from_kappa(mixture_pattern_str)
    rule_left = Pattern.from_kappa(rule_left_str)
    rule_right = Pattern.from_kappa(rule_right_str)
    observables = [ComponentPattern.from_kappa(s) for s in observables_str]

    mixture = Mixture()
    for _ in range(n_copies):
        mixture.instantiate(mixture_pattern)
    # mixture.instantiate(mixture_pattern, n_copies) # This call won't work as intended right now

    rule = KappaRule(rule_left, rule_right, 1.0)

    system = System()
    system.mixture = mixture

    system.add_rule(rule)
    system.add_observables(observables)

    assert rule.n_embeddings(system.mixture) == n_copies
    assert system.count_observable(observables[0]) == n_copies
    assert system.count_observable(observables[1]) == 0

    for i in range(1, n_copies + 1):
        update = rule.select(system.mixture)

        assert len(update.edges_to_remove) == 2
        assert len(update.edges_to_add) == 1
        assert len(update.agents_changed) == 1

        system.mixture.apply_update(update)

        assert system.count_observable(observables[0]) == n_copies - i
        assert system.count_observable(observables[1]) == i
        assert system.count_observable(observables[2]) == n_copies - i
        assert system.count_observable(observables[3]) == i
