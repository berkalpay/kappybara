from typing import Self
from dataclasses import dataclass

from kappybara.pattern import SitePattern


def cantor(x: int, y: int) -> int:
    """
    https://en.wikipedia.org/wiki/Pairing_function#Cantor_pairing_function

    TODO: this has some failure cases due to integer overflow.
    """
    return ((x + y) * (x + y + 1)) // 2 + y


@dataclass
class Edge:
    """
    Basically, we want a data structure to represent bonds that we can use as keys
    to a set/dict (i.e. hashset/hashmap). The key property we need is that its hash
    representation should be unordered: Edge(site1=x, site2=y) represents the same
    thing as Edge(site1=y, site2=x), so they should function as the same key.
    """

    site1: SitePattern
    site2: SitePattern

    def __eq__(self, other: Self):
        return (self.site1 == other.site1 and self.site2 == other.site2) or (
            self.site1 == other.site2 and self.site2 == other.site1
        )

    def __hash__(self):
        """
        TODO: Right now XOR is being used to symmetrically combine hashes of the two sites
        so that we get an unordered hash. This is unsound however: https://stackoverflow.com/a/27952689
        """
        return cantor(hash(self.site1), hash(self.site1.agent)) ^ cantor(
            hash(self.site2), hash(self.site2.agent)
        )


# def test_cantor():
#     test_case = (1, 2)
#     x, y = test_case

#     assert cantor(x, y) == cantor(y, x)
