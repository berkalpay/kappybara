"""
Add new constructors for the classes in kappybara/pattern.py using method patching.

Method patching is definitely pretty obfuscating, but IMO it's worth it since
the use of these constructors is well compartmentalized: we only need them at
the start for parsing out a model, which has nothing to do with the actual
simulation logic in pattern.py. So patching in those constructors here saves
us from cluttering up pattern.py with all this stuff.
"""

from kappybara.pattern import Agent, Component, Pattern
from kappybara.grammar import kappa_parser
from kappybara.grammar.pattern_builder import AgentBuilder, PatternBuilder


@classmethod
def agent_from_kappa(cls, kappa_str: str) -> Agent:
    # Check pattern describes only a single agent
    input_tree = kappa_parser.parse(kappa_str)
    assert input_tree.data == "kappa_input"
    assert len(input_tree.children) == 1
    pattern_tree = input_tree.children[0]
    assert pattern_tree.data == "pattern"
    assert (
        len(pattern_tree.children) == 1
    ), "Zero or more than one agent patterns were specified."

    agent_tree = pattern_tree.children[0]
    return AgentBuilder(agent_tree).object


def component_from_kappa(kappa_str: str) -> Component:
    pattern = Pattern.from_kappa(kappa_str)
    assert len(pattern.components) == 1
    return pattern.components[0]


@classmethod
def pattern_from_kappa(cls, kappa_str: str) -> Pattern:
    input_tree = kappa_parser.parse(kappa_str)
    assert input_tree.data == "kappa_input"
    assert (
        len(input_tree.children) == 1
    ), "Zero or more than one patterns were specified."
    assert len(input_tree.children) == 1

    pattern_tree = input_tree.children[0]
    return PatternBuilder(pattern_tree).object


Agent.from_kappa = agent_from_kappa
Component.from_kappa = component_from_kappa
Pattern.from_kappa = pattern_from_kappa
