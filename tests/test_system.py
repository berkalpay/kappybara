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
# - Agent signatures (see comments in Mixture.instantiate_agent in mixture.py)
from kappybara.system import System
from kappybara.pattern import Pattern
from kappybara.grammar import rule_from_kappa

def test_basic_system():
    system = System()

    # %init patterns used to initialize the mixture + their counts
    init_patterns = [("A(a[.], b[.])", 100)]

    rules = [
        "A(a[.]), A(a[.]) <-> A(a[1]), A(a[1]) @ 1.0 {2.0}, 1.0",
        "A(b[.]), A(b[.]) <-> A(b[1]), A(b[1]) @ 1.5, 1.0"
    ]

    for pair in init_patterns:
        pattern_str, count = pair
        pattern = Pattern.from_kappa(pattern_str)

        for i in range(count):
            system.instantiate_pattern(pattern)

        # # TODO: If/when we implement isomorphic component tracking in a mixture,
        # # we can start using this version of the call.
        # system.instantiate_pattern(pattern, count)

    for rule_str in rules:
        system.add_rule_from_kappa(rule_str)

    for i in range(1000):
        system.update()
