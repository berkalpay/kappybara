# TODO: this isn't working like I thought it would
# I want to remove the quotes around types in
# `LinkState` and `LinkStatePattern`
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union

# Specified as '.' in the Kappa language
EmptyState = type(None)


@dataclass
class UndeterminedState:
    """
    When used in a pattern for instantiation, the relevant state should be set
    to a default (empty for link state, some default for internal state).
    When used in a rule or observation pattern, this is the same as a wild card.
    """

    pass


@dataclass
class WildCardPredicate:
    """
    A predicate which will match anything
    Specified as the hash symbol ('#') in the Kappa language
    """

    pass


@dataclass
class BoundPredicate:
    """
    A link state predicate which matches if the site is bound.
    Specified as an underscore ('_') in the Kappa language
    """

    pass


@dataclass
class SiteTypePredicate:
    """
    A link state predicate which matches if the site is bound,
    but only to a specific site type.
    """

    site_name: str
    agent_name: str


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

import pytest


@pytest.mark.parametrize(
    "test_pair",
    [
        (EmptyState(), EmptyState()),
        (UndeterminedState(), UndeterminedState()),
        (WildCardPredicate(), WildCardPredicate()),
        (BoundPredicate(), BoundPredicate()),
        (SiteTypePredicate("a", "A"), SiteTypePredicate("a", "A")),
    ],
)
def test_state_comparison_eq(test_pair):
    a, b = test_pair
    assert a == b
