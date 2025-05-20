import random
from functools import cached_property
from typing import Optional, Iterable

from kappybara.mixture import Mixture
from kappybara.rule import Rule, KappaRule
from kappybara.pattern import Component
from kappybara.alg_exp import AlgExp


class System:
    mixture: Mixture
    rules: list[Rule]
    time: float

    def __init__(
        self,
        mixture: Optional[Mixture] = None,
        rules: Optional[Iterable[Rule]] = None,
        observables: Optional[Iterable[Component]] = None,
    ):
        self.mixture = Mixture() if mixture is None else mixture
        self.rules = [] if rules is None else list(rules)
        for rule in self.rules:
            self._add_rule(rule)
        if observables is not None:
            for observable in observables:
                self.mixture.track_component(observable)
        self.time = 0

    def _add_rule(self, rule: Rule) -> None:
        """
        NOTE: Right now an overarching assumption is that the mixture will be fully initialized
        before any rules or observables are added. But stuff like interventions which instantiate
        the mixture when the simulation is already underway and rules are already declared might
        require us to rethink things a bit.
        """
        if isinstance(rule, KappaRule):
            for component in rule.left.components:
                # TODO: Efficiency thing: check for isomorphism with existing components
                #       Create a surjective map from *all* components to set of unique components
                self.mixture.track_component(component)

    def count_observable(self, obs: Component) -> int:
        """
        NOTE: Must provide with the exact same observable as you set to track.
        Ismorphic components aren't recognized.
        """
        return len(self.mixture.embeddings(obs))

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
