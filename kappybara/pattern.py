from dataclasses import dataclass
from collections import defaultdict
from functools import cached_property
from typing import Self, Iterator

from kappybara.site_states import *


@dataclass
class Site:
    label: str
    internal_state: "InternalStatePattern"
    link_state: "LinkStatePattern"
    agent: "Agent" = None

    def __hash__(self):
        return id(self)

    def __eq__(self, other):
        return hash(self) == hash(other)

    def __repr__(self):  # TODO: add detail
        res = self.label

        match self.link_state:
            case EmptyState():
                res += "[.]"
            case Site() as partner:
                res += f"[id{partner.agent.id}]"

        match self.internal_state:
            case str() as s:
                res += "{" + s + "}"

        return res

    @property
    def undetermined(self) -> bool:
        """
        Returns true if this site is in a state that would be equivalent to leaving it
        unnamed in an agent pattern.
        """
        return isinstance(self.internal_state, UndeterminedState) and (
            isinstance(self.link_state, UndeterminedState)
            or isinstance(self.link_state, EmptyState)
        )

    @cached_property
    def underspecified(self) -> bool:
        """
        Tells you whether or not concrete `Site` instances can be created
        from this pattern, i.e. whether there are ambiguous site states
        """
        match (self.internal_state, self.link_state):
            case (
                (WildCardPredicate(), _)
                | (_, WildCardPredicate())
                | (_, BoundPredicate())
                | (_, SiteTypePredicate())
            ):
                return True
            case _:
                return False


@dataclass
class Agent:
    id: int  # You must ensure this is unique in its context
    type: str
    sites: dict[str, Site]

    def __init__(self, id: int, type: str, sites: list[Site]):
        self.id = id
        self.type = type
        self.sites = {site.label: site for site in sites}

    def __hash__(self):
        # TODO: a global variable to assign deterministic IDs to important mixture objects
        return id(self)

    def __eq__(self, other):
        return id(self) == id(other)

    @cached_property
    def underspecified(self) -> bool:
        """
        Tells you whether or not concrete `Agent` instances can be created
        from this pattern, i.e. whether there are any underspecified sites
        """
        return any(site.underspecified for site in self.sites.values())

    @property
    def neighbors(self) -> list[Self]:
        return [
            site.link_state.agent
            for site in self.sites.values()
            if (isinstance(site.link_state, Site))
        ]

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


