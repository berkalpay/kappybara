import random
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass

from kappybara.physics import Site, Mixture


class Rule(ABC):
    def __init__(self, agent_types: tuple[str, ...], site_labels: tuple[str, ...]):
        self.agent_types = agent_types  # TODO: unneeded?
        self.site_labels = site_labels

    def reactivity(self, system: "System") -> float:
        return self.n_embeddings(system.mixture) * self.rate(system)

    @abstractmethod
    def rate(self, system: "System") -> float:
        pass

    @abstractmethod
    def n_embeddings(self, mixture: Mixture) -> int:
        pass

    @abstractmethod
    def _select(self, mixture: Mixture):
        pass

    @abstractmethod
    def act(self, mixture: Mixture) -> None:
        pass


# Useful constants
AVOGADRO = 6.02214e23
DIFFUSION_RATE = 1e9
KDS = {"weak": 1e-6, "moderate": 1e-7, "strong": 1e-8}
VOLUMES = {"fibro": 2.25e-12, "yeast": 4.2e-14}
ROOM_TEMPERATURE = 273.15 + 25


def basic_binding_unbinding(
    *args, kd: float, k_on: float = DIFFUSION_RATE, **kwargs
) -> tuple[Rule, Rule]:
    return (
        BasicBinding(k_on, *args, **kwargs),
        BasicUnbinding(kd, k_on, *args, **kwargs),
    )


class BasicBinding(Rule):
    def __init__(self, k_on: float = DIFFUSION_RATE, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.k_on = k_on

    def rate(self, system: "System") -> float:
        return self.k_on / (AVOGADRO * system.volume)

    def n_embeddings(self, mixture: Mixture) -> int:
        # NOTE: counts illegal intra-agent bond opportunities
        site1_choices = mixture.free_sites[self.site_labels[0]]
        site2_choices = mixture.free_sites[self.site_labels[1]]
        return len(site1_choices) * len(site2_choices)

    def _select(self, mixture: Mixture) -> tuple[Site, Site]:
        # NOTE: might be an illegal intra-agent bond
        site1 = random.choice(tuple(mixture.free_sites[self.site_labels[0]]))
        site2 = random.choice(tuple(mixture.free_sites[self.site_labels[1]]))
        return (site1, site2)

    def act(self, mixture: Mixture) -> None:
        site1, site2 = self._select(mixture)
        site1.bind(site2)


class BasicUnbinding(Rule):
    def __init__(self, kd: float, k_on: float = DIFFUSION_RATE, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.kd = kd
        self.k_on = k_on

    def rate(self, system: "System") -> float:
        return self.k_on * math.pow(self.kd, 1 / system.temperature)

    def n_embeddings(self, mixture: Mixture) -> int:
        return [
            site.partner.label == self.site_labels[1]
            for site in mixture.bound_sites.get(self.site_labels[0], [])
        ].count(True)

    def _select(self, mixture: Mixture) -> Site:
        site_choices = []
        for agent in mixture.agents_by_type[self.agent_types[0]]:
            site = agent.interface[self.site_labels[0]]
            if site.bound and site.partner.label == self.site_labels[1]:
                site_choices.append(site)
        site_choice = random.choice(site_choices)
        return site_choice

    def act(self, mixture: Mixture) -> None:
        self._select(mixture).unbind()


@dataclass
class System:
    mixture: Mixture
    rules: list[Rule]
    volume: float = VOLUMES["fibro"]
    temperature: float = 273.15 + 25  # Room temperature
    time: float = 0

    @property
    def rule_reactivities(self) -> list[float]:
        return [rule.reactivity(self) for rule in self.rules]

    @property
    def reactivity(self) -> float:
        return sum(self.rule_reactivities)

    def wait(self) -> None:
        self.time += random.expovariate(self.reactivity)

    def act(self) -> None:
        rule = random.choices(self.rules, weights=self.rule_reactivities)[0]
        try:
            rule.act(self.mixture)
        except AssertionError:
            return

    def update(self) -> None:
        self.wait()
        self.act()
