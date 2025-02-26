from typing import Any, Optional, Iterable


class OrderedSet:
    def __init__(self, items: Optional[Iterable] = None):
        self.dict = dict() if items is None else dict.fromkeys(items)

    def __iter__(self):
        yield from self.dict

    def __len__(self):
        return len(self.dict)

    def add(self, item: Any) -> None:
        self.dict[item] = None

    def remove(self, item: Any) -> None:
        del self.dict[item]
