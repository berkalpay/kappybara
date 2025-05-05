# For now this is just a test to see if the code runs, and doesn't test anything
# about correctness of results. In `test_rule.py` there are a few tests with simple
# models whose progression is entirely deterministic where we check that rule embeddings
# are being counted correctly, but when we want to test more complex models, see TODO below.
#
# TODO:
# At the level of `System`, when we're running whole models, I think correctness
# testing should start to look more like statistical tests on distributions over
# system state and observable counts w.r.t. to empirically known or analytically
# derived ground truths. This requires the example models/expected results which
# we're expecting from Walter. On the code side it also will probably end up
# requiring us to continue the effort to try to support the full Kappa language
# to make importing/testing these models more feasible. A non-exhaustive list of
# stuff we still need to implement in that regard:
# - Algebraic expressions (for example to be used in rate constants, see rule.py and rate.py)
# - Agent signatures
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

        for i in range(count):
            mixture.instantiate(pattern)

        # # TODO: If/when we implement isomorphic component tracking in a mixture,
        # # we can start using this version of the call.
        # mixture.instantiate(pattern, count)

    rules = [rule for rule_str in rules for rule in kappa.rules(rule_str)]
    system = System(mixture, rules)
    for obs in observables:
        system.add_observable(obs)

    counts = {obs: [] for obs in observables}

    for i in range(1000):
        system.update()

        for obs in observables:
            c = system.count_observable(obs)
            counts[obs].append(c)
