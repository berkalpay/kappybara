from dataclasses import dataclass, field
from collections import defaultdict
from collections.abc import Callable, Hashable
from typing import Optional, Iterable, Generic, TypeVar, Any

T = TypeVar("T")  # Parent type


class SetProperty:
    def __init__(self, fn: Callable[[T], Iterable[Hashable]], is_unique=False):
        self.fn = fn
        self.is_unique = is_unique

    def __call__(self, item: T) -> Iterable[Hashable]:
        return self.fn(item)


class Property(SetProperty):
    def __init__(self, fn: Callable[[T], Hashable], is_unique=False):
        self.fn = fn
        self.is_unique = is_unique

    def __call__(self, item: T) -> Iterable[Hashable]:
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

    properties: dict[str, SetProperty]
    indices: dict[str, defaultdict[Hashable, set[T]]]

    def __init__(self, iterable: Iterable[T] = []):
        self.properties = {}
        self.indices = {}

        super().__init__(iterable)

    def add(self, el: T):
        assert el not in self

        super().add(el)

        for prop_name in self.properties:
            prop = self.properties[prop_name]

            for val in prop(el):
                if prop.is_unique:
                    assert not self.indices[prop_name][val]
                self.indices[prop_name][val].add(el)

    def remove(self, el: T):
        super().remove(el)

        for prop_name in self.properties:
            prop = self.properties[prop_name]

            for val in prop(el):
                self.indices[prop_name][val].remove(el)

                # If the index entry is now empty, delete it
                if not self.indices[prop_name][val]:
                    del self.indices[prop_name][val]

    def lookup(self, name: str, value: Any) -> T | Iterable[T]:
        prop = self.properties[name]
        matches = self.indices[name][value]

        if prop.is_unique:
            assert len(matches) == 1
            return next(iter(matches))
        else:
            return matches

    def create_index(self, name: str, prop: SetProperty):
        """
        Given a function which maps a set member to an `Any`-typed value, create
        a reverse-index mapping a property value to the set of the members of `self`
        with that property. This index is updated when adding new members or removing
        existing ones, but please note that if you mutate the internal state of an
        existing set member, this object will not reflect those updates unless you
        take the care to update the indices manually.

        NOTE: mutating set members outside of interface calls will invalidate indices.
        """
        assert name not in self.properties

        self.properties[name] = prop
        self.indices[name] = defaultdict(set)

        for el in self:
            for val in prop(el):
                if prop.is_unique:
                    assert not self.indices[name][val]
                self.indices[name][val].add(el)
