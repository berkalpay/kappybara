from dataclasses import dataclass
from functools import cached_property
from typing import Self, List

from kappybara.grammar import kappa_parser
from kappybara.site_states import *
from kappybara.physics import Site, Agent
from lark import ParseTree, Visitor, Tree, Token


@dataclass
class SitePattern:
    label: str
    internal_state: "InternalStatePattern"
    link_state: "LinkStatePattern"

    def create_instance(self) -> Site:
        assert (
            not self.underspecified
        ), "Site pattern is not specific enough to be instantiated"

        raise NotImplementedError

    @cached_property
    def underspecified(self) -> bool:
        """
        Tells you whether or not concrete `Site` instances can be created
        from this pattern, i.e. whether there are ambiguous site states
        """
        match (internal_state, link_state):
            case (
                (WildCardPredicate(), _)
                | (_, WildCardPredicate())
                | (_, BoundPredicate())
                | (_, SiteTypePredicate())
            ):
                return True
            case _:
                return False

    @classmethod
    def from_parse_tree(cls, tree: ParseTree) -> Self:
        assert tree.data == "site"

        builder = SitePatternBuilder(tree)
        return cls(
            builder.parsed_site_name,
            builder.parsed_internal_state,
            builder.parsed_link_state,
        )


@dataclass
class AgentPattern:
    type: str
    sites: List[SitePattern]

    def create_instance(self) -> Site:
        assert (
            not self.underspecified
        ), "Agent pattern is not specific enough to be instantiated"

        raise NotImplementedError

    @cached_property
    def underspecified(self) -> bool:
        """
        Tells you whether or not concrete `Agent` instances can be created
        from this pattern, i.e. whether there are any underspecified sites
        """
        return all(site.underspecified for site in self.sites)

    @classmethod
    def from_parse_tree(cls, tree: ParseTree) -> Self:
        assert tree.data == "agent"
        builder = AgentPatternBuilder(tree)

        return cls(builder.parsed_type, builder.parsed_interface)

    @classmethod
    def from_kappa(cls, kappa_str: str) -> Self:
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


@dataclass
class MoleculePattern:
    """
    A set of agents that are all in the same connected component (this is
    not guaranteed statically), you have to make sure it's enforced when you create it.

    NOTE: I'm including this class as a demonstration that stylistically
    follows the ideas in physics.py, but I'm pretty hesitant about committing
    to this pattern unless it's strictly just a dataclass without implemented
    methods for pattern matching/isomorphism; one concrete consideration is
    w.r.t. rectangular approximation and the necessary computations for
    observable patterns. Will try to elaborate later.
    """

    pass


@dataclass
class Pattern:
    agents: List[AgentPattern]

    def create_instance(self) -> Site:
        assert (
            not self.underspecified
        ), "Pattern is not specific enough to be instantiated"

        raise NotImplementedError

    @cached_property
    def underspecified(self) -> bool:
        return all(agent.underspecified for agent in self.agents)

    @classmethod
    def from_parse_tree(cls, tree: ParseTree) -> Self:
        assert tree.data == "pattern"

        builder = PatternBuilder(tree)
        return cls(
            builder.parsed_agents[::-1]
        )  # The agents get parsed in reverse order

    @classmethod
    def from_kappa(cls, kappa_str: str) -> Self:
        input_tree = kappa_parser.parse(kappa_str)
        assert input_tree.data == "kappa_input"
        assert (
            len(input_tree.children) == 1
        ), "Zero or more than one patterns were specified."
        assert len(input_tree.children) == 1

        pattern_tree = input_tree.children[0]
        return cls.from_parse_tree(pattern_tree)


@dataclass
class SitePatternBuilder(Visitor):
    parsed_site_name: str
    parsed_internal_state: "InternalStatePattern"
    parsed_link_state: "LinkStatePattern"

    def __init__(self, tree: ParseTree):
        super().__init__()

        self.parsed_agents: List[AgentPattern] = []

        assert tree.data == "site"
        self.visit(tree)

    # Visitor method for Lark
    def site_name(self, tree: ParseTree):
        self.parsed_site_name = str(tree.children[0])

    # Visitor method for Lark
    def internal_state(self, tree: ParseTree):
        match tree.children[0]:
            case "#":
                self.parsed_internal_state = WildCardPredicate()
            case str(internal_state):
                # TODO: check if this is a legal option as specified by the agent signature
                # this object would need to hold the agent type this site is being built for and do some checks against that
                self.parsed_internal_state = str(internal_state)
            case Tree(data="unspecified"):
                self.parsed_internal_state = UndeterminedState()
            case _:
                raise ValueError(
                    f"Unexpected internal state in Lark's parse tree: {tree}"
                )

    # Visitor method for Lark
    def link_state(self, tree: ParseTree):
        match tree.children:
            case ["#"]:
                self.parsed_link_state = WildCardPredicate()
            case ["_"]:
                self.parsed_link_state = BoundPredicate()
            case ["."]:
                self.parsed_link_state = EmptyState()
            case [Token("INT", x)]:
                self.parsed_link_state = int(x)
            case [
                Tree(data="site_name", children=[site_name]),
                Tree(data="agent_name", children=[agent_name]),
            ]:
                self.parsed_link_state = SiteTypePredicate(
                    str(site_name), str(agent_name)
                )
            case [Tree(data="unspecified")]:
                self.parsed_link_state = UndeterminedState()
            case _:
                raise ValueError(f"Unexpected link state in Lark's parse tree: {tree}")


@dataclass
class AgentPatternBuilder(Visitor):
    parsed_type: str
    parsed_interface: List[SitePattern]

    def __init__(self, tree: ParseTree):
        super().__init__()

        self.parsed_type = None
        self.parsed_interface: List[SitePattern] = []

        assert tree.data == "agent"
        self.visit(tree)

    # Visitor method for Lark
    def agent_name(self, tree: ParseTree):
        self.parsed_type = str(tree.children[0])

    # Visitor method for Lark
    def site(self, tree: ParseTree):
        self.parsed_interface.append(SitePattern.from_parse_tree(tree))


@dataclass
class PatternBuilder(Visitor):
    parsed_agents: List[AgentPattern]

    def __init__(self, tree: ParseTree):
        super().__init__()

        self.parsed_agents: List[SitePattern] = []

        assert tree.data == "pattern"
        self.visit(tree)

    # Visitor method for Lark
    def agent(self, tree: ParseTree):
        self.parsed_agents.append(AgentPattern.from_parse_tree(tree))


def test_pattern_from_kappa():
    test_kappa = """
        A(a[.]{blah}, b[_]{bleh}, c[#], d[some_site_name.some_agent_name], e[13]),
        B(),
        C(),
        D()
    """
    pattern = Pattern.from_kappa(test_kappa)

    assert ["A", "B", "C", "D"] == list(map(lambda agent: agent.type, pattern.agents))
    assert ["a", "b", "c", "d", "e"] == list(
        map(lambda site: site.label, pattern.agents[0].sites)
    )
