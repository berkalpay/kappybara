"""
Add new constructors for the classes in kappybara/pattern.py using method patching.

Method patching is definitely pretty obfuscating, but IMO it's worth it since
the use of these constructors is well compartmentalized: we only need them at
the start for parsing out a model, which has nothing to do with the actual
simulation logic in pattern.py. So patching in those constructors here saves
us from cluttering up pattern.py with all this stuff.
"""

from lark import ParseTree
from kappybara.pattern import Site, Agent, Component, Pattern
from kappybara.grammar import kappa_parser
from kappybara.grammar.pattern_builder import (
    SiteBuilder,
    AgentBuilder,
    PatternBuilder,
)


@classmethod
def site_from_parse_tree(cls, tree: ParseTree) -> Site:
    assert tree.data == "site"

    builder = SiteBuilder(tree)
    return cls(
        label=builder.parsed_site_name,
        internal_state=builder.parsed_internal_state,
        link_state=builder.parsed_link_state,
    )


@classmethod
def agent_from_parse_tree(cls, tree: ParseTree) -> Agent:
    """
    Parse an agent from a Kappa expression, whose `id` defaults to 0.

    Wherever you use this method, you *must* manually reassign
    the id of the created agent to ensure uniqueness in its context.

    TODO: Think about refactoring this to explicitly require an id assignment.
    One way would be to require a `Mixture` as an argument just to be able
    to call this method in the first place, and using the `Mixture`'s nonce
    to determine the id.
    """
    assert tree.data == "agent"
    builder = AgentBuilder(tree)

    agent: Agent = cls(id=0, type=builder.parsed_type, sites=builder.parsed_interface)

    for site in agent.sites.values():
        site.agent = agent

    return agent


@classmethod
def agent_from_kappa(cls, kappa_str: str) -> Agent:
    input_tree = kappa_parser.parse(kappa_str)
    assert input_tree.data == "kappa_input"
    assert len(input_tree.children) == 1

    pattern_tree = input_tree.children[0]
    assert pattern_tree.data == "pattern"
    assert (
        len(pattern_tree.children) == 1
    ), "Zero or more than one agent patterns were specified."

    agent_tree = pattern_tree.children[0]
    return cls.from_parse_tree(agent_tree)


def component_from_kappa(kappa_str: str) -> Component:
    pattern = Pattern.from_kappa(kappa_str)

    assert len(pattern.components) == 1

    return pattern.components[0]


@classmethod
def pattern_from_parse_tree(cls, tree: ParseTree) -> Pattern:
    assert tree.data == "pattern"

    builder = PatternBuilder(tree)

    # Reassign agent id's so they are unique (in the
    # context of this individual Pattern)
    for i in range(len(builder.parsed_agents)):
        builder.parsed_agents[i].id = i

    return cls(agents=builder.parsed_agents)


@classmethod
def pattern_from_kappa(cls, kappa_str: str) -> Pattern:
    input_tree = kappa_parser.parse(kappa_str)
    assert input_tree.data == "kappa_input"
    assert (
        len(input_tree.children) == 1
    ), "Zero or more than one patterns were specified."
    assert len(input_tree.children) == 1

    pattern_tree = input_tree.children[0]
    return cls.from_parse_tree(pattern_tree)


Site.from_parse_tree = site_from_parse_tree
Agent.from_parse_tree = agent_from_parse_tree
Agent.from_kappa = agent_from_kappa
Component.from_kappa = component_from_kappa
Pattern.from_parse_tree = pattern_from_parse_tree
Pattern.from_kappa = pattern_from_kappa


def test_pattern_from_kappa():
    test_kappa = """
        A(a[.]{blah}, b[_]{bleh}, c[#], d[some_site_name.some_agent_name], e[13]),
        B(f[13], e[1], z[3]),
        C(x[1]),
        D(w[3]),
        E()
    """
    pattern = Pattern.from_kappa(test_kappa)

    assert ["A", "B", "C", "D", "E"] == list(
        map(lambda agent: agent.type, pattern.agents)
    )
    assert [0, 1, 2, 3, 4] == list(map(lambda agent: agent.id, pattern.agents))
    assert ["a", "b", "c", "d", "e"] == list(
        map(lambda site: site.label, pattern.agents[0].sites.values())
    )
    assert len(pattern.components) == 2
