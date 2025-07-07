from dataclasses import dataclass, field
from collections import defaultdict
from typing import Optional, Iterable

from kappybara.pattern import Site, Agent, Component, Pattern, Embedding
from kappybara.indexed_set import SetProperty, Property, IndexedSet

type ComponentPattern = Component
type AgentPattern = Agent


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
    agents: IndexedSet[Agent]
    _embeddings: dict[ComponentPattern, IndexedSet[Embedding]]
    _max_embedding_width: int

    def __init__(self, patterns: Optional[Iterable[Pattern]] = None):
        self.agents = IndexedSet()
        self._embeddings = {}
        self._max_embedding_width = 0

        self.agents.create_index("type", Property(lambda a: a.type))

        if patterns is not None:
            for pattern in patterns:
                # If `instantiate` has an overriding definition in a subclass,
                # then when that subclass calls this `__init__` method, its
                # override will be the one called here.
                self.instantiate(pattern)

    def instantiate(self, pattern: Pattern, n_copies: int = 1) -> None:
        assert (
            not pattern.underspecified
        ), "Pattern isn't specific enough to instantiate."
        for _ in range(n_copies):
            for component in pattern.components:
                self._instantiate_component(component, 1)

    def _instantiate_component(
        self, component: ComponentPattern, n_copies: int
    ) -> None:
        component_ordered = list(component.agents)
        new_agents = [agent.detached() for agent in component_ordered]
        new_edges = set()

        for i, agent in enumerate(component_ordered):
            # Duplicate the proper link structure
            for site in agent:
                if site.coupled:
                    partner = site.partner
                    i_partner = component_ordered.index(partner.agent)

                    new_site = new_agents[i][site.label]
                    new_partner = new_agents[i_partner][partner.label]
                    new_edges.add(Edge(new_site, new_partner))

        update = MixtureUpdate(agents_to_add=new_agents, edges_to_add=new_edges)
        self.apply_update(update)

    def embeddings(self, component: ComponentPattern) -> IndexedSet[Embedding]:
        assert (
            component in self._embeddings
        ), f"Undeclared component: {component}. To embed components, they must first be declared using `track_component`"
        return self._embeddings[component]

    def track_component(self, component: ComponentPattern):
        self._max_embedding_width = max(component.diameter, self._max_embedding_width)
        embeddings = IndexedSet(component.embeddings(self))
        embeddings.create_index("agent", SetProperty(lambda e: iter(e.values())))

        self._embeddings[component] = embeddings

    def apply_update(self, update: "MixtureUpdate") -> None:
        """
        Apply the update while keeping indices up to date
        """
        for agent in update.touched_before:
            for tracked in self._embeddings:
                self._embeddings[tracked].remove_by("agent", agent)

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

        update_region = neighborhood(update.touched_after, self._max_embedding_width)

        update_region = IndexedSet(update_region)
        update_region.create_index("type", Property(lambda a: a.type))
        for component_pattern in self._embeddings:
            new_embeddings = component_pattern.embeddings(update_region)
            for e in new_embeddings:
                self._embeddings[component_pattern].add(e)

    def _update_embeddings(self) -> None:
        for component_pattern in self._embeddings:
            self.track_component(component_pattern)

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

    def _remove_agent(self, agent: Agent) -> None:
        """
        NOTE: Any bonds associated with `agent` must be removed as well
        before trying to use this method call.
        """
        assert all(site.partner == "." for site in agent)  # Check all sites are unbound

        self.agents.remove(agent)

    def _add_edge(self, edge: Edge) -> None:
        assert edge.site1.agent in self.agents
        assert edge.site2.agent in self.agents

        edge.site1.partner = edge.site2
        edge.site2.partner = edge.site1

    def _remove_edge(self, edge: Edge) -> None:
        assert edge.site1.partner == edge.site2
        assert edge.site2.partner == edge.site1

        edge.site1.partner = "."
        edge.site2.partner = "."


