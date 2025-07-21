import random
from typing import Any, Optional, Iterable


class OrderedSet[T]:
    def __init__(self, items: Optional[Iterable[T]] = None):
        self.dict = dict() if items is None else dict.fromkeys(items)

    def __iter__(self):
        yield from self.dict

    def __len__(self):
        return len(self.dict)

    def add(self, item: Any) -> None:
        self.dict[item] = None

    def remove(self, item: Any) -> None:
        del self.dict[item]


class Counted:
    counter = 0

    def __init__(self):
        self.id = Counted.counter
        Counted.counter += 1

    def __hash__(self):
        return self.id

    def __eq__(self, other):
        return hash(self) == hash(other)


def rejection_sample(population: Iterable, excluded: Iterable, max_attempts: int = 100):
    population = list(population)
    if not population:
        raise ValueError("Sequence is empty")
    excluded_ids = set(id(x) for x in excluded)

    # Fast rejection sampling (O(1) average case for small exclusion sets)
    for _ in range(max_attempts):
        choice = random.choice(population)
        if id(choice) not in excluded_ids:
            return choice

    # Fallback to O(n) scan only if necessary (rare for small exclusion sets)
    valid_choices = [item for item in population if id(item) not in excluded_ids]
    if not valid_choices:
        raise ValueError("No valid elements to choose from")
    return random.choice(valid_choices)
