from dataclasses import dataclass
from collections import defaultdict
from copy import deepcopy

import kappybara.site_states as states
from kappybara.pattern import Site, Agent, Component, Pattern


@dataclass
class Edge:
    """
    A data structure to represent bonds to use as keys to a set/dict.
    Its hash should be unordered: Edge(x, y) is the same as Edge(y, x).

    TODO: make this a frozen dataclass? Could simply cache hashes then.
    """

    site1: Site
    site2: Site

    def __eq__(self, other):
        return (self.site1 == other.site1 and self.site2 == other.site2) or (
            self.site1 == other.site2 and self.site2 == other.site1
        )

    def __hash__(self):
        return hash(frozenset((self.site1, self.site2)))


@dataclass
class Mixture:
    agents: set[Agent]
    components: set[Component]
    component_index: dict[Agent, Component]  # Maps agents to their components
    agents_by_type: dict[str, set[Agent]]

    # An index of the matches for each component in any rule or observable pattern
    match_cache: dict[Component, list[dict[Agent, Agent]]]
    match_cache_by_component: dict[Component, dict[Component, list[dict[Agent, Agent]]]]

    def __init__(self):
        self.agents = set()
        self.components = set()
        self.component_index = {}
        self.agents_by_type = defaultdict(list)
        self.match_cache = defaultdict(list)
        self.match_cache_by_component = defaultdict(lambda: defaultdict(list))

    def instantiate(self, pattern: Pattern, n_copies: int = 1):
        assert (
            not pattern.underspecified
        ), "Pattern is not specific enough to be instantiated."

        for component in pattern.components:
            self._instantiate_component(component, n_copies)

    def _instantiate_component(self, component: Component, n_copies: int):
        new_agents = [agent.detached() for agent in component.agents]

        for i, agent in enumerate(component.agents):
            # Duplicate the proper link structure
            for site in agent:
                if site.coupled:
                    partner: Site = site.partner
                    i_partner = component.agents.index(partner.agent)
                    new_agents[i].sites[site.label].partner = new_agents[
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

    def embeddings(self, component: Component) -> list[dict[Agent, Agent]]:
        embeddings = []

        a_root = component.agents[0]  # "a" refers to `component`, "b" refers to `self`
        for b_root in self.agents_by_type[a_root.type]:
            potential_embedding = {a_root: b_root}
            frontier = {a_root}
            search_failed = False

            while frontier and not search_failed:
                a = frontier.pop()
                b = potential_embedding[a]

                if a.type != b.type:
                    search_failed = True
                    break

                for site_name in a.sites:
                    a_site = a.sites[site_name]
                    if site_name not in b.sites and not a_site.undetermined:
                        search_failed = True
                        break
                    b_site = b.sites[site_name]

                    if not a_site.matches(b_site):
                        search_failed = True
                        break

                    if a_site.coupled:
                        a_partner = a_site.partner.agent
                        b_partner = b_site.partner.agent
                        if (
                            a_partner in potential_embedding
                            and potential_embedding[a_partner] != b_partner
                        ):
                            search_failed = True
                            break
                        elif a_partner not in potential_embedding:
                            frontier.add(a_partner)
                            potential_embedding[a_partner] = b_partner

            if not search_failed:
                embeddings.append(potential_embedding)

        return embeddings

    def update_embeddings(self):
        pass

    def fetch_embeddings(self, component: Component) -> list[list[Agent]]:
        """
        TODO: Take advantage of isomorphism redundancies
        """
        return self.match_cache[component]

    def fetch_embeddings_in_component(
        self, match_pattern: Component, mixture_component: Component
    ) -> list[list[Agent]]:
        return self.match_cache_by_component[mixture_component][match_pattern]

    def track_component(self, component: Component):
        embeddings = self.embeddings(component)
        self.match_cache[component] = embeddings

        for embedding in embeddings:
            self.match_cache_by_component[
                self.component_index[next(iter(embedding.values()))]
            ][component].append(embedding)

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

        self._update_embeddings()

    def _update_embeddings(self):
        # TODO: Update APSP. This is imo the best thing to do to support horizon conditions. Don't worry
        # about it until later though, I'm more concerned with getting essential functionality for now.
        # In an incremental version the APSP should be updated at every agent/edge addition/removal above
        # in the delegated calls above.
        # raise NotImplementedError

        # 3. Update embeddings
        #    TODO: Only update embeddings of affected `Component`s. This requires a pre-simulation step
        #    where we build a dependency graph of rules at the level of either `Rule`s or `Component`s
        #
        # Similarly to elsewhere, for the first draft implementation we just reconstruct our indexes from scratch.
        # Eventually though, we might want to do this incrementally on every edge/agent removal/addition.
        self.match_cache_by_component = defaultdict(lambda: defaultdict(list))
        for component in self.match_cache:
            embeddings = self.embeddings(component)
            self.match_cache[component] = embeddings
            for embedding in embeddings:
                self.match_cache_by_component[
                    self.component_index[next(iter(embedding.values()))]
                ][component].append(embedding)

    def _add_agent(self, agent: Agent):
        """
        Calling any of these private functions which modify the mixture is *not*
        guaranteed to keep any of our indexes up to date, which is why they should
        not be used externally.

        NOTE: The provided `agent` should not have any bound sites. Add those
        afterwards using `self._add_edge`
        """
        # Assert all sites are unbound
        assert all(isinstance(site.partner, states.Empty) for site in agent)
        assert agent.instantiable

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
        assert all(isinstance(site.partner, states.Empty) for site in agent)

        self.agents.remove(agent)
        self.agents_by_type[agent.type].remove(agent)

        # if self.enable_component_tracking:
        component = self.component_index[agent]
        assert len(component.agents) == 1
        self.components.remove(component)
        del self.component_index[agent]

    def _add_edge(self, edge: Edge) -> None:
        assert edge.site1.agent in self.agents
        assert edge.site2.agent in self.agents

        edge.site1.partner = edge.site2
        edge.site2.partner = edge.site1

        # If the agents are in different components, merge the components
        # TODO: if self.enable_component_tracking
        component1 = self.component_index[edge.site1.agent]
        component2 = self.component_index[edge.site2.agent]
        if component1 == component2:
            return
        for agent in component2.agents:
            component1.add_agent(agent)
            self.component_index[agent] = component1
        self.components.remove(component2)

    def _remove_edge(self, edge: Edge):
        assert edge.site1.partner == edge.site2
        assert edge.site2.partner == edge.site1

        edge.site1.partner = states.Empty()
        edge.site2.partner = states.Empty()

        agent1: Agent = edge.site1.agent
        agent2: Agent = edge.site2.agent
        old_component = self.component_index[agent1]
        assert old_component == self.component_index[agent2]

        # Create a new component if the old one got disconnected
        # TODO: don't do component indexing if not required by the rules?
        # TODO: improve efficiency with incremental min-cut?
        maybe_new_component = Component(agent1.depth_first_traversal)
        if agent2 not in maybe_new_component.agents:
            self.components.add(maybe_new_component)
            for agent in maybe_new_component.agents:
                old_component.agents.remove(agent)
                self.component_index[agent] = maybe_new_component

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
    #     #    TODO: double-check that invalidation by edge addition can only happen when there's an Empty predicate in the pattern
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
        """Specify to remove the agent and its edges from the mixture."""
        self.agents_to_remove.append(agent)
        for site in agent:
            if site.coupled:
                self.edges_to_remove.add(Edge(site, site.partner))

    def create_agent(self, agent: Agent) -> Agent:
        """NOTE: Sites in the created agent will be emptied."""
        new_agent = agent.detached()
        self.agents_to_add.append(new_agent)
        return new_agent

    def register_changed_agent(self, agent: Agent):
        self.agents_changed.add(agent)

    def disconnect_site(self, site: Site):
        """
        If `site` is bound, indicate that it should be unbound.
        Does nothing if `site` is already empty.

        All removed bonds (indicated in `self.edges_to_remove`) will be
        applied before any new bonds (`self.edges_to_add`) are created
        when this `MixtureUpdate` is actually applied.
        """
        if site.coupled:
            self.edges_to_remove.add(Edge(site, site.partner))

    def connect_sites(self, site1: Site, site2: Site):
        """
        Indicate there should be an edge between two sites. If either of the
        sites are already bound to some other agent, this will indicate those
        bonds for removal.
        """

        # Indicate the removal of bonds to the wrong agents
        if site1.coupled and site1.partner != site2:
            self.disconnect_site(site1)
        if site2.coupled and site2.partner != site1:
            self.disconnect_site(site2)

        # Indicate these sites should be bound if they aren't already
        if not (site1.coupled and site2.coupled and site1.partner == site2):
            self.edges_to_add.add(Edge(site1, site2))
