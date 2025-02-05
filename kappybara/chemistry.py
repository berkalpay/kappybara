from dataclasses import dataclass
from random import expovariate, choices
from itertools import chain, product
from typing import Hashable, NamedTuple, Iterable

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
            self._free_sites = {k: set(free_sites_lists[k]) for k in free_sites_lists}
        return self._free_sites

    def free_site(self, site: Site) -> None:
        self._free_sites[site.label].add(site)

    def unfree_site(self, site: Site) -> None:
        self._free_sites[site.label].remove(site)


@dataclass
class Rule:
    agent_types: tuple[str, str]  # TODO: unneeded?
    site_labels: tuple[str, str]
    rate: float


Action = NamedTuple(
    "Action", [("sites", tuple[Site]), ("bind", bool), ("activity", float)]
)  # TODO: refactor


@dataclass
class System:
    mixture: Mixture
    rules: list[Rule]
    temperature: float = ROOM_TEMPERATURE
    time: float = 0

    @property
    def possible_unbonds(self) -> list[Action]:
        actions = []
        for rule in self.rules:
            for agent in self.mixture.agents_by_type[rule.agent_types[0]]:
                agent1_site = agent.interface[rule.site_labels[0]]
                # Assumes site labels are unique across agent types
                if (
                    agent1_site.bound
                    and agent1_site.partner.label == rule.site_labels[1]
                ):
                    actions.append(
                        Action((agent1_site, agent1_site.partner), False, rule.rate)
                    )  # TODO: stochastic rate, unimolecular
        return actions

    @property
    def possible_bonds(self) -> list[Action]:
        actions = []
        for rule in self.rules:
            sites1 = self.mixture.free_sites[rule.site_labels[0]]
            sites2 = self.mixture.free_sites[rule.site_labels[1]]
            for site1, site2 in product(sites1, sites2):
                if site1.agent is not site2.agent:
                    actions.append(Action((site1, site2), True, rule.rate))
        return actions

    @property
    def possible_actions(self) -> list[Action]:
        return self.possible_unbonds + self.possible_bonds

    @property
    def reactivity(self) -> float:
        return sum(action.activity for action in self.possible_actions)

    def wait(self) -> None:
        self.time += expovariate(self.reactivity)

    def action(self) -> Action:
        possible_actions = self.possible_actions
        return choices(
            possible_actions,
            weights=[action.activity / self.reactivity for action in possible_actions],
        )[0]

    def act(self) -> None:
        action = self.action()
        if action.bind:
            action.sites[0].bind(action.sites[1])
        else:
            action.sites[0].unbind()
        self.mixture.molecules = [
            molecule for molecule in self.mixture.molecules if len(molecule)
        ]

    def update(self) -> None:
        self.wait()
        self.act()
