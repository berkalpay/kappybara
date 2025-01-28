from dataclasses import dataclass
from collections import Counter
from typing import Self, Optional


@dataclass
class Site:
    label: str
    partner: Optional[Self] = None
    agent: Optional["Agent"] = None

    @property
    def bound(self) -> bool:
        self.partner is not None

    def bind(self, other: Self) -> None:
        self.partner = other
        other.partner = self
        if not self.agent.same_molecule(other.agent):
            self.agent.molecule.merge(other.agent.molecule)

    def unbind(self) -> None:
        assert self.bound
        other = self.partner
        self.partner = None
        other.partner = None
        if not self.agent.same_molecule(other.agent):
            self.agent.molecule.update()
            other.agent.molecule.update()


@dataclass
class Agent:
    type: str
    sites: tuple[Site]
    molecule: Optional["Molecule"] = None

    def __post_init__(self):
        for site in self.sites:
            site.agent = self
        self.interface = {site.label: site for site in self.sites}

    def __iter__(self):
        yield from self.sites

    @property
    def bound_sites(self) -> list[Site]:
        return [site for site in self if site.bound]

    @property
    def neighbors(self) -> list[Self]:
        [site.partner.agent for site in self]

    def same_molecule(self, other: Self) -> bool:
        return self in self.molecule.depth_first_traversal(other)


@dataclass(frozen=True)
class AgentType:
    name: str
    site_labels: list[str]

    def agent(self) -> Agent:
        return Agent(self.name, tuple([Site(label) for label in self.site_labels]))


@dataclass
class Molecule:
    agents: list[Agent]
    mixture: Optional["Mixture"] = None

    @classmethod
    def create(cls, agent_types: list[AgentType], bonds=None):
        return cls([agent_type.agent() for agent_type in agent_types])

    def __post_init__(self):
        self.attach_agents()

    def attach_agents(self, molecule: Optional[Self] = None) -> None:
        molecule = self if molecule is None else molecule
        for agent in self.agents:
            agent.molecule = molecule

    def __len__(self):
        return len(self.agents)

    def __iter__(self):
        yield from self.agents

    def merge(self, other: Self) -> None:
        self.agents.extend(other.agents)
        self.attach_agents()
        other.clear()

    @property
    def composition(self) -> Counter:
        return Counter(agent.type for agent in self)

    @property
    def rarest_type(self) -> str:
        next(iter(self.composition))  # TODO: fix

    def depth_first_traversal(self, start: Agent) -> list[Self]:
        visited = {}
        traversal = []
        stack = [start]
        while stack:
            if agent := stack.pop() not in visited:
                visited.add(agent)
                traversal.append(agent)
                stack.extend(agent.neighbors)
        return traversal

    def clear(self) -> None:
        self.agents = []

    def update(self, start: Agent) -> Self:
        molecule = Molecule(self.depth_first_traversal(start))
        self.mixture.add(molecule)
        self.clear()
        return molecule
