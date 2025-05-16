from collections import defaultdict
from functools import cached_property
from typing import Self, Optional, Iterator, Iterable, NamedTuple

import kappybara.site_states as states
from kappybara.utils import Counted


class Site(Counted):
    def __init__(
        self,
        label: str,
        state: str,
        partner: states.LinkPattern,
        agent: Optional["Agent"] = None,
    ):
        super().__init__()
        self.label = label
        self.state = state
        self.partner = partner
        self.agent = agent

    def __repr__(self):
        partner = "_" if self.coupled else self.partner
        return f"{self.label}[{partner}]{{{self.state}}}"

    @property
    def undetermined(self) -> bool:
        """
        Returns true if this site is in a state that would be equivalent to leaving it
        unnamed in an agent pattern.
        """
        return self.state == "?" and self.partner in ("?", ".")

    @cached_property
    def underspecified(self) -> bool:
        """
        Tells you whether or not concrete `Site` instances can be created
        from this pattern, i.e. whether there are ambiguous site states
        """
        match (self.state, self.partner):
            case ("#", _) | (_, "#") | (_, "_") | (_, states.SiteType()):
                return True
            case _:
                return False

    @property
    def stated(self) -> bool:
        return self.state not in ("#", "?")

    @property
    def bound(self) -> bool:
        return self.partner == "_" or any(
            isinstance(self.partner, state) for state in [states.SiteType, Site]
        )

    @property
    def coupled(self) -> bool:
        return isinstance(self.partner, Site)

    def matches(self, other) -> bool:
        if self.stated and self.state != other.state:
            return False

        if self.bound and not other.coupled:
            return False

        match self.partner:
            case ".":
                return other.partner == "."
            case states.SiteType():
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
    def __init__(self, type: str, sites: Iterable[Site]):
        super().__init__()
        self.type = type
        self.interface = {site.label: site for site in sites}

    def __iter__(self):
        yield from self.sites

    def __getitem__(self, key: str) -> Site:
        return self.interface[key]

    def __repr__(self):
        return f"{self.type}({" ".join(str(site) for site in self)})"

    @property
    def sites(self) -> Iterable[Site]:
        yield from self.interface.values()

    @cached_property
    def underspecified(self) -> bool:
        """
        Tells you whether or not concrete `Agent` instances can be created
        from this pattern, i.e. whether there are any underspecified sites
        """
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

    def same_site_states(self, other: Self) -> bool:
        """
        Check if two `Agent`s are equivalent locally, i.e. whether they
        are identical if we ignore any `partner` fields in sites.

        NOTE: Doesn't assume agents of the same type will have the same site signatures
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


class Component(Counted):
    """
    A set of agents that are all in the same connected component (this is
    not guaranteed statically, you have to make sure it's enforced whenever
    you create or manipulate it.)

    NOTE(24-03-2025): Some new considerations following convo w/ Walter, elaborate.
    - Optionally turning off connected component tracking
    - Cost of detailed structs when it comes to FFI conversions
    """

    agents: list[Agent]
    agents_by_type: dict[str, set[Agent]]
    n_copies: int

    def __init__(self, agents: list[Agent], n_copies: int = 1):
        super().__init__()

        assert agents
        assert n_copies >= 1
        if n_copies != 1:
            raise NotImplementedError(
                "Simulations won't handle n_copies correctly in counting embeddings."
            )

        self.agents = agents  # TODO: I want this to be ordered by graph traversal
        self.agents_by_type = defaultdict(set)  # Reverse index on agent type
        for agent in agents:
            self.agents_by_type[agent.type].add(agent)
        self.n_copies = n_copies

    def __iter__(self):
        yield from self.agents

    def add(self, agent: Agent):
        self.agents.append(agent)
        self.agents_by_type[agent.type].add(agent)

    def isomorphic(self, other: Self) -> bool:
        # TODO: set __eq__ with this method?
        return next(self.isomorphisms(other), None) is not None

    def isomorphisms(self, other: Self) -> Iterator[dict[Agent, Agent]]:
        """
        Checks for bijections which respect links in the site graph,
        ensuring that any internal site state specified in one compononent
        exists and is the same in the other.

        NOTE: This is trying to handle things more general than just isomorphisms between
        instantiated components in a mixture, so that we can also potentially check
        isomorphism between rule patterns. See the cases in `test_component_isomorphism`
        (in tests/test_pattern.py) for some usage examples between component patterns and
        their expected behavior.
        """
        if len(self.agents) != len(other.agents):
            return

        a_root = self.agents[0]  # "a" refers to `self` and "b" to `other`
        # Narrow the search by mapping `a_root` to agents in `other` of the same type
        for b_root in other.agents_by_type[a_root.type]:

            agent_map = {a_root: b_root}  # The potential bijection
            frontier = {a_root}
            root_failed = False

            while frontier and not root_failed:
                a = frontier.pop()
                b = agent_map[a]

                if not a.same_site_states(b):
                    root_failed = True
                    break

                for a_site, b_site in zip(a, b):
                    if a_site.coupled and b_site.coupled:
                        if a_site.partner.agent not in agent_map:
                            frontier.add(a_site.partner.agent)
                            agent_map[a_site.partner.agent] = b_site.partner.agent
                        elif agent_map[a_site.partner.agent] != b_site.partner.agent:
                            root_failed = True
                            break
                    elif a_site.partner != b_site.partner:
                        root_failed = True
                        break

            if not root_failed:
                yield agent_map  # A valid bijection

    def __repr__(self):  # TODO: add detail
        return f'Molecule(id={self.id}, kappa_str="{self.kappa_str}")'

    @property
    def kappa_str(self, show_agent_ids=True) -> str:
        # TODO: add arg to canonicalize?
        bond_num_counter = 1
        bond_nums: dict[Site, int] = dict()
        agent_signatures = []
        for agent in self.agents:
            site_strs = []
            for site in agent:
                if site.partner == ".":
                    bond_num = None
                elif site in bond_nums:
                    bond_num = bond_nums[site]
                elif site.coupled:
                    bond_num = bond_num_counter
                    bond_nums[site.partner] = bond_num
                    bond_num_counter += 1
                else:
                    bond_num = str(site.partner)
                state_str = (
                    "{" + site.state + "}" if isinstance(site.state, str) else ""
                )
                site_strs.append(
                    f"{site.label}[{"." if bond_num is None else bond_num}]{state_str}"
                )
            agent_signatures.append(
                f"{agent.type}({"id" + str(agent.id) + ", " if show_agent_ids else ""}{' '.join(site_strs)})"
            )
        return ", ".join(agent_signatures)


class Pattern:
    agents: list[Optional[Agent]]

    def __init__(self, agents: list[Optional[Agent]]):
        """
        Compile a pattern from a list of `Agent`s whose edges are implied by integer
        link states. Replaces integer link states with references to actual partners, and
        constructs a helper object which tracks connected components in the pattern.

        # NOTE: `agents` is a list of `Optional` types to support the possibility of
        empty slots (represented by ".") in rule expression patterns.
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

    @cached_property
    def components(self) -> list[Component]:
        """
        Returns connected components.
        NOTE: some redundant loops but only slows down initialization.
        """
        unseen = set(self.agents)
        if None in unseen:
            unseen.remove(None)
        components = []
        while unseen:
            component = Component(next(iter(unseen)).depth_first_traversal)
            for agent in component:
                unseen.remove(agent)
            components.append(component)
        return components

    @cached_property
    def underspecified(self) -> bool:
        return any(agent.underspecified for agent in self.agents)
