import random
from dataclasses import dataclass
from collections import defaultdict
from itertools import chain
from functools import cached_property
from typing import Hashable, Iterable, Optional

from kappybara.physics import Site, Agent, Molecule
from kappybara.utils import OrderedSet

AVOGADRO = 6.02214e23
ROOM_TEMPERATURE = 273.15 + 25


def group(iterable: Iterable, key) -> dict[Hashable, list]:
    groups = dict()
    for item in iterable:
        k = key(item)
        if k in groups:
            groups[k].append(item)
        else:
            groups[k] = [item]
    return groups


class Mixture:
    molecules: set[Molecule]
    free_sites: dict[str, set]
    bound_sites: dict[str, set]

    def __init__(self, molecules: set[Molecule]):
        self.molecules = OrderedSet()
        # TODO: a data structure to handle two complementary sets?
        self.free_sites = defaultdict(OrderedSet)
        self.bound_sites = defaultdict(OrderedSet)
        for molecule in molecules:
            self.add(molecule)

    def __len__(self):
        return len(self.molecules)

    def __iter__(self):
        yield from self.molecules

    def add(self, molecule: Molecule) -> None:
        self.molecules.add(molecule)
        molecule.mixture = self
        for site in molecule.sites:
            if site.bound:
                self.bound_sites[site.label].add(site)
            else:
                self.free_sites[site.label].add(site)

    def remove(self, molecule: Molecule) -> None:
        self.molecules.remove(molecule)
        for site in molecule.sites:
            try:
                self.free_sites[site.label].remove(site)
            except KeyError:
                self.bound_sites[site.label].remove(site)

    @property
    def agents(self) -> chain[Agent]:
        return chain.from_iterable(molecule.agents for molecule in self.molecules)

    @cached_property  # TODO: update if agent composition changes
    def agents_by_type(self) -> dict[str, list[Agent]]:
        return group(self.agents, lambda agent: agent.type)

    def free_site(self, site: Site) -> None:
        self.free_sites[site.label].add(site)
        self.bound_sites[site.label].remove(site)

    def unfree_site(self, site: Site) -> None:
        self.free_sites[site.label].remove(site)
        self.bound_sites[site.label].add(site)


@dataclass
class Rule:
    agent_types: tuple[str, str]  # TODO: unneeded?
    site_labels: tuple[str, str]
    bind: bool
    rate: float

    def reactivity(self, mixture: Mixture) -> float:
        return self.n_embeddings(mixture) * self.rate

    def n_embeddings(self, mixture: Mixture) -> int:
        if self.bind:
            # Note: counts illegal intra-agent bond opportunities
            site1_choices = mixture.free_sites[self.site_labels[0]]
            site2_choices = mixture.free_sites[self.site_labels[1]]
            return len(site1_choices) * len(site2_choices)
        else:
            return [
                site.partner.label == self.site_labels[1]
                for site in mixture.bound_sites.get(self.site_labels[0], [])
            ].count(True)

    def _select(self, mixture: Mixture) -> tuple[Site, Optional[Site]]:
        if self.bind:
            # Note: might be an illegal intra-agent bond
            site1 = random.choice(tuple(mixture.free_sites[self.site_labels[0]]))
            site2 = random.choice(tuple(mixture.free_sites[self.site_labels[1]]))
            return (site1, site2)
        else:
            site_choices = []
            for agent in mixture.agents_by_type[self.agent_types[0]]:
                site = agent.interface[self.site_labels[0]]
                if site.bound and site.partner.label == self.site_labels[1]:
                    site_choices.append(site)
            site_choice = random.choice(site_choices)
            return (site_choice, None)

    def act(self, mixture: Mixture) -> None:
        site1, site2 = self._select(mixture)
        if self.bind:
            site1.bind(site2)
        else:
            site1.unbind()


@dataclass
class System:
    mixture: Mixture
    rules: list[Rule]
    temperature: float = ROOM_TEMPERATURE
    time: float = 0

    @property
    def rule_reactivities(self) -> list[float]:
        return [rule.reactivity(self.mixture) for rule in self.rules]

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
