# TODO: this isn't working like I thought it would
# I want to remove the quotes around types in
# `LinkState` and `LinkStatePattern`
from __future__ import annotations
from typing import Union, NamedTuple

Empty = type(None)  # '.' in Kappa

# Default state in pattern instantiation. Same as a wildcard in rules and observations.
Undetermined = NamedTuple("Undetermined", [])

# Matches anything ('#' in Kappa)
Wildcard = NamedTuple("Wildcard", [])

# Matches if the sites is bound ('_' in Kappa)
Bound = NamedTuple("Bound", [])

# Matches if the site is bound to a specific type of site
SiteType = NamedTuple("SiteType", [("site_name", str), ("agent_name", str)])

# TODO: implementing other internal state types should start by extending this to a union type e.g. str | int
Internal = str
InternalPattern = Internal | Wildcard | Undetermined

# This is the same as Optional[Site], just makes what the None type actually means in context a bit clearer
Link = Union["Site"] | Empty
LinkPattern = (
    Wildcard
    | Bound
    | SiteType
    | int
    | Empty
    | Undetermined
    | Union[
        "Site"
    ]  # Hack to make this a forward ref to avoid cyclic dependencies, same as Site in LinkState. TODO something better
)

# NOTE: This pattern (lru_cache) might help with memory overhead in the future
# class NameState(str):
#     @lru_cache(maxsize=1024)
#     def __new__(cls, value):
#         return super().__new__(cls, value)
