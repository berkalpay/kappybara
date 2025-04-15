from typing import Iterable
from dataclasses import dataclass

from kappybara.mixture import Mixture
from kappybara.chemistry import Rule
from kappybara.rule import KappaRule
from kappybara.pattern import SitePattern, AgentPattern, ComponentPattern, Pattern


class System:
    mixture: Mixture
    rules: list[Rule]
    rule_reactivities: dict[Rule, float]

    def __init__(self):
        self.mixture = Mixture()
        self.rules = []

    def reactivity(self) -> float:
        for rule in self.rules:
            self.rule_reactivities[rule] = rule.reactivity(self)

        return sum(self.rule_reactivities.values())

    def add_rule(self, rule: Rule):
        self.rules.append(rule)

        if isinstance(rule, KappaRule):
            for component in rule.left.components:
                # TODO: Efficiency thing: check for isomorphism with existing components
                #       Create a surjective map from *all* components to set of unique components
                self.mixture.track_component_pattern(component)

    def add_observables(self, observables: Iterable[ComponentPattern]):
        for obs in observables:
            self.add_observable(obs)

    def add_observable(self, obs: ComponentPattern):
        assert isinstance(
            obs, ComponentPattern
        ), "An observable must be a single ComponentPattern"

        self.mixture.track_component_pattern(obs)

    def count_observable(self, obs: ComponentPattern):
        return len(self.mixture.fetch_embeddings(obs))
