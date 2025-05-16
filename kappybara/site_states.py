from typing import Union, NamedTuple


class Empty(NamedTuple):
    def __str__(self):
        return "."


class Undetermined(NamedTuple):
    """Default in pattern instantiation and a wildcard in rules and observations."""

    def __str__(self):
        return "?"


class Wildcard(NamedTuple):
    def __str__(self):
        return "#"


class Bound(NamedTuple):
    def __str__(self):
        return "_"


class SiteType(NamedTuple):
    """Specifies the site is bound to a specific type of site."""

    site_name: str
    agent_name: str


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
    | Union["Site"]  # TODO: something better for cyclic dependencies
)