@dataclass
class ComponentMixture(Mixture):
    components: IndexedSet[Component]

    def __init__(self, patterns: Optional[Iterable[Pattern]] = None):
        self.components = IndexedSet()
        self.components.create_index(
            "agent", SetProperty(lambda c: c.agents, is_unique=True)
        )

        super().__init__(patterns)

    def embeddings_in_component(
        self, match_pattern: ComponentPattern, mixture_component: Component
    ) -> list[dict[Agent, Agent]]:
        return self._embeddings[match_pattern].lookup("component", mixture_component)

    def track_component(self, component: ComponentPattern):
        super().track_component(component)

        self._embeddings[component].create_index(
            "component",
            Property(lambda e: self.components.lookup("agent", next(iter(e.values())))),
        )

    def apply_update(self, update: "MixtureUpdate") -> None:
        super().apply_update(update)

    def _update_embeddings(self) -> None:
        for component_pattern in self._embeddings:
            self.track_component(component_pattern)

    def _add_agent(self, agent: Agent) -> None:
        super()._add_agent(agent)

        component = Component([agent])
        self.components.add(component)

    def _remove_agent(self, agent: Agent) -> None:
        super()._remove_agent(agent)

        component = self.components.lookup("agent", agent)
        assert len(component.agents) == 1
        self.components.remove(component)

    def _add_edge(self, edge: Edge) -> None:
        super()._add_edge(edge)

        # If the agents are in different components, merge the components
        # TODO: incremental mincut
        component1 = self.components.lookup("agent", edge.site1.agent)
        component2 = self.components.lookup("agent", edge.site2.agent)
        if component1 == component2:
            return

        # Ensure `component2` is the smaller of the 2
        if len(component2.agents) > len(component1.agents):
            component1, component2 = component2, component1

        relocated: dict[ComponentPattern, list[Embedding]] = {}
        for tracked in self._embeddings:
            relocated[tracked] = list(
                self._embeddings[tracked].lookup("component", component2)
            )
            for e in relocated[tracked]:
                self._embeddings[tracked].remove(e)

        self.components.remove(
            component2
        )  # NOTE: This invokes a redundant linear time pass
        for agent in component2:
            component1.add(agent)
            # self.component_index[agent] = component1
            # TODO: better semantics for this type of operation
            #       Operate on diffs to set property.. ?
            # NOTE: tricky part
            self.components.indices["agent"][agent] = [component1]

        for tracked in self._embeddings:
            # TODO: come back to refactor this when we have something
            # for registering IndexedSet item updates, including cached
            # property evaluations.
            for e in relocated[tracked]:
                assert (
                    self.components.lookup("agent", next(iter(e.values())))
                    == component1
                )
                self._embeddings[tracked].add(e)

    def _remove_edge(self, edge: Edge) -> None:
        super()._remove_edge(edge)

        agent1: Agent = edge.site1.agent
        agent2: Agent = edge.site2.agent
        old_component = self.components.lookup("agent", agent1)
        assert old_component == self.components.lookup("agent", agent2)

        # Create a new component if the old one got disconnected
        maybe_new_component = Component(agent1.depth_first_traversal)

        if agent2 in maybe_new_component:
            return  # The old component is still connected, do nothing

        new_component1 = maybe_new_component
        new_component2 = Component(agent2.depth_first_traversal)

        relocated: dict[ComponentPattern, list[Embedding]] = {}
        for tracked in self._embeddings:
            relocated[tracked] = list(
                self._embeddings[tracked].lookup("component", old_component)
            )
            for e in relocated[tracked]:
                self._embeddings[tracked].remove(e)

        # TODO: A lot of redundancy here for the sake of keeping the
        # code simple for now. We could save a lot here by only
        # creating one new component and making the necessary
        # deletions, but this requires manual updates to the indices
        # in `components`.
        self.components.remove(old_component)
        self.components.add(new_component1)
        self.components.add(new_component2)

        for tracked in self._embeddings:
            # TODO: come back to refactor this when we have something
            # for registering IndexedSet item updates, including cached
            # property evaluations.
            for e in relocated[tracked]:
                assert self.components.lookup("agent", next(iter(e.values()))) in [
                    new_component1,
                    new_component2,
                ]
                self._embeddings[tracked].add(e)


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

    @property
    def touched_after(self) -> set[Agent]:
        """
        Return the agents that will/have been changed or added after this
        update is applied.
        """
        touched = self.agents_changed | set(self.agents_to_add)

        for edge in self.edges_to_add:
            touched.add(edge.site1.agent)
            touched.add(edge.site2.agent)

        for edge in self.edges_to_remove:
            a, b = edge.site1.agent, edge.site2.agent
            if a not in self.agents_to_remove:  # TODO make agents_to_remove a set
                touched.add(a)
            if b not in self.agents_to_remove:
                touched.add(b)

        return touched

    @property
    def touched_before(self) -> set[Agent]:
        """
        Lots of code redundancy, but deduplicating here would make what's
        happening in either case a lot less clear. There's also a good chance
        this version won't be needed in an improved incremental impl.
        """
        touched = self.agents_changed | set(self.agents_to_remove)

        for edge in self.edges_to_remove:
            touched.add(edge.site1.agent)
            touched.add(edge.site2.agent)

        for edge in self.edges_to_add:
            a, b = edge.site1.agent, edge.site2.agent
            if a not in self.agents_to_add:  # TODO make agents_to_add a set
                touched.add(a)
            if b not in self.agents_to_add:
                touched.add(b)

        return touched


def neighborhood(agents: Iterable[Agent], radius: int) -> set[Agent]:
    """
    Return the set of all agents within a distance of `radius`
    of any agent affected by this update.

    NOTE: You must fully apply the update before using this.
    """
    frontier = agents
    seen = set(frontier)

    for _ in range(radius):
        new_frontier = set()
        for cur in frontier:
            for n in cur.neighbors:
                seen.add(n)
                if n not in seen:
                    new_frontier.add(n)

        frontier = new_frontier

    return seen
