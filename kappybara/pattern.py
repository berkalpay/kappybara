from dataclasses import dataclass
from typing import Self, List

from kappybara.grammar import kappa_parser
from kappybara.site_states import *
from lark import ParseTree, Visitor, Tree, Token


@dataclass
class SitePattern:
    label: str
    internal_state: InternalStatePattern
    link_state: LinkStatePattern

    @classmethod
    def from_parse_tree(cls, tree: ParseTree) -> Self:
        print(tree.pretty())
        print(tree)
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

    def __init__(self, type: str, sites: List[SitePattern]):
        self.type = type
        self.sites = sites

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
class SitePatternBuilder(Visitor):
    parsed_site_name: str
    parsed_internal_state: InternalStatePattern = None
    parsed_link_state: LinkStatePattern = None

    def __init__(self, tree: ParseTree):
        super().__init__()

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


def test_agent_pattern_from_kappa():
    a = AgentPattern.from_kappa(
        "A(b[.]{blah}, hi[_]{bleh}, c[#], d[some_site_name.some_agent_name], e[13])"
    )
