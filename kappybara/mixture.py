from typing import Self
from dataclasses import dataclass
from collections import defaultdict
from copy import deepcopy

from kappybara.site_states import *
from kappybara.pattern import SitePattern, AgentPattern, MoleculePattern, Pattern

def cantor(x: int, y: int) -> int:
    """
    https://en.wikipedia.org/wiki/Pairing_function#Cantor_pairing_function

    """
    return ((x + y) * (x + y + 1)) // 2 + y


class Edge:
    site1: SitePattern
    site2: SitePattern

    def __eq__(self, other: Self):
        return (self.site1 == other.site1 and self.site2 == other.site2) or (
            self.site1 == other.site2 and self.site2 == other.site1
        )

    def __hash__(self):
        """
        TODO: this has some failure cases due to integer overflow.
        """
        return cantor(
            cantor(hash(site1), hash(site1.agent)),
            cantor(hash(site2), hash(site2.agent)),
        )


@dataclass
class Mixture:
    agents: set[AgentPattern]
    components: set[MoleculePattern]
    _nonce: int  # Used to assign id's to instantiated agents.

    # An index matching each agent in the mixture to the connected
    # component in the mixture it belongs to
    component_index: dict[AgentPattern, MoleculePattern]

    agents_by_type: dict[str, set[AgentPattern]]

    # An index of the matches for each component in any rule or observable pattern
    pattern_match_cache: dict[MoleculePattern, list[list[AgentPattern]]]

    def __init__(self):
        self.agents = set()
        self.components = set()
        self._nonce = 0
        self.component_index = {}
        self.agents_by_type = defaultdict(list)
        self.component_match_cache = {}

    def instantiate(self, pattern: Pattern, n_copies: int = 1):
        assert (
            not pattern.underspecified
        ), "Pattern is not specific enough to be instantiated"

        for component in pattern.components:
            self._instantiate_component(component, n_copies)

    def _instantiate_component(self, component: MoleculePattern, n_copies: int):
        new_agents = [deepcopy(agent) for agent in component.agents]

        for i, agent in enumerate(component.agents):
            # Reassign agent id
            new_agents[i].id = self.new_id()

            # Duplicate the proper link structure
            for site in agent.sites.values():
                if isinstance(site.link_state, SitePattern):
                    partner: SitePattern = site.link_state
                    i_partner = component.agents.index(partner.agent)
                    new_agents[i].sites[site.label].link_state = new_agents[i_partner].sites[
                        partner.label
                    ]

        new_component = MoleculePattern(new_agents)

        # Update mixture contents
        self.agents.update(new_agents)

        # Update indices
        self.components.add(new_component)

        for agent in new_agents:
            self.agents_by_type[agent.type].append(agent)
            self.component_index[agent] = new_component

        # TODO: Update APSP

    def new_id(self) -> int:
        self._nonce += 1
        return self._nonce - 1

    def find_embeddings(self, component: MoleculePattern) -> list[dict[AgentPattern, AgentPattern]]:
        # Variables labelled with "a" are associate with `component`, as with "b" and `self`
        a_root = component.agents[0]

        # The set of valid bijections
        valid_maps: list[dict[AgentPattern, AgentPattern]] = []

        # Narrow down our search space by only attempting to map `a_root` with
        # agents in `self` with the same type.
        for b_root in self.agents_by_type[a_root.type]:
            # The bijection between agents of `pattern` and `self` that we're trying to construct
            agent_map: dict[AgentPattern, AgentPattern] = {a_root: b_root}

            frontier: set[AgentPattern] = {a_root}
            search_failed: bool = False

            while frontier and not search_failed:
                a: AgentPattern = frontier.pop()
                b: AgentPattern = agent_map[a]

                if a.type != b.type:
                    search_failed = True
                    break

                for site_name in a.sites:
                    a_site: SitePattern = a.sites[site_name]

                    # Check that `b` has a site with the same name
                    if site_name not in b.sites and not a_site.undetermined():
                        search_failed = True
                        break

                    b_site: SitePattern = b.sites[site_name]

                    # Check internal state
                    match a_site.internal_state:
                        case WildCardPredicate() | UndeterminedState():
                            pass
                        case InternalState():
                            if a_site.internal_state != b_site.internal_state:
                                search_failed = True
                                break

                    # Check link state
                    match a_site.link_state:
                        case WildCardPredicate() | UndeterminedState():
                            pass
                        case EmptyState():
                            if not isinstance(b_site.link_state, EmptyState):
                                search_failed = True
                                break
                        case BoundPredicate():
                            if not isinstance(b_site.link_state, SitePattern):
                                search_failed = True
                                break
                        case SiteTypePredicate():
                            if not isinstance(b_site.link_state, SitePattern):
                                search_failed = True
                                break
                            b_partner: SitePattern = b_site.link_state
                            if (
                                a_site.link_state.site_name != b_partner.label
                                and a_site.link_state.agent_name != b_partner.agent.type
                            ):
                                search_failed = True
                                break
                        case SitePattern(agent=a_partner):
                            if not isinstance(b_site.link_state, SitePattern):
                                search_failed = True
                                break
                            b_partner = b_site.link_state.agent
                            if (
                                a_partner in agent_map
                                and agent_map[a_partner] != b_partner
                            ):
                                search_failed = True
                                break

                            elif a_partner not in agent_map:
                                frontier.add(a_partner)
                                agent_map[a_partner] = b_partner

            if not search_failed:
                # We know we've constructed an acceptable isomorphism
                valid_maps.append(agent_map)

        return valid_maps

    # def apply_rule(self, rule: Rule):
    #     raise NotImplementedError

    # def apply_update(self, update: MixtureUpdate):
    #     # 1. Update `components`
    #     #
    #     # 2. TODO: Update APSP (?)
    #     #
    #     # 3. Update rule matches
    #     #    TODO: Only update affected rule matches
    #     raise NotImplementedError

    # def update_components(self, update: MixtureUpdate):
    #     raise NotImplementedError

    # def update_shortest_paths(self, update: MixtureUpdate):
    #     """
    #     TODO:
    #     """
    #     raise NotImplementedError

    # def update_matches(self, pattern: Pattern, update: MixtureUpdate):
    #     # Account for invalidated matches
    #     #  - Matches invalidated by removal of edges or nodes
    #     #  - Matches invalidated by *addition* of edges. This is rather unique to Kappa.
    #     #    TODO: double-check that invalidation by edge addition can only happen when there's an EmptyPredicate in the pattern

    #     # Add
    #     raise NotImplementedError


class MixtureUpdate:
    removed_edges: list[Edge]
    removed_agents: list[AgentPattern]
    added_edges: list[Edge]
    added_agents: list[AgentPattern]
