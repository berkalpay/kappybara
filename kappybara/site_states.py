# TODO: this isn't working like I thought it would
# I want to remove the quotes around types in
# `LinkState` and `LinkStatePattern`
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union, NamedTuple

EmptyState = type(None)  # '.' in the Kappa language
UndeterminedState = NamedTuple("UndeterminedState", [])
WildCardPredicate = NamedTuple("WildCardPredicate", [])
BoundPredicate = NamedTuple("BoundPredicate", [])
SiteTypePredicate = NamedTuple(
    "SiteTypePredicate", [("site_name", str), ("agent_name", str)]
)

# TODO: implementing other internal state types should start by extending this to a union type e.g. str | int
InternalState = str
InternalStatePattern = InternalState | WildCardPredicate | UndeterminedState

# This is the same as Optional[Site], just makes what the None type actually means in context a bit clearer
LinkState = Union["Site"] | EmptyState
LinkStatePattern = (
    WildCardPredicate
    | BoundPredicate
    | SiteTypePredicate
    | int
    | EmptyState
    | UndeterminedState
    | Union[
        "Site"
    ]  # Hack to make this a forward ref to avoid cyclic dependencies, same as Site in LinkState. TODO something better
)

# NOTE: This pattern (lru_cache) might help with memory overhead in the future
# class NameState(str):
#     @lru_cache(maxsize=1024)
#     def __new__(cls, value):
#         return super().__new__(cls, value)
