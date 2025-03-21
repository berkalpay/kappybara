from dataclasses import dataclass
from typing import Optional

from kappybara.physics import Site

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

LinkState = Site | EmptyState
LinkStatePattern = (
    WildCardPredicate
    | BoundPredicate
    | SiteTypePredicate
    | int
    | EmptyState
    | UndeterminedState
)

# NOTE: This pattern (lru_cache) might help with memory overhead in the future
# class NameState(str):
#     @lru_cache(maxsize=1024)
#     def __new__(cls, value):
#         return super().__new__(cls, value)
