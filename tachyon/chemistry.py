from dataclasses import dataclass
from random import expovariate, choices
from itertools import chain
from typing import NamedTuple

from physics import Site, Agent, Molecule

AVOGADRO = 6.02214e23
ROOM_TEMPERATURE = 273.15 + 25


@dataclass
class Mixture:
    molecules: list[Molecule]

    def __len__(self):
        return len(self.molecules)

    def add_molecule(self, molecule: Molecule) -> None:
        self.molecules.append(molecule)

    @property
    def agents(self) -> chain[Agent]:
        return chain.from_iterable(molecule.agents for molecule in self.molecules)

    @property
    def agents_by_type(self) -> dict[str, list[Agent]]:
        agents_by_type = dict()
        for agent in self.agents:
            if agent.type not in agents_by_type:
                agents_by_type[agent.type] = [agent]
            else:
                agents_by_type[agent.type].append(agent)
        return agents_by_type

    @property
    def free_sites(self) -> list[Site]:
        pass


@dataclass
class Rule:
    agent_types: tuple[str, str]
    site_labels: tuple[str, str]
    rate: float


Action = NamedTuple(
    "Action", [("sites", tuple[Site]), ("bind", bool), ("activity", float)]
)


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
                print(agent.interface)
                agent1_site = agent.interface[rule.site_labels[0]]
                # Assumes site labels are unique across agent types
                if agent1_site.bound and agent1_site.partner.label == rule.sites[1]:
                    actions.append(
                        Action((agent1_site, agent1_site.partner), False, rule.rate)
                    )  # TODO: stochastic rate, unimolecular
        return actions

    @property
    def possible_bonds(self) -> list[Action]:
        return []  # TODO: implement

    @property
    def possible_actions(self) -> list[Action]:
        return self.possible_unbonds + self.possible_bonds

    @property
    def reactivity(self) -> float:
        return sum(action.activity for action in self.possible_actions)

    def holding_time(self) -> float:
        return expovariate(self.reactivity)

    def action(self) -> Action:
        possible_actions = self.possible_actions
        choices(
            possible_actions,
            weights=[action.activity / self.reactivity for action in possible_actions],
        )[0]

    def update(self):
        self.time += self.holding_time()
        action = self.action()
        if action.bind:
            action.sites[0].bind(action.sites[1])
        else:
            action.sites[0].unbind(action.sites[1])
        self.molecules = [molecule for molecule in self.molecules if len(molecule)]
