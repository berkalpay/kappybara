from dataclasses import dataclass
from functools import cached_property
from itertools import chain
from collections import defaultdict, Counter
from typing import Self, Optional, Iterator, Iterable

from kappybara.utils import OrderedSet


@dataclass
class Site:
    label: str
    agent: "Agent"
    partner: Optional[Self] = None

    def __repr__(self):
        return f"Site(label={self.label}, partner={self.partner.label if self.bound else None})"

    def __hash__(self):
        return id(self)

    @property
    def bound(self) -> bool:
        return self.partner is not None

    def bind(self, other: Self) -> None:
        assert self.agent is not other.agent
        self.partner = other
        other.partner = self
        if self.agent.molecule != other.agent.molecule:
            self.agent.molecule.merge(other.agent.molecule)
        for site in [self, other]:
            mixture.unfree_site(site)

    def unbind(self) -> None:
        other = self.partner
        self.partner = None
        assert other is not None
        other.partner = None
        if not self.agent.same_molecule(other.agent):
            molecule = self.agent.molecule
            molecule.mixture.remove(molecule)
            molecule.update(self.agent)
            molecule.update(other.agent)
        else:
            self.agent.molecule.mixture.free_site(self)
            other.agent.molecule.mixture.free_site(other)


class Agent:
    def __init__(self, type: str, site_labels: Iterable[str], molecule: "Molecule"):
        self.type = type
        self.sites = tuple(Site(site_label, self) for site_label in site_labels)
        self.molecule = molecule

    def __iter__(self):
        yield from self.sites

    def __hash__(self):
        return id(self)

    def __repr__(self):
        interface_str = [str(site) for _, site in self.interface.items()]
        return f"Agent(type={self.type}, interface={interface_str})"

    @cached_property
    def interface(self) -> dict[str, Site]:
        return {site.label: site for site in self.sites}

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

    def agent(self, molecule: "Molecule") -> Agent:
        return Agent(self.name, self.site_labels, molecule)

    def molecule(self) -> "Molecule":
        return Molecule(
            [(self.name, {site_label: None for site_label in self.site_labels})]
        )


class Molecule:
    def __init__(self, agent_signatures: list[tuple[str, dict[str, Optional[int]]]]):
        """
        Takes an agent_list that denotes agent types with their interfaces and
        bond labels, e.g.
        [("A", {"l": 1, "p": None, "r": None}),
         ("A", {"l": None, "p": None, "r": 1})]
        """
        self.mixture: "Mixture" = mixture

        # Make agents
        self.agents = []
        bonds: defaultdict[int, list[Site]] = defaultdict(list)
        for agent_signature in agent_signatures:
            interface = agent_signature[1]
            agent = Agent(agent_signature[0], interface.keys(), self)
            self.agents.append(agent)
            for site_label, bond_num in interface.items():
                if bond_num is not None:
                    bonds[bond_num].append(agent.interface[site_label])

        # Make bonds
        self.mixture.add(self)
        for bond in bonds.values():
            assert len(bond) == 2
            site1, site2 = bond
            site1.bind(site2)

    @classmethod
    def from_agents(cls, agents: Iterable[Agent]) -> Self:
        molecule = cls([])
        molecule.agents = list(agents)
        molecule.attach_agents()
        return molecule

    @classmethod
    def from_kappa(cls):
        # TODO: initialize from a kappa string representation
        pass

    def __len__(self):
        return len(self.agents)

    def __iter__(self):
        yield from self.agents

    def __hash__(self):
        return id(self)

    def __repr__(self):  # TODO: add detail
        return f"Molecule with id {id(self)} and composition {self.composition}"

    def __str__(self):
        # TODO: return the canonical kappa string representation
        pass

    def attach_agents(self, molecule: Optional[Self] = None) -> None:
        molecule = self if molecule is None else molecule
        for agent in self.agents:
            agent.molecule = molecule

    def merge(self, other: Self) -> None:
        """Merges the other molecules into this one (without affecting bonds)."""
        self.agents.extend(other.agents)
        self.attach_agents()
        mixture.molecules.remove(other)

    @property
    def sites(self) -> Iterator[Site]:
        for agent in self.agents:
            for site in agent:
                yield site

    @property
    def composition(self) -> Counter:
        return Counter(agent.type for agent in self)

    def depth_first_traversal(self, start: Agent) -> list[Agent]:
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
        molecule = self.from_agents(self.depth_first_traversal(start))
        self.mixture.add(molecule)
        # TODO: remove old molecule here instead?
        return molecule


class Mixture:
    def __init__(self, molecules: Optional[set[Molecule]] = None):
        self.molecules: OrderedSet[Molecule] = OrderedSet()
        # TODO: a data structure to handle two complementary sets?
        self.agents_by_type: defaultdict[str, OrderedSet[Agent]] = defaultdict(
            OrderedSet
        )
        self.free_sites: defaultdict[str, OrderedSet[Site]] = defaultdict(OrderedSet)
        self.bound_sites: defaultdict[str, OrderedSet[Site]] = defaultdict(OrderedSet)

        if molecules is not None:
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


mixture = Mixture()
