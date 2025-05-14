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
    observables: dict[str, AlgExp]
    variables: dict[str, AlgExp]

    def __init__(
        self,
        mixture: Optional[Mixture] = None,
        rules: Optional[Iterable[Rule]] = None,
        observables: Optional[dict[str, AlgExp]] = None,
        variables: Optional[dict[str, AlgExp]] = None,
    ):
        self.mixture = Mixture() if mixture is None else mixture
        self.rules = [] if rules is None else list(rules)
        for rule in self.rules:
            self._track_rule(rule)
        if observables:
            for name in observables:
                self._track_alg_exp(observables[name])
        if variables:
            for name in variables:
                self._track_alg_exp(variables[name])

        self.observables = observables if observables else {}
        # TODO: once we support pattern counts in variables, make sure to check for those and track them
        self.variables = variables if variables else {}
        self.time = 0

    def _track_alg_exp(self, alg_exp: AlgExp) -> None:
        """
        Tracks the `Component`s which existing in `obs`.

        NOTE: Does not track patterns nested by indirection in `obs`, see
        the comment in the `filter` method.
        """
        filtered: list[AlgExp] = alg_exp.filter("component_pattern")

        for component_exp in filtered:
            component: Component = component_exp.attrs["value"]
            self.mixture.track_component(component)

    def _track_rule(self, rule: Rule) -> None:
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

    def count_observable(self, name: str) -> int:
        assert name in self.observables, f"Undeclared observable: {name}"
        obs: AlgExp = self.observables[name]

        return obs.evaluate(self)

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
