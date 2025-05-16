from typing import Union, NamedTuple

# . empty
# # wildcard
# _ bound
# ? default in pattern instantiation and a wildcard in rules and observations.


class SiteType(NamedTuple):
    """Specifies the site is bound to a specific type of site."""

    site_name: str
    agent_name: str


# This is the same as Optional[Site], just makes what the None type actually means in context a bit clearer
Link = Union["Site"] | str
LinkPattern = str | SiteType | int | Union["Site"]
