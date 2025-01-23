from dataclasses import dataclass
from collections import Counter
from typing import Self, Optional


@dataclass
class Site:
    label = str
    partner: Optional[Self] = None
    state: Optional[str] = None
    agent: Optional["Agent"] = None

    @property
    def bound(self) -> bool:
        self.partner is not None

    def bind(self, site: Self) -> None:
        self.partner = site
        site.partner = self
        site.agent.molecule.attach_agents(self.agent.molecule)

    def unbind(self, site: Self) -> None:
        self.partner = None
        site.partner = None
        # TODO: check if molecule has split


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


@dataclass(frozen=True)
class AgentType:
    name: str
    site_labels: list[str]

    def agent(self) -> Agent:
        return Agent(self.name, tuple([Site(label) for label in self.site_labels]))


@dataclass
class Molecule:
    agents: list[Agent]

    @classmethod
    def create(cls, agent_types: list[AgentType], bonds=None):
        return cls([agent_type.agent() for agent_type in agent_types])

    def __post_init__(self):
        self.attach_agents()

    def attach_agents(self, molecule: Optional[Self] = None) -> None:
        for agent in self.agents:
            agent.molecule = molecule if molecule is not None else self

    def __len__(self):
        return len(self.agents)

    def __iter__(self):
        yield from self.agents

    @property
    def composition(self) -> Counter:
        return Counter(agent.type for agent in self)

    @property
    def rarest_type(self) -> str:
        next(iter(self.composition))  # TODO: fix
