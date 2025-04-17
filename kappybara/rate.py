from dataclasses import dataclass
from typing import Callable

from kappybara.pattern import AgentPattern
from kappybara.mixture import Mixture


RateFunction = Callable[Mixture, float]

Rate = RateFunction | float

"""
Some old stuff below, might want to come back to this stuff later
"""
# @dataclass
# class DefaultPredicate:
#     pass


# @dataclass
# class UnimolecularPredicate:
#     pass


# @dataclass
# class BimolecularPredicate:
#     pass


# @dataclass
# class HorizonPredicate:
#     pass


# CustomPredicate = Callable[list[AgentPattern], bool]

# RatePredicate = (
#     DefaultPredicate | UnimolecularPredicate | BimolecularPredicate | CustomPredicate
# )

# @dataclass
# class Rate:
#     predicate: RatePredicate
#     value: RateValue
