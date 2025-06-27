from dataclasses import dataclass, field
from collections import defaultdict
from collections.abc import Callable, Hashable
from typing import Optional, Iterable, Generic, TypeVar, Any

from kappybara.pattern import Site, Agent, Component, Pattern
from kappybara.mixture import Edge, MixtureUpdate

T = TypeVar('T') # Parent type
Property = Callable[[T, Mixture], Hashable]
SetProperty = Callable[[T, Mixture], Collection[Hashable]]

class SetProperty:
    """
    """
    def __init__(self,
                 fn: Callable[[T, Mixture], Collection[Hashable]],
                 is_unique=False):
        self.fn = fn
        self.is_unique = is_unique

    def __call__(self, item: T) -> Collection[Hashable]:
        return self.fn(item)

class Property(SetProperty):
    def __init__(self,
                 fn: Callable[[T, Mixture], Hashable],
                 is_unique=False):
        self.fn = fn
        self.is_unique = is_unique

    def __call__(self, item: T) -> Collection[Hashable]:
        return [self.fn(item)]

class IndexedSet(set[T]):
    """
    A subclass of the built-in `set`, with support for indexing
    by arbitrary properties of set members.

    If you know for some property that you should only get a single
    set member back when using `lookup`, mark that property as unique
    when you create it.

    TODO: How to distinguish when we know that a lookup will always yield
    a single set member, versus a collection? I'm going to call the former
    "uniqueness" of a property, which formally means that for such a unique
    property, the evaluations of two different set members will never intersect.
    """
    mixture: Mixture
    properties: dict[str, Property]
    set_properties: dict[str, SetProperty]
    indices: dict[str, dict[Hashable, T]]

    def __init__(self, mixture: Mixture):
        self.mixture = mixture
        self.properties = {}
        self.set_properties = {}
        self.indices = {}

        super().__init__()

    def add(self, element):
        assert element not in self
        super().add(element)

    def remove(self, element):
        super().remove(element)

    def index_property(name: str, prop: Property):
        """
        Given a function which maps a set member to an `Any`-typed value, create
        a reverse-index mapping a property value to the set of `IndexedSet` members with
        that property. This index is updated when making appropriate calls
        through the rest of the object interface.

        NOTE: mutating set members outside of interface calls will invalidate this object.
        """

    def index_set_property(name: str, prop: SetProperty):
        """
        """


class CounterSet(IndexedSet[Counter, Component]):
    def __init__(self):


@dataclass
class Mixture:
    agents: set[Agent]
    # counters: set[Counter]
    # counter_index: set[Component, Counter]
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
        self._embeddings_by_edge =
        self._embeddings_by_agent =

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
