import random
from functools import cached_property
from typing import Optional, Iterable

from kappybara.mixture import Mixture, ComponentMixture
from kappybara.rule import Rule, KappaRule, KappaRuleUnimolecular, KappaRuleBimolecular
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
            self._track_rule(rule)
        if observables is not None:
            for observable in observables:
                self.mixture.track_component(observable)
        self.time = 0

    def _track_rule(self, rule: Rule) -> None:
        """
        Track any components mentioned in the left hand side of a `Rule`
        """
        if isinstance(rule, KappaRule):
            for component in rule.left.components:
                # TODO: Efficiency thing: check for isomorphism with existing components
                #       Create a surjective map from *all* components to set of unique components
                self.mixture.track_component(component)

    def count_observable(self, obs: Component) -> int:
        """
        NOTE: You must query with the same object in memory that you provided in the constructor.
        Ismorphic components aren't recognized.
        """
        assert type(obs) is Component
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
        # print(rule.left.components)
        update = rule.select(self.mixture)
        if update is not None:
            self.mixture.apply_update(update)
            del self.__dict__["rule_reactivities"]

    def update(self) -> None:
        self.wait()
        self.act()


class KappaSystem(System):
    """
    A wrapper around a base `System` that allows for more expressive observables
    in the form of an `AlgExp`.
    """

    alg_exp_observables: dict[str, AlgExp]
    variables: dict[str, AlgExp]

    def __init__(
        self,
        mixture: Optional[ComponentMixture] = None,
        rules: Optional[Iterable[Rule]] = None,
        alg_exp_observables: Optional[dict[str, AlgExp]] = None,
        variables: Optional[dict[str, AlgExp]] = None,
    ):
        if mixture is None:
            self.mixture = (
                ComponentMixture()
                if any(
                    type(r) in [KappaRuleUnimolecular, KappaRuleBimolecular]
                    for r in rules
                )
                else Mixture()
            )
        else:
            self.mixture = mixture

        super().__init__(mixture, rules, None)

        if alg_exp_observables:
            for name in alg_exp_observables:
                self._track_alg_exp(alg_exp_observables[name])
        if variables:
            for name in variables:
                self._track_alg_exp(variables[name])

        self.alg_exp_observables = alg_exp_observables or {}
        self.variables = variables or {}

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

    def eval_observable(self, obs_name: str) -> int | float:
        assert type(obs_name) is str
        assert (
            obs_name in self.alg_exp_observables
        ), f"Observable `{obs_name}` not defined"
        return self.alg_exp_observables[obs_name].evaluate(self)

    def eval_variable(self, var_name: str) -> int | float:
        assert var_name in self.variables, f"Variable `{var_name}` not defined"
        return self.variables[var_name].evaluate(self)
