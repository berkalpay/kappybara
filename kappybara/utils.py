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


chemical_constants = {
    "avogadro": 6.02214e23,
    "diffusion_rate": 1e9,
    "kds": {"weak": 1e-6, "moderate": 1e-7, "strong": 1e-8},
    "volumes": {"fibro": 2.25e-12, "yeast": 4.2e-14},
    "room_temperature": 273.15 + 25,
}
