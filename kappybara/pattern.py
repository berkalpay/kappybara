from dataclasses import dataclass
from collections import defaultdict
from functools import cached_property
from typing import Self, List, Dict

from kappybara.site_states import *
from kappybara.physics import Site, Agent, Mixture
from lark import ParseTree#, Visitor, Tree, Token


def depth_first_traversal(start: Agent) -> list[Agent]:
    visited = set()
    traversal = []
    stack = [start]
    while stack:
        if (agent := stack.pop()) not in visited:
            visited.add(agent)
            traversal.append(agent)
            stack.extend(agent.neighbors)
    return traversal


@dataclass
class SitePattern:
    label: str
    internal_state: "InternalStatePattern"
    link_state: "LinkStatePattern"
    agent: "AgentPattern" = None

    def create_instance(self) -> Site:
        assert (
            not self.underspecified
        ), f"Site pattern: {self} is not specific enough to be instantiated in a mixture"

        raise NotImplementedError

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
class AgentPattern:
    id: int  # You must ensure this is unique in its context
    type: str
    sites: List[SitePattern]

    def __hash__(self):
        return self.id

    def create_instance(self) -> Site:
        assert (
            not self.underspecified
        ), "Agent pattern is not specific enough to be instantiated"

        raise NotImplementedError

    @cached_property
    def underspecified(self) -> bool:
        """
        Tells you whether or not concrete `Agent` instances can be created
        from this pattern, i.e. whether there are any underspecified sites
        """
        return all(site.underspecified for site in self.sites)

    @property
    def neighbors(self) -> list[Self]:
        return [
            site.link_state.agent
            for site in self.sites
            if (isinstance(site.link_state, SitePattern))
        ]


@dataclass
class MoleculePattern:
    """
    A set of agents that are all in the same connected component (this is
    not guaranteed statically), you have to make sure it's enforced when you create it.

    NOTE: I'm including this class as a demonstration that stylistically
    follows the ideas in physics.py, but I'm pretty hesitant about committing
    to this pattern unless it's strictly just a dataclass without implemented
    methods for pattern matching/isomorphism; one concrete consideration is
    w.r.t. rectangular approximation and the necessary computations for
    observable patterns. Will try to elaborate later.

    NOTE(24-03-2025): Some new considerations following convo w/ Walter, elaborate.
    - Optionally turning off connected component tracking
    - Cost of detailed structs when it comes to FFI conversions
    """

    agents: List[AgentPattern]

    def isomorphic(self, other: MoleculePattern):
        """
        NOTE: There is some potential ambiguity to 'isomorphism' in the context of what
        we're trying to accomplish in this codebase.
        with potentially distinct meanings. Consider two patterns, p1="A(site1[a])" and
        p2="A(site1[a], site2[b])". If we consider p1 as a rule pattern and p2 as a component
        in a mixture, then p2 should match p1,

        But when we're tracking identical components (which is what this ), we cannot
        consider these as equivalent patterns. For the purpose of
        This method not only checks for a bijection which respects links in the site graph,
        but also ensures that any internal site state specified in one compononent must
        exist and be the same in the other.

        We assume that both of these components are
        """



@dataclass
class Pattern:
    agents: List[AgentPattern]
    connected_components: List[
        List[AgentPattern]
    ]  # An index on the constituent connected components making up the pattern

    def __init__(self, agents: List[AgentPattern]):
        """
        Compile a pattern from a list of `AgentPatterns` whose edges are implied by integer
        link states. Replaces integer link states with references to actual partners, and
        constructs a helper object which tracks connected components in the pattern.
        """
        self.agents = agents

        # Parse out site connections implied by integer LinkStates
        integer_links: defaultdict[int, list[SitePattern]] = defaultdict(list)

        for agent in self.agents:
            for site in agent.sites:
                if isinstance(site.link_state, int):
                    if site.link_state in integer_links:
                        integer_links[site.link_state].append(site)
                    else:
                        integer_links[site.link_state] = [site]

        # Replace integer LinkStates with AgentPattern references
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
        not_seen: Set[AgentPattern] = set(agents)

        while not_seen:
            component = depth_first_traversal(next(iter(not_seen)))
            for agent in component:
                not_seen.remove(agent)

            self.components.append(component)

    @cached_property
    def underspecified(self) -> bool:
        return all(agent.underspecified for agent in self.agents)

    def create_instance(self) -> Site:
        assert (
            not self.underspecified
        ), "Pattern is not specific enough to be instantiated"

        raise NotImplementedError

    def matches(self, mixture: Mixture):
        raise NotImplementedError

    def find_all_matches(self, mixture: Mixture):
        raise NotImplementedError


def test_pattern_isomorphism():
    pass


