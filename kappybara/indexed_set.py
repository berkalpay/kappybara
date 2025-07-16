from dataclasses import dataclass, field
from collections import defaultdict
from collections.abc import Callable, Hashable
from typing import Optional, Iterable, Generic, TypeVar, Any, Self

T = TypeVar("T")  # Member type of `IndexedSet`


class SetProperty:
    """
    This class should be initialized with a function or lambda which
    takes a set member as input, and returns a collection or iterable of
    values associated with that member that you want to index by.

    Example initialization:
    ```
    @dataclass
    class SportsTeam:
        name: str
        members: list[str]

    def get_members(team: SportsTeam):
        return team.members

    members = SetProperty(get_members, is_unique=False) # If someone can belong to multiple teams (default)
    members_unique = SetProperty(get_members, is_unique=True) # If someone can belong to only one team

    members_alt = SetProperty(lambda team: team.members) # Equivalent to `members`
    ```
    """

    def __init__(self, fn: Callable[[T], Iterable[Hashable]], is_unique=False):
        self.fn = fn
        self.is_unique = is_unique

    def __call__(self, item: T) -> Iterable[Hashable]:
        return self.fn(item)


class Property(SetProperty):
    """
    This class should be initialized with a function or lambda which
    takes a set member as input, and returns a single object which is
    the corresponding property value of a set member.

    Two alternative examples for initializing a `Property`
    ```
    @dataclass
    class Fruit:
        color: str

    def get_color(f: Fruit):
        return f.color

    my_property = Property(get_color)

    my_property_alt = Property(lambda fruit: fruit.color) # Equivalent using a lambda function
    ```
    """

    def __init__(self, fn: Callable[[T], Hashable], is_unique=False):
        self.fn = fn
        self.is_unique = is_unique

    def __call__(self, item: T) -> Iterable[Hashable]:
        return [self.fn(item)]


class IndexedSet(set[T], Generic[T]):
    """
    A subclass of the built-in `set`, with support for indexing
    by arbitrary properties of set members, as well as integer
    indexing to allow for random sampling.

    Credit https://stackoverflow.com/a/15993515 for the integer indexing logic.

    If you know for some property that you should only get a single
    set member back when using `lookup`, mark that property as unique
    when you create it.

    NOTE: although this class is indexable due to the implementation
    of `__getitem__`, member ordering is not stable across insertions
    and deletions.

    Example usage:
    ```
    @dataclass
    class SportsTeam:
        name: str
        jersey_color: str
        members: list[str]

    def get_members(team: SportsTeam):
        return team.members

    members = SetProperty(get_members, is_unique=False) # If someone can belong to multiple teams (default)
    members_unique = SetProperty(get_members, is_unique=True) # If someone can belong to only one team

    teams: IndexedSet[SportsTeam] = IndexedSet()
    teams.create_index("name", Property(lambda team: team.name, is_unique=True))
    teams.create_index("members", members_prop)
    teams.create_index("color", Property(lambda team: team.jersey_color))

    [...] # populate the set with teams

    teams.lookup("members", "Alice") # Returns all `SportsTeam`s that Alice belongs to
    teams.lookup("color", "blue")    # Returns all teams with blue jerseys
    teams.lookup("name", "Manchester") # Returns the team whose name is "Manchester"
    ```
    """

    properties: dict[str, SetProperty]
    indices: dict[str, defaultdict[Hashable, Self]]

    _item_to_pos: dict[T, int]
    _item_list: list[T]

    def __init__(self, iterable: Iterable[T] = []):
        iterable = list(iterable)

        super().__init__(iterable)

        self._item_list = iterable
        self._item_to_pos = {item: i for (i, item) in enumerate(iterable)}

        self.properties = {}
        self.indices = {}

    def add(self, item: T):
        assert item not in self
        super().add(item)

        # Update integer index
        self._item_list.append(item)
        self._item_to_pos[item] = len(self._item_list) - 1

        # Update property indices
        for prop_name in self.properties:
            prop = self.properties[prop_name]

            for val in prop(item):
                if prop.is_unique:
                    assert not self.indices[prop_name][val]
                self.indices[prop_name][val].add(item)

    def remove(self, item: T):
        assert item in self
        super().remove(item)

        # Update integer index
        pos = self._item_to_pos.pop(item)
        last_item = self._item_list.pop()
        if pos != len(self._item_list):
            self._item_list[pos] = last_item
            self._item_to_pos[last_item] = pos

        # Update property indices
        for prop_name in self.properties:
            prop = self.properties[prop_name]

            for val in prop(item):
                self.indices[prop_name][val].remove(item)

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

        NOTE: mutating set members outside of interface calls can invalidate indices.
        """
        assert name not in self.properties

        self.properties[name] = prop
        self.indices[name] = defaultdict(IndexedSet)

        for el in self:
            for val in prop(el):
                if prop.is_unique:
                    assert not self.indices[name][val]
                self.indices[name][val].add(el)

    def __getitem__(self, i):
        assert 0 <= i < len(self)
        return self._item_list[i]
