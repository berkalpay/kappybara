from kappybara.pattern import Agent, Component, Pattern
from kappybara.grammar import kappa_parser
from kappybara.grammar.pattern_builder import AgentBuilder, PatternBuilder


def agent(kappa_str: str) -> Agent:
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


def component(kappa_str: str) -> Component:
    parsed_pattern = pattern(kappa_str)
    assert len(parsed_pattern.components) == 1
    return parsed_pattern.components[0]


def pattern(kappa_str: str) -> Pattern:
    input_tree = kappa_parser.parse(kappa_str)
    assert input_tree.data == "kappa_input"
    assert (
        len(input_tree.children) == 1
    ), "Zero or more than one patterns were specified."
    assert len(input_tree.children) == 1

    pattern_tree = input_tree.children[0]
    return PatternBuilder(pattern_tree).object
