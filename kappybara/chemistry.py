import random
from dataclasses import dataclass
from collections import defaultdict
from itertools import chain

from kappybara.physics import Site, Agent, Molecule
from kappybara.utils import OrderedSet

AVOGADRO = 6.02214e23
ROOM_TEMPERATURE = 273.15 + 25


class Mixture:
    molecules: OrderedSet[Molecule]
    free_sites: dict[str, OrderedSet[Site]]
    bound_sites: dict[str, OrderedSet[Site]]

    def __init__(self, molecules: set[Molecule]):
        self.molecules = OrderedSet()
        # TODO: a data structure to handle two complementary sets?
        self.agents_by_type = defaultdict(OrderedSet)
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
        for agent in molecule.agents:
            self.agents_by_type[agent.type].add(agent)
        for site in molecule.sites:
            if site.bound:
                self.bound_sites[site.label].add(site)
            else:
                self.free_sites[site.label].add(site)

    def remove(self, molecule: Molecule) -> None:
        self.molecules.remove(molecule)
        for agent in molecule.agents:
            self.agents_by_type[agent.type].remove(agent)
        for site in molecule.sites:
            try:
                self.free_sites[site.label].remove(site)
            except KeyError:
                self.bound_sites[site.label].remove(site)

    @property
    def agents(self) -> chain[Agent]:
        return chain.from_iterable(
            self.agents_by_type[agent_type] for agent_type in self.molecules
        )

    def free_site(self, site: Site) -> None:
        self.free_sites[site.label].add(site)
        self.bound_sites[site.label].remove(site)

    def unfree_site(self, site: Site) -> None:
        self.free_sites[site.label].remove(site)
        self.bound_sites[site.label].add(site)


@dataclass
class System:
    mixture: Mixture
    rules: list["Rule"]
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
