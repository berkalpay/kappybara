from typing import Self
from dataclasses import dataclass
from collections import defaultdict
from copy import deepcopy

from kappybara.site_states import *
from kappybara.edge import Edge
from kappybara.pattern import (
    SitePattern,
    AgentPattern,
    ComponentPattern,
    Pattern,
    Site,
    Agent,
    Component,
)


@dataclass
class Mixture:
    agents: set[Agent]
    components: set[Component]
    _nonce: int  # Used to assign id's to instantiated agents.

    # An index matching each agent in the mixture to the connected
    # component in the mixture it belongs to
    component_index: dict[Agent, Component]

    agents_by_type: dict[str, set[Agent]]

    # An index of the matches for each component in any rule or observable pattern
    match_cache: dict[ComponentPattern, list[dict[AgentPattern, Agent]]]
    match_cache_by_component: dict[
        Component, dict[ComponentPattern, list[dict[AgentPattern, Agent]]]
    ]

    def __init__(self):
        self.agents = set()
        self.components = set()
        self._nonce = 0
        self.component_index = {}
        self.agents_by_type = defaultdict(list)
        self.match_cache = defaultdict(list)
        self.match_cache_by_component = defaultdict(lambda: defaultdict(list))

    def instantiate(self, pattern: Pattern, n_copies: int = 1):
        """
        TODO: n_copies feature is not actually supported right now, don't try to use it until it's impl'd
        """
        assert (
            not pattern.underspecified
        ), "Pattern is not specific enough to be instantiated"

        for component in pattern.components:
            self._instantiate_component(component, n_copies)

    def _instantiate_component(self, component: Component, n_copies: int):
        new_agents = [deepcopy(agent) for agent in component.agents]

        for i, agent in enumerate(component.agents):
            # Reassign agent id
            new_agents[i].id = self.new_id()

            # Duplicate the proper link structure
            for site in agent.sites.values():
                if isinstance(site.link_state, Site):
                    partner: Site = site.link_state
                    i_partner = component.agents.index(partner.agent)
                    new_agents[i].sites[site.label].link_state = new_agents[
                        i_partner
                    ].sites[partner.label]

        new_component = Component(new_agents)

        # Update mixture contents
        self.agents.update(new_agents)

        # Update component indices
        self.components.add(new_component)

        for agent in new_agents:
            self.agents_by_type[agent.type].append(agent)
            self.component_index[agent] = new_component

        # TODO: Update APSP

    def component_of_agent(self, agent):
        return self.component_index[agent]

    def new_id(self) -> int:
        self._nonce += 1
        return self._nonce - 1

    def find_embeddings(
        self, component: ComponentPattern
    ) -> list[dict[AgentPattern, Agent]]:
        # Variables labelled with "a" are associate with `component`, as with "b" and `self`
        a_root = component.agents[0]

        # The set of valid bijections
        valid_maps: list[dict[AgentPattern, Agent]] = []

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
                # We know we've constructed an acceptable embedding
                valid_maps.append(agent_map)

        return valid_maps

    def update_embeddings(self):
        pass

    def fetch_embeddings(self, component: ComponentPattern) -> list[list[Agent]]:
        """
        TODO: Take advantage of isomorphism redundancies
        """
        return self.match_cache[component]

    def fetch_embeddings_in_component(
        self, match_pattern: ComponentPattern, mixture_component: Component
    ) -> list[list[Agent]]:
        return self.match_cache_by_component[mixture_component][match_pattern]

    def track_component_pattern(self, component: ComponentPattern):
        embeddings = self.find_embeddings(component)
        self.match_cache[component] = embeddings

        for embedding in embeddings:
            # TODO: Remove these debug prints
            # print("embedding", embedding)
            # print("component_of_agent", self.component_of_agent(next(iter(embedding.values()))))
            # print(component)
            self.match_cache_by_component[
                self.component_of_agent(next(iter(embedding.values())))
            ][component].append(embedding)

    # TODO: Quoted type reference due to circular reference with `MixtureUpdate`,
    # see the comments in `add_agent` there.
    def apply_update(self, update: "MixtureUpdate"):
        """
        In this first implementation, we will just apply the update and then
        naively recompute all of our indexes from scratch, without taking advantage
        of any of the incremental properties of our computation. However, the reason
        that we separate out the work of determining an update (i.e. the logic in the
        `select` method of `Rule`), as opposed to actually applying it (the logic in
        this method), is so that we can do something better here that actually recomputes
        indexes based on `update` itself, rather than recomputing on the entire mixture.
        """

        # Order will be important later, i.e. doing all removals before any additions
        # Also removing edges before agents, so that agents aren't removed until all their
        # associated edges are removed already. Right now we are assuming that the
        # `MixtureUpdate` is constructed with this in mind already so we don't have to check
        # for dangling edges here.
        for edge in update.edges_to_remove:
            self._remove_edge(edge)

        for agent in update.agents_to_remove:
            self._remove_agent(agent)

        for agent in update.agents_to_add:
            self._add_agent(agent)

        for edge in update.edges_to_add:
            self._add_edge(edge)

        for agent in update.agents_changed:
            # For the naive approach we don't have to do anything here, but
            # for incremental approaches it's important to know about any agents
            # who haven't been removed/added but whose internal states have changed.
            pass

        # 1. TODO: update component indexes: `self.components` and `self.component_index`.
        # Once that's done, also update `self.match_cache_by_component` in (3).
        # `KappaRuleUnimolecular` and `KappaRuleBimolecular` `won't work correctly until we
        # do this, since they depend on these indexes being correct/up to date when counting
        # embeddings and selecting rewrites.
        #
        # We should start with the simple approach of BFSing from all disconnected agents
        # like Berk was doing. If it ends up being a bottleneck, I'm pretty confident now
        # that incremental min-cut will help a lot
        # raise NotImplementedError

        # 2. TODO: Update APSP. Don't worry about this until every other todo here is finished.
        # raise NotImplementedError

        # 3. Update embeddings
        #    TODO: Only update embeddings of affected `ComponentPatterns`. This requires a pre-simulation step
        #    where we build a dependency graph of rules at the level of either `Rule`s or `ComponentPattern`s
        for component_pattern in self.match_cache.keys():
            self.match_cache[component_pattern] = self.find_embeddings(
                component_pattern
            )

            # TODO: Update `self.match_cache_by_component` here as well, after (1) is implemented,
            # by doing the same thing as in `self.track_component`.
            # Again, this is necessary for uni/bimolecular rules to work correctly.

    def _add_agent(self, agent: Agent):
        """
        Calling any of these private functions which modify the mixture is *not*
        guaranteed to keep any of our indexes up to date, which is why they should
        not be used externally.
        """
        self.agents.add(agent)
        self.agents_by_type[agent.type].add(agent)

    def _delete_agent(self, agent: Agent):
        self.agents.remove(agent)
        self.agents_by_type[agent.type].remove(agent)

    def _add_edge(self, edge: Edge):
        # TODO: sanity checks, can remove if confident about correctness
        assert edge.site1.agent in self.agents
        assert edge.site2.agent in self.agents

        # NOTE: this is another place where it might be nice to have
        # semantics like what Berk was doing, e.g. define a `bind` method
        # of `SitePattern`. I am holding off on this for now because I still
        # am not certain about linked representations like these long term.
        #
        # However in other places I think it's just clearly better to clean things
        # up by using e.g. what Berk was doing with the distinction between the `sites` of
        # an Agent being just a simple list while `interface` allows us to access sites by
        # their labels. Just haven't gotten around to it. (TODO)
        edge.site1.link_state = edge.site2
        edge.site2.link_state = edge.site1

    def _remove_edge(self, edge: Edge):
        # Sanity checking that the edge exists, can remove later
        assert edge.site1.link_state == edge.site2
        assert edge.site2.link_state == edge.site1

        edge.site1.link_state = EmptyState()
        edge.site2.link_state = EmptyState()

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
    """
    Rather than having a `Rule` modify a `Mixture` directly when we select it, we
    instead ask it to indicate what changes *should* occur in the mixture using this object.
    """

    agents_to_add: list[Agent]
    agents_to_remove: list[Agent]
    edges_to_add: set[Edge]
    edges_to_remove: set[Edge]

    # Agents which have sites whose *internal* state should change
    # If an agent's internal site states should all remain unchanged, but
    # their link states have changed, you don't have to add it here, just
    # use the `disconnect_site` and `connect_sites` to indicate the changed edges.
    agents_changed: set[Agent]

    def __init__(self):
        self.agents_to_add = []
        self.agents_to_remove = []
        self.edges_to_add = set()
        self.edges_to_remove = set()
        self.agents_changed = set()

    def remove_agent(self, agent: Agent):
        """
        This function call will not actually change anything in a mixture.
        """
        # Specify this agent should be deleted
        self.agents_to_remove.append(agent)

        # Also remove any edges the removed agent was associated with
        for site in agent.sites.values():
            if isinstance(site.link_state, Site):
                self.edges_to_remove.append(Edge(site, site.link_state))

    def create_agent(self, agent_pattern: AgentPattern, mixture: Mixture) -> Agent:
        """
        It is important to note again that this method does not actually add
        the created agent to the mixture. `mixture` is an argument here only because
        we need it to assign a new agent ID.

        NOTE: Link state references in the created agent will be empty, even if `agent_pattern`
        has bound sites. It's up to the user to make this call to every agent they want instantiated,
        and then adding any desired bonds back in manually using `self.connect_sites`.

        TODO: It's necessary to assign a fresh ID, whether here or when applying the `MixtureUpdate`?
        I'll go with here for now, right when it's created. But more generally
        ensuring that we don't mess up with id assignment for instantiated agents
        right now is super ad-hoc and I'd like to think of a better design pattern for this.
        Relatedly, there is a circular reference here with `Mixture` that we could maybe
        factor out if we organized things better.
        """
        # TODO: Better design for instantiating agents from patterns.
        # If we had something nicer we wouldn't have to manually reset link states as below
        new_agent: Agent = deepcopy(agent_pattern)

        # Reset any occupied link state to empty
        for site in new_agent.sites.values():
            if isinstance(site.link_state, Site):
                site.link_state = EmptyState()

        new_agent.id = mixture.new_id()

        self.agents_to_add.append(new_agent)

        return new_agent

    def disconnect_site(self, site: Site):
        """
        If `site` is bound, indicate that it should be unbound.
        Does nothing if `site` is already empty.

        All removed bonds (indicated in `self.edges_to_remove`) will be
        applied before any new bonds (`self.edges_to_add`) are created
        when this `MixtureUpdate` is actually applied.
        """
        if isinstance(site.link_state, Site):
            self.edges_to_remove.add(Edge(site, site.link_state))

    def connect_sites(self, site1: Site, site2: Site):
        """
        Indicate that two `Site`s should be connected (i.e. an edge should exist between them).

        NOTE: If either of the `Site`s are already bound to some
        other agent, this method will also indicate those existing bonds
        for removal.
        """

        # Indicate the removal of bonds to the wrong agents
        if isinstance(site1.link_state, Site) and site1.link_state != site2:
            self.disconnect_site(site1)

        if isinstance(site2.link_state, Site) and site2.link_state != site1:
            self.disconnect_site(site2)

        # Indicate these sites should be bound if they aren't already
        if not (
            isinstance(site1.link_state, Site)
            and isinstance(site2.link_state, Site)
            and site1.link_state == site2
        ):
            self.edges_to_add.add(Edge(site1, site2))