@dataclass
class Component:
    """
    A set of agents that are all in the same connected component (this is
    not guaranteed statically, you have to make sure it's enforced whenever
    you create or manipulate it.)

    NOTE: I'm including this class as a demonstration that stylistically
    follows the ideas in physics.py, but I'm pretty hesitant about committing
    to this pattern unless it's strictly just a dataclass without implemented
    methods for pattern matching/isomorphism; one concrete consideration is
    w.r.t. rectangular approximation and the necessary computations for
    observable patterns. Will try to elaborate later. (Update 26-03-2025: eh
    just go with this for now. It's actually not that important to be able to
    correct rect. approximation analytically according to Walter. Just warning
    users when they declare an %obs pattern with more than one connected component
    should be enough.)

    NOTE(24-03-2025): Some new considerations following convo w/ Walter, elaborate.
    - Optionally turning off connected component tracking
    - Cost of detailed structs when it comes to FFI conversions
    """

    agents: list[Agent]
    agents_by_type: dict[str, set[Agent]]
    n_copies: int

    def __init__(self, agents: list[Agent], n_copies: int = 1):
        assert len(agents) >= 1
        assert n_copies >= 1

        if n_copies != 1:
            raise NotImplementedError(
                "Simulation code currently will not handle the n_copies field correctly when counting embeddings."
            )

        self.agents = agents  # TODO: I want this to be ordered by graph traversal
        self.agents_by_type = defaultdict(set)  # Reverse index on agent type

        for agent in agents:
            self.agents_by_type[agent.type].add(agent)

        self.n_copies = n_copies

    def __hash__(self):
        return id(self)

    def __eq__(self, other):
        return hash(self) == hash(other)

    def add_agent(self, agent: Agent):
        """
        Adds an agent along with maintaining the type index.
        """
        self.agents.append(agent)
        self.agents_by_type[agent.type].add(agent)

    def isomorphic(self, other: Self) -> bool:
        """
        NOTE: concerns with ambiguity if we overloaded __eq__ with this method
        """
        return next(self.isomorphisms(other), None) is not None

    def isomorphisms(self, other: Self) -> Iterator[dict[Agent, Agent]]:
        """
        NOTE: There is some potential ambiguity to 'isomorphism' in the context of what
        we're trying to accomplish in this codebase. Consider two patterns, p1="A(site1[a])" and
        p2="A(site1[a], site2[b])". If we consider p1 as a rule pattern and p2 as a component
        in a mixture, then p2 should match p1, since we can embed p1 into it.

        But when we're tracking identical components in a mixture (which is what this this
        method is written for), we cannot consider these as equivalent patterns.
        This method not only checks for a bijection which respects links in the site graph,
        but also ensures that any internal site state specified in one compononent must
        exist and be the same in the other.

        NOTE: re: convo with Walter, we can't assume that agents with the same type
        will have the same site signatures.

        NOTE: This code isn't nearly as readable as most of what Berk has written so far.
        Part of this is just that it's a complicated operation. Another part is that this
        is trying to handle the problem in a bit more generality than just isomorphisms
        between instantiated components in a mixture so that we can also potentially
        check isomorphism between rule patterns. However, should discuss w/ Berk some
        of the tradeoffs here.

        TODO: There will be times when we need the explicit bijection to know which
        agents to apply rule transformations to. We'll also need methods that count
        every possible
        """
        if len(self.agents) != len(other.agents):
            return []

        # Variables labelled with "a" are associate with `self`, as with "b" and `other`
        a_root = self.agents[0]

        # Narrow down our search space by only attempting to map `a_root` with
        # agents in `other` with the same type.
        for b_root in other.agents_by_type[a_root.type]:
            # The bijection between agents of `self` and `other` that we're trying to construct
            agent_map: dict[Agent, Agent] = {a_root: b_root}

            frontier: set[Agent] = {a_root}
            search_failed: bool = False

            while frontier and not search_failed:
                a: Agent = frontier.pop()
                # TODO: sanity check, can remove if confident about correctness
                assert a in agent_map
                b: Agent = agent_map[a]

                if a.type != b.type:
                    search_failed = True
                    break

                # We use this to track sites in b which aren't mentioned in a
                b_sites_leftover = set(b.sites.keys())

                for site_name in a.sites:
                    a_site: Site = a.sites[site_name]

                    # Check that `b` has a site with the same name
                    if site_name not in b.sites and not a_site.undetermined:
                        search_failed = True
                        break

                    b_site: Site = b.sites[site_name]
                    b_sites_leftover.remove(
                        site_name
                    )  # In this way we are left with any unexamined sites in b at the end

                    # TODO: make sure types work the way we intend (singleton)
                    if a_site.internal_state != b_site.internal_state:
                        search_failed = True
                        break

                    match (a_site.link_state, b_site.link_state):
                        case (
                            Site(agent=a_partner),
                            Site(agent=b_partner),
                        ):
                            if (
                                a_partner in agent_map
                                and agent_map[a_partner] != b_partner
                            ):
                                search_failed = True
                                break

                            elif a_partner not in agent_map:
                                frontier.add(a_partner)
                                agent_map[a_partner] = b_partner
                        case (a_state, b_state) if a_state != b_state:
                            search_failed = True
                            break

                # Check leftovers not mentioned in a_sites
                for site_name in b_sites_leftover:
                    leftover_site: Site = b.sites[site_name]

                    if not leftover_site.undetermined:
                        search_failed = True
                        break

            if not search_failed:
                yield agent_map  # A valid bijection

    def __repr__(self):  # TODO: add detail
        return f'Molecule(id={id(self)}, kappa_str="{self.kappa_str}")'

    @property
    def kappa_str(self, show_agent_ids=True) -> str:
        # TODO: add arg to canonicalize?
        bond_num_counter = 1
        bond_nums: dict[Site, int] = dict()
        agent_signatures = []
        for agent in self.agents:
            site_strs = []
            for site in agent.sites.values():
                if site.link_state is None:
                    bond_num = None
                elif site in bond_nums:
                    bond_num = bond_nums[site]
                elif isinstance(site.link_state, Site):
                    bond_num = bond_num_counter
                    bond_nums[site.link_state] = bond_num
                    bond_num_counter += 1
                else:
                    bond_num = str(site.link_state)
                internal_state_str = (
                    "{" + site.internal_state + "}"
                    if isinstance(site.internal_state, str)
                    else ""
                )
                site_strs.append(
                    f"{site.label}[{"." if bond_num is None else bond_num}]{internal_state_str}"
                )
            agent_signatures.append(
                f"{agent.type}({"id" + str(agent.id) + ", " if show_agent_ids else ""}{' '.join(site_strs)})"
            )
        return ", ".join(agent_signatures)


@dataclass
class Pattern:
    agents: list[Optional[Agent]]
    components: list[
        Component
    ]  # An index on the constituent connected components making up the pattern

    def __init__(self, agents: list[Optional[Agent]]):
        """
        Compile a pattern from a list of `Agent`s whose edges are implied by integer
        link states. Replaces integer link states with references to actual partners, and
        constructs a helper object which tracks connected components in the pattern.

        # NOTE: `agents` is a list of `Optional` types to support the possibility of
        empty slots (represented by ".") in rule expression patterns.
        """
        self.agents = agents

        # Only work with actual agents from now on
        agents = [a for a in self.agents if a is not None]

        # Parse out site connections implied by integer LinkStates
        integer_links: defaultdict[int, list[Site]] = defaultdict(list)

        for agent in agents:
            for site in agent.sites.values():
                if isinstance(site.link_state, int):
                    integer_links[site.link_state].append(site)

        # Replace integer LinkStates with Agent references
        for i in integer_links:
            linked_sites = integer_links[i]
            match len(linked_sites):
                case n if n == 1:
                    raise AssertionError(
                        f"Site link {i} is only referenced in one site."
                    )
                case n if n > 2:
                    raise AssertionError(
                        f"Site link {i} is referenced in more than two sites."
                    )
                case n if n == 2:
                    linked_sites[0].link_state = linked_sites[1]
                    linked_sites[1].link_state = linked_sites[0]

        # Discover connected components
        # NOTE: some redundant loops but prioritized code simplicity;
        # worst this can do is slow down initialization.
        self.components = []
        not_seen: set[Agent] = set(agents)

        while not_seen:
            agents_in_component = next(iter(not_seen)).depth_first_traversal
            for agent in agents_in_component:
                not_seen.remove(agent)

            self.components.append(Component(agents_in_component))

    @cached_property
    def underspecified(self) -> bool:
        return any(agent.underspecified for agent in self.agents)
