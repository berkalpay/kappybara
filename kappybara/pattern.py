from collections import defaultdict
from functools import cached_property
from typing import Self, Optional, Iterator, Iterable, Union, NamedTuple, TYPE_CHECKING

from kappybara.utils import Counted, IndexedSet, Property

if TYPE_CHECKING:
    from kappybara.mixture import Mixture


# String partner states can be: "#" (wildcard), "." (empty), "_" (bound), "?" (undetermined)
# "?" is the default in pattern instantiation and a wildcard in rules and observations
SiteType = NamedTuple("SiteType", [("site_name", str), ("agent_name", str)])
Partner = str | SiteType | int | Union["Site"]


class Site(Counted):
    agent: "Agent"  # Expected to be set after initialization

    def __init__(self, label: str, state: str, partner: Partner):
        super().__init__()
        self.label = label
        self.state = state
        self.partner = partner

    def __repr__(self):
        return f'Site(id={self.id}, kappa_str="{self.kappa_str}")'

    @property
    def kappa_partner_str(self) -> str:
        if self.partner == "?":
            return ""
        elif self.coupled:
            return "[_]"
        return f"[{self.partner}]"

    @property
    def kappa_state_str(self) -> str:
        return "" if self.state == "?" else f"{{{self.state}}}"

    @property
    def kappa_str(self) -> str:
        return f"{self.label}{self.kappa_partner_str}{self.kappa_state_str}"

    @property
    def undetermined(self) -> bool:
        """Is the site in a state equivalent to leaving it unnamed in an agent?"""
        return self.state == "?" and self.partner in ("?", ".")

    @property
    def underspecified(self) -> bool:
        """Checks if a concrete `Site` can be created from this pattern."""
        return (
            self.state == "#"
            or self.partner in ("#", "_")
            or isinstance(self.partner, SiteType)
        )

    @property
    def stated(self) -> bool:
        return self.state not in ("#", "?")

    @property
    def bound(self) -> bool:
        return (
            self.partner == "_"
            or isinstance(self.partner, SiteType)
            or isinstance(self.partner, Site)
        )

    @property
    def coupled(self) -> bool:
        return isinstance(self.partner, Site)

    def embeds_in(self, other: Self) -> bool:
        """Checks whether self as a pattern matches other as a concrete site."""
        if (self.stated and self.state != other.state) or (
            self.bound and not other.coupled
        ):
            return False

        match self.partner:
            case ".":
                return other.partner == "."
            case SiteType():
                return (
                    self.partner.site_name == other.partner.label
                    and self.partner.agent_name == other.partner.agent.type
                )
            case Site():
                return (
                    self.partner.agent.type == other.partner.agent.type
                    and self.label == other.label
                )

        return True


class Agent(Counted):
    @classmethod
    def from_kappa(cls, kappa_str: str) -> Self:
        from kappybara.grammar import kappa_parser, AgentBuilder

        # Check pattern describes only a single agent
        input_tree = kappa_parser.parse(kappa_str)
        assert input_tree.data == "kappa_input"
        assert len(input_tree.children) == 1
        pattern_tree = input_tree.children[0]
        assert pattern_tree.data == "pattern"
        assert (
            len(pattern_tree.children) == 1
        ), "Zero or more than one agent patterns were specified."
        agent_tree = pattern_tree.children[0]
        return AgentBuilder(agent_tree).object

    def __init__(self, type: str, sites: Iterable[Site]):
        super().__init__()
        self.type = type
        self.interface = {site.label: site for site in sites}

    def __iter__(self):
        yield from self.sites

    def __getitem__(self, key: str) -> Site:
        return self.interface[key]

    def __repr__(self):
        return f'Agent(id={self.id}, kappa_str="{self.kappa_str}")'

    @property
    def kappa_str(self):
        return f"{self.type}({" ".join(site.kappa_str for site in self)})"

    @property
    def sites(self) -> Iterable[Site]:
        yield from self.interface.values()

    @cached_property
    def underspecified(self) -> bool:
        """Checks if a concrete `Agent` can be created from this pattern."""
        return any(site.underspecified for site in self)

    @property
    def neighbors(self) -> list[Self]:
        return [site.partner.agent for site in self if site.coupled]

    @property
    def depth_first_traversal(self) -> list[Self]:
        """Depth first traversal starting here."""
        visited = set()
        traversal = []
        stack = [self]
        while stack:
            if (agent := stack.pop()) not in visited:
                visited.add(agent)
                traversal.append(agent)
                stack.extend(agent.neighbors)
        return traversal

    @property
    def instantiable(self) -> bool:
        return not any(site.underspecified for site in self)

    def detached(self) -> Self:
        """Makes a clone of itself but with all its sites emptied."""
        detached = type(self)(
            self.type, [Site(site.label, site.state, ".") for site in self]
        )
        for site in detached:
            site.agent = detached
        return detached

    def isomorphic(self, other: Self) -> bool:
        """
        Check if two `Agent`s are equivalent locally, ignoring partners.
        NOTE: Doesn't assume agents of the same type will have the same site signatures.
        """

        if self.type != other.type:
            return False

        b_sites_leftover = set(other.interface)
        for site_name, a_site in self.interface.items():
            # Check that `b` has a site with the same name and state
            if site_name not in other.interface and not a_site.undetermined:
                return False
            b_sites_leftover.remove(site_name)
            if a_site.state != other[site_name].state:
                return False

        # Check that sites in `other` not mentioned in `self`are undetermined
        return all(other[site_name].undetermined for site_name in b_sites_leftover)

    def embeds_in(self, other: Self) -> bool:
        """Checks whether self as a pattern matches other as a concrete agent."""
        if self.type != other.type:
            return False

        for a_site in self:
            if a_site.label not in other.interface and not a_site.undetermined:
                return False
            b_site = other[a_site.label]
            if not a_site.embeds_in(b_site):
                return False

        return True


