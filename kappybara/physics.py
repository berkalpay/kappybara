from dataclasses import dataclass
from collections import Counter
from typing import Self, Optional, Iterator


@dataclass
class Site:
    label: str
    partner: Optional[Self] = None
    agent: Optional["Agent"] = None

    def __repr__(self):
        return f"Site(label={self.label}, partner={self.partner.label if self.bound else None})"

    def __hash__(self):
        return id(self)

    @property
    def bound(self) -> bool:
        return self.partner is not None

    def bind(self, other: Self) -> None:
        assert self.agent is not other.agent
        intramolecular = self.agent.same_molecule(other.agent)
        self.partner = other
        other.partner = self
        if not intramolecular:
            self.agent.molecule.merge(other.agent.molecule)
        for site in [self, other]:
            self.agent.molecule.mixture.unfree_site(site)

    def unbind(self) -> None:
        assert self.bound
        other = self.partner
        self.partner = None
        other.partner = None
        if not self.agent.same_molecule(other.agent):
            molecule = self.agent.molecule
            molecule.mixture.remove(molecule)
            molecule.update(self.agent)
            molecule.update(other.agent)
        else:
            self.agent.molecule.mixture.free_site(self)
            other.agent.molecule.mixture.free_site(other)


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

    def __hash__(self):
        return id(self)

    def __repr__(self):
        interface_str = [str(site) for _, site in self.interface.items()]
        return f"Agent(type={self.type}, interface={interface_str})"

    @property
    def bound_sites(self) -> list[Site]:
        return [site for site in self if site.bound]

    @property
    def free_sites(self) -> list[Site]:
        return [site for site in self if not site.bound]

    @property
    def neighbors(self) -> list[Self]:
        return [site.partner.agent for site in self if site.bound]

    def same_molecule(self, other: Self) -> bool:
        return any(
            self is agent for agent in other.molecule.depth_first_traversal(other)
        )


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

    def __hash__(self):
        return id(self)

    def __repr__(self):  # TODO: add detail
        return f"Molecule with id {id(self)} and composition {self.composition}"

    def merge(self, other: Self) -> None:
        self.agents.extend(other.agents)
        self.attach_agents()
        other.mixture.molecules.remove(other)

    @property
    def sites(self) -> Iterator[Site]:
        for agent in self.agents:
            for site in agent:
                yield site

    @property
    def composition(self) -> Counter:
        return Counter(agent.type for agent in self)

    @property
    def rarest_type(self) -> str:
        next(iter(self.composition))  # TODO: fix

    def depth_first_traversal(self, start: Agent) -> list[Self]:
        visited = set()
        traversal = []
        stack = [start]
        while stack:
            if (agent := stack.pop()) not in visited:
                visited.add(agent)
                traversal.append(agent)
                stack.extend(agent.neighbors)
        return traversal

    def update(self, start: Agent) -> Self:
        molecule = Molecule(self.depth_first_traversal(start))
        self.mixture.add(molecule)
        # TODO: remove old molecule here instead?
        return molecule
