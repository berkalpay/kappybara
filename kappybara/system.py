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
    observables: dict[str, Component | AlgExp]
    variables: Optional[dict[str, AlgExp]] = None
    time: float

    def __init__(
        self,
        mixture: Optional[Mixture] = None,
        rules: Optional[Iterable[Rule]] = None,
        observables: Optional[list[Component] | dict[str, Component | AlgExp]] = None,
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

        self.rules = [] if rules is None else list(rules)
        for rule in self.rules:
            self._track_rule(rule)

        if observables is None:
            self.observables = {}
        elif isinstance(observables, list):
            self.observables = {str(i): obs for i, obs in enumerate(observables)}
        else:
            self.observables = observables
        for observable in self.observables.values():
            self._track_components(observable)

        self.variables = {} if variables is None else variables
        for variable in self.variables.values():
            self._track_components(variable)

        self.time = 0

    def _track_rule(self, rule: Rule) -> None:
        """Track any components mentioned in the left hand side of a `Rule`"""
        if isinstance(rule, KappaRule):
            for component in rule.left.components:
                # TODO: For efficiency check for isomorphism with already-tracked components
                self.mixture.track_component(component)

    def _track_components(self, observable: Component | AlgExp) -> None:
        """
        Tracks the `Component`s in the given observable.

        NOTE: For `AlgExp`s, does not track patterns nested by indirection:
        see the comment in the `filter` method.
        """
        if isinstance(observable, Component):
            self.mixture.track_component(observable)
        else:
            for component_exp in observable.filter("component_pattern"):
                self.mixture.track_component(component_exp.attrs["value"])

    def count_observable(self, obs: Component) -> int:
        try:
            embeddings = self.mixture.embeddings(obs)
        except KeyError:
            # Try to find an isomorphic observable if the specific one given isn't tracked
            try:
                tracked_obs = next(
                    (c for c in self.observables.values() if c.isomorphic(obs))
                )
            except StopIteration as e:
                e.add_note(
                    f"No component isomorphic to observable `{obs}` has been declared"
                )
                raise
            embeddings = self.mixture.embeddings(tracked_obs)
        return len(embeddings)

    def eval_observable(self, obs_name: str) -> int | float:
        try:
            observable = self.observables[obs_name]
        except KeyError as e:
            e.add_note(f"Observable `{obs_name}` not defined")
            raise

        if isinstance(observable, Component):
            return len(self.mixture.embeddings(observable))
        else:
            return observable.evaluate(self)

    def eval_variable(self, var_name: str) -> int | float:
        assert var_name in self.variables, f"Variable `{var_name}` not defined"
        return self.variables[var_name].evaluate(self)

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


class Monitor:
    system: System
    history: dict[str, list[float]]

    def __init__(self, system: System):
        self.system = system
        self.history = {"time": []} | {obs_name: [] for obs_name in system.observables}

    @cached_property
    def obs_names(self) -> list[str]:
        return list(self.system.observables.keys())

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
