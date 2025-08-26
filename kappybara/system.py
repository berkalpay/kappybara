import os
import tempfile
import random
import warnings
from collections import defaultdict
from functools import cached_property
from typing import Optional, Iterable, Self

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.figure

import kappybara.kappa as kappa
from kappybara.mixture import Mixture, ComponentMixture
from kappybara.rule import Rule, KappaRule, KappaRuleUnimolecular, KappaRuleBimolecular
from kappybara.pattern import Component, Pattern
from kappybara.algebra import Expression


class System:
    mixture: Mixture
    rules: list[Rule]
    observables: dict[str, Expression]
    variables: dict[str, Expression]
    monitor: Optional["Monitor"]
    time: float
    tallies: defaultdict[str, dict[str, int]]

    def __init__(
        self,
        mixture: Optional[Mixture] = None,
        rules: Optional[Iterable[Rule]] = None,
        observables: Optional[dict[str, Expression]] = None,
        variables: Optional[dict[str, Expression]] = None,
        monitor: bool = True,
    ):
        self.rules = [] if rules is None else list(rules)

        if not isinstance(mixture, ComponentMixture) and any(
            type(rule) in [KappaRuleUnimolecular, KappaRuleBimolecular]
            for rule in self.rules
        ):
            patterns = [] if mixture is None else [Pattern(list(mixture.agents))]
            mixture = ComponentMixture(patterns)

        if mixture is None:
            mixture = (
                ComponentMixture()
                if any(
                    type(rule) in [KappaRuleUnimolecular, KappaRuleBimolecular]
                    for rule in self.rules
                )
                else Mixture()
            )

        self.observables = {} if observables is None else observables
        self.variables = {} if variables is None else variables

        self.set_mixture(mixture)
        self.time = 0

        self.tallies = defaultdict(lambda: {"applied": 0, "failed": 0})
        if monitor:
            self.monitor = Monitor(self)
            self.monitor.update()
        else:
            self.monitor = None

    @classmethod
    def from_kappa(
        cls,
        mixture: Optional[Mixture] = None,  # TODO: Optional[dict[str, int]]
        rules: Optional[Iterable[str]] = None,
        observables: Optional[list[str] | dict[str, str]] = None,
        variables: Optional[dict[str, str]] = None,
        *args,
        **kwargs,
    ) -> Self:
        real_rules = []
        if rules is not None:
            for rule in rules:
                real_rules.extend(kappa.rules(rule))

        if observables is None:
            real_observables = {}
        elif isinstance(observables, list):
            real_observables = {
                f"o{i}": kappa.expression(obs) for i, obs in enumerate(observables)
            }
        else:
            real_observables = {
                name: kappa.expression(obs) for name, obs in observables.items()
            }

        real_variables = (
            {}
            if variables is None
            else {name: kappa.expression(var) for name, var in variables.items()}
        )

        return cls(
            mixture,
            real_rules,
            real_observables,
            real_variables,
            *args,
            **kwargs,
        )

    def __str__(self):
        return self.kappa_str

    def __getitem__(self, name: str) -> int | float:
        if name in self.observables:
            return self.observables[name].evaluate(self)
        elif name in self.variables:
            return self.variables[name].evaluate(self)
        else:
            raise KeyError(
                f"Name {name} doesn't correspond to a declared observable or variable"
            )

    def __setitem__(self, name: str, kappa_str: str):
        expr = kappa.expression(kappa_str)
        self._track_constituent_components(expr)
        if name in self.variables:
            self.variables[name] = expr
        else:  # Set new expressions as observables
            self.observables[name] = expr

    @property
    def names(self) -> dict[str, set[str]]:
        return {
            "observables": set(self.observables),
            "variables": set(self.variables),
        }

    @property
    def tallies_str(self) -> str:
        return "Rule\tApplied\tFailed\n" + "\n".join(
            f"{rule_str}\t{tallies["applied"]}\t{tallies["failed"]}"
            for rule_str, tallies in self.tallies.items()
        )

    @property
    def kappa_str(self) -> str:
        kappa_str = ""
        for var_name, var in self.variables.items():
            kappa_str += f"%var: '{var_name}' {var.kappa_str}\n"
        for rule in self.rules:
            assert isinstance(rule, KappaRule)
            kappa_str += f"{rule.kappa_str}\n"
        for obs_name, obs in self.observables.items():
            obs_str = (
                f"|{obs.kappa_str}|" if isinstance(obs, Component) else obs.kappa_str
            )
            kappa_str += f"%obs: '{obs_name}' {obs_str}\n"
        kappa_str += self.mixture.kappa_str
        return kappa_str

    def to_ka(self, filepath: str) -> None:
        """Writes system information to a Kappa file."""
        with open(filepath, "w") as f:
            f.write(self.kappa_str)

    def set_mixture(self, mixture: Mixture) -> None:
        self.mixture = mixture
        for rule in self.rules:
            self._track_rule(rule)
        for observable in self.observables.values():
            self._track_constituent_components(observable)
        for variable in self.variables.values():
            self._track_constituent_components(variable)

    def _track_rule(self, rule: Rule) -> None:
        """Track any components mentioned in the left hand side of a `Rule`"""
        if isinstance(rule, KappaRule):
            for component in rule.left.components:
                # TODO: For efficiency check for isomorphism with already-tracked components
                self.mixture.track_component(component)

    def _track_constituent_components(self, obj: Component | Expression) -> None:
        """
        Tracks the `Component`s in the given observable.
        NOTE: for `Expression`s, doesn't track patterns nested by indirection - see the `filter` method.
        """
        if isinstance(obj, Component):
            self.mixture.track_component(obj)
        else:
            for component_exp in obj.filter("component_pattern"):
                self.mixture.track_component(component_exp.attrs["value"])

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

    def choose_rule(self) -> Optional[Rule]:
        try:
            return random.choices(self.rules, weights=self.rule_reactivities)[0]
        except ValueError:
            warnings.warn("system has no reactivity: no rule applied", RuntimeWarning)
            return None

    def apply_rule(self, rule: Rule) -> None:
        update = rule.select(self.mixture)
        if update is not None:
            self.tallies[str(rule)]["applied"] += 1
            self.mixture.apply_update(update)
            del self.__dict__["rule_reactivities"]
        else:
            self.tallies[str(rule)]["failed"] += 1

    def update(self) -> None:
        self.wait()
        if (rule := self.choose_rule()) is not None:
            self.apply_rule(rule)
        if self.monitor:
            self.monitor.update()

    def update_via_kasim(self, time: float) -> None:
        """
        Simulates for `time` additional time units in KaSim.
        Needs KaSim to be installed and in the PATH.
        NOTE: some features may not be compatible between Kappybara and KaSim.
        """
        with tempfile.TemporaryDirectory() as tmpdirname:
            # Run KaSim on the current system
            output_ka_path = os.path.join(tmpdirname, "out.ka")
            output_cmd = f'%mod: alarm {time} do $SNAPSHOT "{output_ka_path}";'
            input_ka_path = os.path.join(tmpdirname, "in.ka")
            with open(input_ka_path, "w") as f:
                f.write(f"{self.kappa_str}\n{output_cmd}")
            os.system(f"KaSim {input_ka_path} -l {time} -d {tmpdirname}")

            # Read the KaSim output
            output_kappa_str = ""
            with open(output_ka_path) as f:
                for line in f:
                    if line.startswith("%init"):
                        split = line.split("/")
                        output_kappa_str += split[0] + split[-1]

        # Apply the update
        self.set_mixture(kappa.system(output_kappa_str).mixture)
        self.time += time
        if self.monitor:
            self.monitor.update()


class Monitor:
    system: System
    history: dict[str, list[Optional[float]]]

    def __init__(self, system: System):
        self.system = system
        self.history = {"time": []} | {obs_name: [] for obs_name in system.observables}

    def update(self) -> None:
        self.history["time"].append(self.system.time)
        for obs_name in self.system.observables:
            if obs_name not in self.history:
                self.history[obs_name] = [None] * (len(self.history["time"]) - 1)
            self.history[obs_name].append(self.system[obs_name])

    @property
    def dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(self.history)

    def plot(self) -> matplotlib.figure.Figure:
        fig, ax = plt.subplots()
        for obs_name in self.system.observables:
            ax.plot(self.history["time"], self.history[obs_name], label=obs_name)
        plt.legend()
        plt.xlabel("Time")
        plt.ylabel("Observable")
        plt.margins(0, 0)
        return fig