class Embedding(dict[Agent, Agent]):
    def __hash__(self):
        return hash(frozenset(self.items()))

    def __repr__(self):
        return f"Embedding({', '.join(f"{a.id}: {self[a].id}" for a in self)})"


class Component(Counted):
    """
    A set of agents that are all in the same connected component.
    NOTE: Connectedness is not guaranteed statically and must be enforced.
    """

    agents: IndexedSet[Agent]
    n_copies: int

    @classmethod
    def from_kappa(cls, kappa_str: str) -> Self:
        parsed_pattern = Pattern.from_kappa(kappa_str)
        assert len(parsed_pattern.components) == 1
        return parsed_pattern.components[0]

    def __init__(self, agents: list[Agent], n_copies: int = 1):
        super().__init__()

        assert agents
        assert n_copies >= 1
        if n_copies != 1:
            raise NotImplementedError(
                "Simulations won't handle n_copies correctly in counting embeddings."
            )

        self.agents = IndexedSet(agents)  # TODO: order by graph traversal
        self.agents.create_index("type", Property(lambda a: a.type))
        self.n_copies = n_copies

    def __iter__(self):
        yield from self.agents

    def __len__(self):
        return len(self.agents)

    def __repr__(self):
        return f'Component(id={self.id}, kappa_str="{self.kappa_str}")'

    @property
    def kappa_str(self) -> str:
        return Pattern.agents_to_kappa_str(self.agents)

    def add(self, agent: Agent):
        self.agents.add(agent)

    def isomorphic(self, other: Self) -> bool:
        return next(self.isomorphisms(other), None) is not None

    def embeddings(  # TODO: rename to `embed_in` or `embeddings_in`
        self, other: Self | "Mixture" | Iterable[Agent], exact: bool = False
    ) -> Iterator[Embedding]:
        """Finds embeddings of self in other. Setting exact=True finds isomorphisms."""
        if hasattr(other, "agents"):
            other: IndexedSet[Agent] = other.agents

        assert "type" in other.properties

        a_root = next(iter(self.agents))  # "a" refers to `self` and "b" to `other`
        # Narrow the search by mapping `a_root` to agents in `other` of the same type
        for b_root in other.lookup("type", a_root.type):

            agent_map = Embedding({a_root: b_root})  # The potential bijection
            frontier = {a_root}
            root_failed = False

            while frontier and not root_failed:
                a = frontier.pop()
                b = agent_map[a]

                match_func = a.isomorphic if exact else a.embeds_in
                if not match_func(b):
                    root_failed = True
                    break

                for a_site in a:
                    b_site = b[a_site.label]

                    if a_site.coupled:
                        a_partner = a_site.partner.agent
                        b_partner = b_site.partner.agent

                        if b_partner not in other:
                            # The embedding must be enclosed within the set of agents
                            # provided.
                            root_failed = True
                            break
                        elif a_partner not in agent_map:
                            frontier.add(a_partner)
                            agent_map[a_partner] = b_partner
                        elif agent_map[a_site.partner.agent] != b_site.partner.agent:
                            root_failed = True
                            break
                    elif exact and a_site.partner != b_site.partner:
                        root_failed = True
                        break

            if not root_failed:
                yield agent_map  # A valid bijection

    def isomorphisms(self, other: Self | "Mixture") -> Iterator[dict[Agent, Agent]]:
        """
        Checks for bijections which respect links in the site graph,
        ensuring that any internal site state specified in one compononent
        exists and is the same in the other.

        NOTE: Handles isomorphism generally, between instantiated components
        in a mixture and potentially between rule patterns.
        """
        if len(self.agents) != len(other.agents):
            return
        yield from self.embeddings(other, exact=True)

    @property
    def diameter(self) -> int:
        """The maximum minimum shortest path between any two agents."""

        def bfs_depth(root) -> int:
            frontier = set([root])
            seen = set()
            depth = -1

            while frontier:
                depth += 1
                new_frontier = set()
                seen = seen | frontier
                for cur in frontier:
                    for n in cur.neighbors:
                        if n not in seen:
                            new_frontier.add(n)

                frontier = new_frontier

            return depth

        return max(bfs_depth(a) for a in self.agents)


