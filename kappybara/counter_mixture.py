from kappybara.indexed_set import SetProperty, Property, IndexedSet
from kappybara.pattern import Site, Agent, Component, Pattern, Embedding
from kappybara.mixture import ComponentMixture, MixtureUpdate


class Counter:
    """
    A collection of isomorphic components of a mixture.
    """

    copies: IndexedSet[Component]

    def __init__(self, rep: Component):
        self.copies = IndexedSet([rep])

    @property
    def rep(self):
        """
        This property is not guaranteed to be consistent across accesses.
        Its only intended purpose is to provide an arbitrary member for
        isomorphism checks.
        """
        return next(iter(self.copies))

    def add(self, component: Component):
        """
        This method should ordinarily be used only after the provided
        component is known to be isomorphic to other copies, so we can
        probably remove the assertion below.
        """
        assert component.isomorphic(self.rep)

        self.copies.add(component)

    def remove(self, component: Component):
        self.copies.remove(component)


class CounterMixture(ComponentMixture):
    counters: IndexedSet[Counter]
    counter_size_limit: int

    def __init__(self, counter_size_limit=1):
        super().__init__()

        self.counter_size_limit = counter_size_limit
        self.counters = IndexedSet()
        self.counters.create_index(
            "component_size", Property(lambda counter: len(counter.rep.agents))
        )
