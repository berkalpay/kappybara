from typing import Self
from dataclasses import dataclass
from collections import defaultdict
from copy import deepcopy
from warnings import warn

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
    depth_first_traversal,
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

    def instantiate_agent(self, agent_p: AgentPattern, add_to_mixture=False) -> Agent:
        """
        NOTE: Any bound sites in the provided `AgentPattern` will be reset to `EmptyState`
        in the instantiated agent. You're expected to properly create bonds between agents
        yourself after using this method call when instantiating patterns.
        """
        agent = deepcopy(agent_p)
        agent.id = self.new_id()

        for site in agent.sites.values():
            match site.internal_state:
                case str():
                    pass
                case UndeterminedState():
                    warn(
                        f"Agent pattern: {agent_p} was instantiated with an undetermined internal site state with no known default. We might want to require an agent signature for cases like these."
                    )
                    # TODO: Right now this code makes the assumption that if an internal state is undetermined in
                    # a pattern which is instantiated, the rest of the model will not depend on that internal state.
                    # Here we could alternatively force any internal states to be unambiguous by explicitly setting
                    # them in patterns which are being instantiated, with something like this error:
                    # raise NotImplementedError(
                    #     f"Without an agent signature, we don't know how to instantiate the internal state of this site: {site}"
                    # )
                    #
                    # However, once we have agent signatures we'll want to do something here like:
                    # 1. Have the mixture maintain a set of agent signatures
                    # 2. Check if there's a signature for agents of this type (or require it)
                    # 3. Use the signature to determine what state we should default to here.
                    #
                    # You could also maybe think of a way of inferring what the default state of internal states
                    # could/should be even without an explicit signature, by doing some logic with the other places
                    # this agent type is mentioned, but I don't like this approach b/c of inherent ambiguity.
                    #
                    # I'd rather just require explicit agent signatures for everything, although Walter has noted that
                    # this might make quickly prototyping models more difficult.
                case _:
                    raise AssertionError(
                        "Pattern is not specific enough to be instantiated."
                    )
            match site.link_state:
                case EmptyState():
                    pass
                case SitePattern() | UndeterminedState():
                    # NOTE: This can cause unintended behavior if you're not aware of this
                    # Be aware of this if you're writing internal methods for instantiating patterns.
                    site.link_state = EmptyState()
                case _:
                    raise AssertionError(
                        f"Agent pattern: {agent_p} is not specific enough to be instantiated."
                    )

        # TODO: Check against an agent signature to add in any sites that aren't
        # explicitly named in the `AgentPattern` and fill in default internal states

        if add_to_mixture:
            raise NotImplementedError(
                "Right now this call is only used to create agents that are added in manually later."
            )

        return agent

    def instantiate(self, pattern: Pattern, n_copies: int = 1):
        """
        TODO: n_copies feature is not actually supported right now, don't try to use it until it's impl'd
        """
        assert (
            not pattern.underspecified
        ), "Pattern is not specific enough to be instantiated."

        for component in pattern.components:
            self._instantiate_component(component, n_copies)

    def _instantiate_component(self, component: Component, n_copies: int):
        new_agents = [self.instantiate_agent(a) for a in component.agents]

        for i, agent in enumerate(component.agents):
            # Duplicate the proper link structure
            for site in agent.sites.values():
                if isinstance(site.link_state, Site):
                    partner: Site = site.link_state
                    i_partner = component.agents.index(partner.agent)
                    new_agents[i].sites[site.label].link_state = new_agents[
                        i_partner
                    ].sites[partner.label]

        new_component = Component(new_agents, n_copies)

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

        # TODO: Update APSP. This is imo the best thing to do to support horizon conditions. Don't worry
        # about it until later though, I'm more concerned with getting essential functionality for now.
        # In an incremental version the APSP should be updated at every agent/edge addition/removal above
        # in the delegated calls above.
        # raise NotImplementedError

        # 3. Update embeddings
        #    TODO: Only update embeddings of affected `ComponentPatterns`. This requires a pre-simulation step
        #    where we build a dependency graph of rules at the level of either `Rule`s or `ComponentPattern`s
        #
        # Similarly to elsewhere, for the first draft implementation we just reconstruct our indexes from scratch.
        # Eventually though, we might want to do this incrementally on every edge/agent removal/addition.
        self.match_cache_by_component = defaultdict(lambda: defaultdict(list))

        for component_pattern in self.match_cache.keys():
            embeddings = self.find_embeddings(component_pattern)
            self.match_cache[component_pattern] = embeddings

            for embedding in embeddings:
                self.match_cache_by_component[
                    self.component_of_agent(next(iter(embedding.values())))
                ][component_pattern].append(embedding)

    def _add_agent(self, agent: Agent):
        """
        Calling any of these private functions which modify the mixture is *not*
        guaranteed to keep any of our indexes up to date, which is why they should
        not be used externally.

        NOTE: The provided `agent` should not have any bound sites. Add those
        afterwards using `self._add_edge`
        """
        # Assert all sites are unbound
        assert all(
            isinstance(site.link_state, EmptyState) for site in agent.sites.values()
        )

        self.agents.add(agent)
        self.agents_by_type[agent.type].append(agent)

        # if self.enable_component_tracking: # TODO: Add this kind of thing anywhere we manage component indexes
        component = Component([agent])
        self.components.add(component)
        self.component_index[agent] = component

    def _remove_agent(self, agent: Agent):
        """
        NOTE: Any bonds associated with `agent` must be removed as well
        before trying to use this method call.
        """
        # Assert all sites are unbound
        assert all(
            isinstance(site.link_state, EmptyState) for site in agent.sites.values()
        )

        self.agents.remove(agent)
        self.agents_by_type[agent.type].remove(agent)

        # if self.enable_component_tracking:
        component = self.component_index[agent]
        assert len(component.agents) == 1
        self.components.remove(component)
        del self.component_index[agent]

    def _add_edge(self, edge: Edge):
        # TODO: sanity checks, can remove if confident about correctness
        assert edge.site1.agent in self.agents
        assert edge.site2.agent in self.agents

        # NOTE: this is another place where it might be nice to have
        # semantics like what Berk was doing, e.g. define a `bind` method
        # of `SitePattern`. I am holding off on this for now because I still
        # am not certain about linked representations like these long term in
        # the first place.
        #
        # However in other places I think it's just clearly better to clean things
        # up by using e.g. what Berk was doing with the distinction between the `sites` of
        # an Agent being just a simple list while `interface` allows us to access sites by
        # their labels. Just haven't gotten around to it. (TODO)
        edge.site1.link_state = edge.site2
        edge.site2.link_state = edge.site1

        # if self.enable_component_tracking
        agent1: Agent = edge.site1.agent
        agent2: Agent = edge.site2.agent

        component1 = self.component_index[agent1]
        component2 = self.component_index[agent2]

        if component1 == component2:
            return

        # Otherwise, merge the two components
        for a in component2.agents:
            component1.add_agent(a)
            self.component_index[a] = component1

        self.components.remove(component2)

    def _remove_edge(self, edge: Edge):
        # Sanity checking that the edge exists, can remove later
        assert edge.site1.link_state == edge.site2
        assert edge.site2.link_state == edge.site1

        edge.site1.link_state = EmptyState()
        edge.site2.link_state = EmptyState()

        # Check if component became disconnected
        agent1: Agent = edge.site1.agent
        agent2: Agent = edge.site2.agent
        old_component = self.component_index[agent1]
        assert old_component == self.component_index[agent2]

        # Update component indexes: `self.components` and `self.component_index`.
        # Once that's done, also need to update `self.match_cache_by_component`
        # (this is currently done globally in `apply_update`).
        #
        # This is required for `KappaRuleUnimolecular` and `KappaRuleBimolecular` to work correctly,
        # but not for vanilla `KappaRule`s, so we should also switch off these code paths if
        # the computation is not needed for a particular model.
        #
        # We start with the simple approach of BFSing from all disconnected agents
        # like Berk was doing. If it ends up being a bottleneck, I'm pretty confident now
        # that incremental min-cut could help a lot
        maybe_new_component = Component(depth_first_traversal(agent1))
        if agent2 not in maybe_new_component.agents:
            self.components.add(maybe_new_component)

            for a in maybe_new_component.agents:
                old_component.agents.remove(a)
                self.component_index[a] = maybe_new_component

    # def update_components(self, update: MixtureUpdate):
    #     raise NotImplementedError

    # def update_shortest_paths(self, update: MixtureUpdate):
    #     """
    #     TODO: Maintain an all pairs shortest paths (APSP) index
    #     """
    #     raise NotImplementedError

    # def update_matches(self, pattern: Pattern, update: MixtureUpdate):
    #     # Account for invalidated matches
    #     #  - Matches invalidated by removal of edges or nodes
    #     #  - Matches invalidated by *addition* of edges. This is rather unique to Kappa.
    #     #    TODO: double-check that invalidation by edge addition can only happen when there's an EmptyPredicate in the pattern
    #     raise NotImplementedError


@dataclass
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

        NOTE: Link site states in the created agent will be `EmptyState`, even if `agent_pattern`
        had bound sites originally, due to the implementation of `instantiate_agent` in `Mixture`.
        It's up to you to add any desired bonds back in manually using `self.connect_sites`.
        """
        new_agent: Agent = mixture.instantiate_agent(
            agent_pattern, add_to_mixture=False
        )

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
