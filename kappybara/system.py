import random
from functools import cached_property
from typing import Optional, Iterable

from kappybara.mixture import Mixture
from kappybara.rule import Rule, KappaRule
from kappybara.pattern import Component, Pattern


class System:
    mixture: Mixture
    rules: list[Rule]
    time: float

    def __init__(
        self, mixture: Optional[Mixture] = None, rules: Optional[Iterable[Rule]] = None
    ):
        self.mixture = Mixture() if mixture is None else mixture
        self.rules = []
        if rules is not None:
            for rule in rules:
                self._add_rule(rule)
        self.time = 0

    def _add_rule(self, rule: Rule) -> None:
        """
        NOTE: Right now an overarching assumption is that the mixture will be fully initialized
        before any rules or observables are added. But stuff like interventions which instantiate
        the mixture when the simulation is already underway and rules are already declared might
        require us to rethink things a bit.
        """
        self.rules.append(rule)
        if isinstance(rule, KappaRule):
            for component in rule.left.components:
                # TODO: Efficiency thing: check for isomorphism with existing components
                #       Create a surjective map from *all* components to set of unique components
                self.mixture.track_component(component)

    @cached_property
    def rule_reactivities(self) -> list[float]:
        return [rule.reactivity(self) for rule in self.rules]

    @property
    def reactivity(self) -> float:
        return sum(self.rule_reactivities)

    def wait(self) -> None:
        self.time += random.expovariate(self.reactivity)

    def act(self) -> None:
        # TODO: warn after many consecutive null events?
        rule = random.choices(self.rules, weights=self.rule_reactivities)[0]
        update = rule.select(self.mixture)
        if update is not None:
            self.mixture.apply_update(update)
            del self.__dict__["rule_reactivities"]

    def update(self) -> None:
        self.wait()
        self.act()

    def instantiate_pattern(self, pattern: Pattern, n_copies=1) -> None:
        self.mixture.instantiate(pattern, n_copies)

    def add_observables(self, observables: Iterable[Component]) -> None:
        for obs in observables:
            self.add_observable(obs)

    def add_observable(self, obs: Component) -> None:
        """
        NOTE: Currently, to retrieve the counts of an observable registered
        through this method, you must provide `count_observable` with the exact
        same object you gave to this method call. An isomorphic but non-identical
        (i.e. different memory address) `Component` currently will not work
        unless it also got registered through this call.
        """
        assert isinstance(obs, Component), "An observable must be a single Component"
        self.mixture.track_component(obs)

    def count_observable(self, obs: Component) -> int:
        return len(self.mixture.embeddings(obs))
