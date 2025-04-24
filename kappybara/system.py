from typing import Iterable
from dataclasses import dataclass
import random

from kappybara.mixture import Mixture
from kappybara.rule import Rule, KappaRule
from kappybara.pattern import Component, Pattern
from kappybara.grammar import rules_from_kappa


class System:
    mixture: Mixture
    rules: list[Rule]
    rule_reactivities: list[float]
    time: float

    def __init__(self):
        self.mixture = Mixture()
        self.rules = []
        self.rule_reactivities = []
        self.time = 0

    @property
    def reactivity(self) -> float:
        for i, rule in enumerate(self.rules):
            self.rule_reactivities[i] = rule.reactivity(self)

        return sum(self.rule_reactivities)

    def wait(self):
        self.time += random.expovariate(self.reactivity)

    def act(self):
        rule: Rule = random.choices(self.rules, weights=self.rule_reactivities)[0]
        update: Optional[MixtureUpdate] = rule.select(self.mixture)

        if update:
            self.mixture.apply_update(update)
        else:
            # TODO: should error if too many consecutive null events occur
            print("Null event")

    def update(self):
        self.wait()
        self.act()

    def instantiate_pattern(self, pattern: Pattern, n_copies=1):
        self.mixture.instantiate(pattern, n_copies)

    def add_observables(self, observables: Iterable[Component]):
        for obs in observables:
            self.add_observable(obs)

    def add_observable(self, obs: Component):
        """
        NOTE: Currently, to retrieve the counts of an observable registered
        through this method, you must provide `count_observable` with the exact
        same object you gave to this method call. An isomorphic but non-identical
        (i.e. different memory address) `Component` currently will not work
        unless it also got registered through this call.
        """
        assert isinstance(obs, Component), "An observable must be a single Component"

        self.mixture.track_component(obs)

    def count_observable(self, obs: Component):
        return len(self.mixture.fetch_embeddings(obs))

    def add_rule(self, rule: Rule):
        """
        NOTE: Right now an overarching assumption is that the mixture will be fully initialized
        before any rules or observables are added. But stuff like interventions which instantiate
        the mixture when the simulation is already underway and rules are already declared might
        require us to rethink things a bit.
        """
        self.rules.append(rule)
        self.rule_reactivities.append(None)

        if isinstance(rule, KappaRule):
            for component in rule.left.components:
                # TODO: Efficiency thing: check for isomorphism with existing components
                #       Create a surjective map from *all* components to set of unique components
                self.mixture.track_component(component)

    def add_rule_from_kappa(self, rule_str: str):
        rules = rules_from_kappa(rule_str)

        for rule in rules:
            self.add_rule(rule)
