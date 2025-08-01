import random
import warnings
from functools import cached_property
from typing import Optional, Iterable

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.figure

from kappybara.mixture import Mixture, ComponentMixture
from kappybara.rule import Rule, KappaRule, KappaRuleUnimolecular, KappaRuleBimolecular
from kappybara.pattern import Component
from kappybara.algebra import AlgExp


class System:
    mixture: Mixture
    rules: list[Rule]
    observables: list[Component]
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
        self.observables = [] if observables is None else list(observables)
        for observable in self.observables:
            self.mixture.track_component(observable)
        self.time = 0

    def _track_rule(self, rule: Rule) -> None:
        """Track any components mentioned in the left hand side of a `Rule`"""
        if isinstance(rule, KappaRule):
            for component in rule.left.components:
                # TODO: For efficiency check for isomorphism with already-tracked components
                self.mixture.track_component(component)

    def count_observable(self, obs: Component) -> int:
        try:
            embeddings = self.mixture.embeddings(obs)
        except KeyError:
            # Try to find an isomorphic observable if the specific one given isn't tracked
            try:
                tracked_obs = next((c for c in self.observables if c.isomorphic(obs)))
            except StopIteration as e:
                e.add_note(
                    f"No component isomorphic to observable `{obs}` has been declared"
                )
                raise
            embeddings = self.mixture.embeddings(tracked_obs)
        return len(embeddings)

    @cached_property
    def rule_reactivities(self) -> list[float]:
        return [rule.reactivity(self) for rule in self.rules]

    @property
    def reactivity(self) -> float:
        return sum(self.rule_reactivities)

    def wait(self) -> None:
        try:
            self.time += random.expovariate(self.reactivity)
        except ZeroDivisionError:
            warnings.warn(
                "system has no reactivity: infinite wait time", RuntimeWarning
            )

    def act(self) -> None:
        try:
            rule = random.choices(self.rules, weights=self.rule_reactivities)[0]
        except ValueError:
            warnings.warn("system has no reactivity: no rule applied", RuntimeWarning)
            return
        update = rule.select(self.mixture)
        if update is not None:
            self.mixture.apply_update(update)
            del self.__dict__["rule_reactivities"]

    def update(self) -> None:
        self.wait()
        self.act()


class KappaSystem(System):
    """
    A wrapper around a base `System` that allows for observables in
    the form of algebraic expressions.
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
        self.alg_exp_observables = alg_exp_observables or {}
        for name in self.alg_exp_observables:
            self._track_alg_exp(self.alg_exp_observables[name])
        self.variables = variables or {}
        for name in self.variables:
            self._track_alg_exp(self.variables[name])

    def _track_alg_exp(self, alg_exp: AlgExp) -> None:
        """
        Tracks the `Component`s in the given expression.

        NOTE: Does not track patterns nested by indirection: see
        the comment in the `filter` method.
        """
        for component_exp in alg_exp.filter("component_pattern"):
            component: Component = component_exp.attrs["value"]
            self.mixture.track_component(component)

    def eval_observable(self, obs_name: str) -> int | float:
        try:
            observable = self.alg_exp_observables[obs_name]
        except KeyError as e:
            e.add_note(f"Observable `{obs_name}` not defined")
            raise
        return observable.evaluate(self)

    def eval_variable(self, var_name: str) -> int | float:
        assert var_name in self.variables, f"Variable `{var_name}` not defined"
        return self.variables[var_name].evaluate(self)


class Monitor:
    system: KappaSystem
    history: dict[str, list[float]]

    def __init__(self, system: KappaSystem):
        self.system = system
        self.history = {"time": []} | {
            obs_name: [] for obs_name in system.alg_exp_observables
        }

    @cached_property
    def obs_names(self) -> list[str]:
        return list(self.system.alg_exp_observables.keys())

    def update(self) -> None:
        self.history["time"].append(self.system.time)
        for obs_name in self.obs_names:
            self.history[obs_name].append(self.system.eval_observable(obs_name))

    @property
    def dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(self.history)

    def plot(self) -> matplotlib.figure.Figure:
        fig, ax = plt.subplots()
        for obs_name in self.obs_names:
            ax.plot(self.history["time"], self.history[obs_name], label=obs_name)
        plt.legend()
        plt.xlabel("Time")
        plt.ylabel("Observable")
        plt.margins(0, 0)
        return fig
