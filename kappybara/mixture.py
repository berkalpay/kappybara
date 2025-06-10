from dataclasses import dataclass, field
from collections import defaultdict
from typing import Optional, Iterable

from kappybara.pattern import Site, Agent, Component, Pattern


@dataclass(frozen=True)
class Edge:
    """Represents bonds between sites. Edge(x, y) is the same as Edge(y, x)."""

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
    agents_by_type: defaultdict[str, list[Agent]]

    # An index of the matches for each component in any rule or observable pattern
    _embeddings: dict[Component, list[dict[Agent, Agent]]]
    _embeddings_by_component: dict[Component, dict[Component, list[dict[Agent, Agent]]]]

    def __init__(self, patterns: Optional[Iterable[Pattern]] = None):
        self.agents = set()
        self.components = set()
        self.component_index = {}
        self.agents_by_type = defaultdict(list)
        self._embeddings = defaultdict(list)
        self._embeddings_by_component = defaultdict(lambda: defaultdict(list))

        if patterns is not None:
            for pattern in patterns:
                self.instantiate(pattern)

    def instantiate(self, pattern: Pattern, n_copies: int = 1) -> None:
        assert (
            not pattern.underspecified
        ), "Pattern isn't specific enough to instantiate."
        for _ in range(n_copies):
            for component in pattern.components:
                self._instantiate_component(component, 1)

    def _instantiate_component(self, component: Component, n_copies: int) -> None:
        new_agents = [agent.detached() for agent in component]
        new_edges = set()

        for i, agent in enumerate(component):
            # Duplicate the proper link structure
            for site in agent:
                if site.coupled:
                    partner = site.partner
                    i_partner = component.agents.index(partner.agent)

                    new_site = new_agents[i][site.label]
                    new_partner = new_agents[i_partner][partner.label]
                    new_edges.add(Edge(new_site, new_partner))

        update = MixtureUpdate(agents_to_add=new_agents, edges_to_add=new_edges)
        self.apply_update(update)
        # TODO: Update APSP

    def embeddings(self, component: Component) -> list[dict[Agent, Agent]]:
        assert (
            component in self._embeddings
        ), f"Undeclared component: {component}. To embed components, they must first be declared using `track_component`"
        return self._embeddings[component]

    def embeddings_in_component(
        self, match_pattern: Component, mixture_component: Component
    ) -> list[dict[Agent, Agent]]:
        return self._embeddings_by_component[mixture_component][match_pattern]

    def track_component(self, component: Component):
        embeddings = list(component.embeddings(self))
        self._embeddings[component] = embeddings

        for embedding in embeddings:
            self._embeddings_by_component[
                self.component_index[next(iter(embedding.values()))]
            ][component].append(embedding)

    def apply_update(self, update: "MixtureUpdate") -> None:
        """
        Apply the update and (naively) recompute embeddings from scratch.
        """
        # Order will be important, i.e. doing all removals before any additions..
        for edge in update.edges_to_remove:
            self._remove_edge(edge)
        for agent in update.agents_to_remove:
            self._remove_agent(agent)
        for agent in update.agents_to_add:
            self._add_agent(agent)
        for edge in update.edges_to_add:
            self._add_edge(edge)
        for agent in update.agents_changed:
            pass  # TODO: for incremental approaches

        self._update_embeddings()

    def _update_embeddings(self) -> None:
        self._embeddings_by_component = defaultdict(lambda: defaultdict(list))
        for component in self._embeddings:
            embeddings = list(component.embeddings(self))
            self._embeddings[component] = embeddings
            for embedding in embeddings:
                self._embeddings_by_component[
                    self.component_index[next(iter(embedding.values()))]
                ][component].append(embedding)

    def _add_agent(self, agent: Agent) -> None:
        """
        NOTE: Calling these private functions that modify the mixture isn't
        guaranteed to keep our indexes up to date, which is why they shouldn't
        be used externally.

        NOTE: The provided `agent` should not have any bound sites. Add those
        afterwards using `self._add_edge`
        """
        assert all(site.partner == "." for site in agent)  # Check all sites are unbound
        assert agent.instantiable

        self.agents.add(agent)
        self.agents_by_type[agent.type].append(agent)

        component = Component([agent])
        self.components.add(component)
        self.component_index[agent] = component

    def _remove_agent(self, agent: Agent) -> None:
        """
        NOTE: Any bonds associated with `agent` must be removed as well
        before trying to use this method call.
        """
        assert all(site.partner == "." for site in agent)  # Check all sites are unbound

        self.agents.remove(agent)
        self.agents_by_type[agent.type].remove(agent)

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
        # TODO: incremental mincut
        component1 = self.component_index[edge.site1.agent]
        component2 = self.component_index[edge.site2.agent]
        if component1 == component2:
            return
        for agent in component2:
            component1.add(agent)
            self.component_index[agent] = component1
        self.components.remove(component2)

    def _remove_edge(self, edge: Edge) -> None:
        assert edge.site1.partner == edge.site2
        assert edge.site2.partner == edge.site1

        edge.site1.partner = "."
        edge.site2.partner = "."

        agent1: Agent = edge.site1.agent
        agent2: Agent = edge.site2.agent
        old_component = self.component_index[agent1]
        assert old_component == self.component_index[agent2]

        # Create a new component if the old one got disconnected
        # TODO: improve efficiency with incremental min-cut?
        maybe_new_component = Component(agent1.depth_first_traversal)
        if agent2 not in maybe_new_component.agents:
            self.components.add(maybe_new_component)
            for agent in maybe_new_component:
                old_component.agents.remove(agent)
                self.component_index[agent] = maybe_new_component


@dataclass
class MixtureUpdate:
    """Indicates which changes should occur in the mixture."""

    agents_to_add: list[Agent] = field(default_factory=list)
    agents_to_remove: list[Agent] = field(default_factory=list)
    edges_to_add: set[Edge] = field(default_factory=set)
    edges_to_remove: set[Edge] = field(default_factory=set)
    agents_changed: set[Agent] = field(default_factory=set)  # Agents changed internally

    def create_agent(self, agent: Agent) -> Agent:
        """NOTE: Sites in the created agent will be emptied."""
        new_agent = agent.detached()
        self.agents_to_add.append(new_agent)
        return new_agent

    def remove_agent(self, agent: Agent) -> None:
        """Specify to remove the agent and its edges from the mixture."""
        self.agents_to_remove.append(agent)
        for site in agent:
            if site.coupled:
                self.edges_to_remove.add(Edge(site, site.partner))

    def connect_sites(self, site1: Site, site2: Site) -> None:
        """
        Indicate there should be an edge between two sites. If the
        sites are bound to other sites, indicate to remove those edges.
        """
        if site1.coupled and site1.partner != site2:
            self.disconnect_site(site1)
        if site2.coupled and site2.partner != site1:
            self.disconnect_site(site2)
        if not site1.partner == site2:
            self.edges_to_add.add(Edge(site1, site2))

    def disconnect_site(self, site: Site) -> None:
        """Indicate that the site should be unbound."""
        if site.coupled:
            self.edges_to_remove.add(Edge(site, site.partner))

    def register_changed_agent(self, agent: Agent) -> None:
        self.agents_changed.add(agent)