class Pattern:
    agents: list[Optional[Agent]]

    @classmethod
    def from_kappa(cls, kappa_str: str) -> Self:
        from kappybara.grammar import kappa_parser, PatternBuilder

        input_tree = kappa_parser.parse(kappa_str)
        assert input_tree.data == "kappa_input"
        assert (
            len(input_tree.children) == 1
        ), "Zero or more than one patterns were specified."
        assert len(input_tree.children) == 1
        pattern_tree = input_tree.children[0]
        return PatternBuilder(pattern_tree).object

    def __init__(self, agents: list[Optional[Agent]]):
        """
        Compile a pattern from a list of `Agent`s whose edges are implied by integer
        link states. Replaces integer link states with references to actual partners, and
        constructs a helper object which tracks connected components in the pattern. A None
        in `agents` represents an empty slot ("." in Kappa) in a rule expression pattern.
        """
        self.agents = agents

        # Parse site connections implied by integer LinkStates
        integer_links: defaultdict[int, list[Site]] = defaultdict(list)
        for agent in agents:
            if agent is not None:
                for site in agent:
                    if isinstance(site.partner, int):
                        integer_links[site.partner].append(site)

        # Replace integer LinkStates with Agent references
        for i in integer_links:
            linked_sites = integer_links[i]
            if len(linked_sites) == 1:
                raise AssertionError(f"Site link {i} is only referenced in one site.")
            elif len(linked_sites) > 2:
                raise AssertionError(
                    f"Site link {i} is referenced in more than two sites."
                )
            else:
                linked_sites[0].partner = linked_sites[1]
                linked_sites[1].partner = linked_sites[0]

    def __iter__(self) -> Iterator[Optional[Agent]]:
        yield from self.agents

    def __len__(self):
        return len(self.agents)

    @cached_property
    def components(self) -> list[Component]:
        unseen = set(agent for agent in self.agents if agent is not None)
        components = []
        while unseen:
            component = Component(next(iter(unseen)).depth_first_traversal)
            unseen = unseen.difference(component)
            components.append(component)
        return components

    @staticmethod
    def agents_to_kappa_str(agents: Iterable[Optional[Agent]]) -> str:
        bond_num_counter = 1
        bond_nums: dict[Site, int] = dict()
        agent_strs = []
        for agent in agents:
            if agent is None:
                agent_strs.append(".")
                continue
            site_strs = []
            for site in agent:
                if site in bond_nums:
                    partner_str = f"[{bond_nums[site]}]"
                elif site.coupled:
                    partner_str = f"[{bond_num_counter}]"
                    bond_nums[site.partner] = bond_num_counter
                    bond_num_counter += 1
                else:
                    partner_str = "" if site.partner == "?" else f"[{site.partner}]"
                site_strs.append(f"{site.label}{partner_str}{site.kappa_state_str}")
            agent_strs.append(f"{agent.type}({" ".join(site_strs)})")
        return ", ".join(agent_strs)

    @property
    def kappa_str(self) -> str:
        return type(self).agents_to_kappa_str(self.agents)

    @cached_property
    def underspecified(self) -> bool:
        return any(agent is None or agent.underspecified for agent in self.agents)
