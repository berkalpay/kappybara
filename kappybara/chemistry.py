from dataclasses import dataclass
from random import expovariate, choice, choices
from itertools import chain
from typing import Hashable, Iterable, Optional

from physics import Site, Agent, Molecule

AVOGADRO = 6.02214e23
ROOM_TEMPERATURE = 273.15 + 25


def group(iterable: Iterable, key) -> dict[Hashable, list | set]:
    groups = dict()
    for item in iterable:
        k = key(item)
        if k in groups:
            groups[k].append(item)
        else:
            groups[k] = [item]
    return groups


@dataclass
class Mixture:
    molecules: list[Molecule]

    def __post_init__(self):
        for molecule in self.molecules:
            molecule.mixture = self

    def __len__(self):
        return len(self.molecules)

    def __iter__(self):
        yield from self.molecules

    def add(self, molecule: Molecule) -> None:
        self.molecules.append(molecule)
        molecule.mixture = self

    @property
    def agents(self) -> chain[Agent]:
        return chain.from_iterable(molecule.agents for molecule in self.molecules)

    @property
    def agents_by_type(self) -> dict[str, list[Agent]]:
        return group(self.agents, lambda x: x.type)

    @property
    def free_sites(self) -> dict[str, set]:
        """
        Generate free sites dictionary {site label: set of sites} from scratch
        if it hasn't be created yet, otherwise access updated.
        """
        if not hasattr(self, "_free_sites"):
            free_sites_lists = group(
                chain.from_iterable(agent.free_sites for agent in self.agents),
                lambda site: site.label,
            )
            self._free_sites = {
                site_label: set(free_sites_lists[site_label])
                for site_label in free_sites_lists
            }
        return self._free_sites

    def free_site(self, site: Site) -> None:
        self._free_sites[site.label].add(site)

    def unfree_site(self, site: Site) -> None:
        self._free_sites[site.label].remove(site)


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
            site_choices = []
            for agent in mixture.agents_by_type[self.agent_types[0]]:
                site = agent.interface[self.site_labels[0]]
                if site.bound and site.partner.label == self.site_labels[1]:
                    site_choices.append(site)
            return len(site_choices)

    def _select(self, mixture: Mixture) -> tuple[Site, Optional[Site]]:
        if self.bind:
            # Note: might be an illegal intra-agent bond
            site1 = choice(tuple(mixture.free_sites[self.site_labels[0]]))
            site2 = choice(tuple(mixture.free_sites[self.site_labels[1]]))
            return (site1, site2)
        else:
            site_choices = []
            for agent in mixture.agents_by_type[self.agent_types[0]]:
                site = agent.interface[self.site_labels[0]]
                if site.bound and site.partner.label == self.site_labels[1]:
                    site_choices.append(site)
            site_choice = choice(site_choices)
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
        self.time += expovariate(self.reactivity)

    def act(self) -> None:
        rule = choices(self.rules, weights=self.rule_reactivities)[0]
        try:
            rule.act(self.mixture)
        except AssertionError:
            return
        self.mixture.molecules = [
            molecule for molecule in self.mixture.molecules if len(molecule)
        ]

    def update(self) -> None:
        self.wait()
        self.act()
