from dataclasses import dataclass
from typing import Self

from kappybara.grammar import kappa_parser
from lark import ParseTree, Visitor

@dataclass
class SitePattern:
    label: str
    internal_state: str
    link_state: str

    @classmethod
    def from_parse_tree(cls, tree: ParseTree) -> Self:
        print(tree)
        assert tree.data == "site"

        builder = SitePatternBuilder(tree)
        return cls(builder.parsed_site_name,
                   builder.parsed_internal_state,
                   builder.parsed_link_state)

class AgentPattern:
    def __init__(self, type: str, sites: tuple["Site"]):
        self.type = type
        self.interface: tuple[Site] = sites

    @classmethod
    def from_parse_tree(cls, tree: ParseTree) -> Self:
        assert tree.data == "agent"
        builder = AgentPatternBuilder(tree)

        return cls(builder.parsed_type, builder.parsed_sites)

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

class AgentPatternBuilder(Visitor):
    def __init__(self, tree: ParseTree):
        super().__init__()

        self.parsed_type = None
        self.parsed_sites = ()

        assert tree.data == "agent"
        self.visit(tree)

    def agent_name(self, tree: ParseTree):
        self.parsed_type = str(tree.children[0])

    def site(self, tree: ParseTree):
        print("working?")
        self.parsed_sites = self.parsed_sites + (SitePattern.from_parse_tree(tree),)
        # self.parsed_sites = self.parsed_sites + ("placeholder",)

@dataclass
class SitePatternBuilder(Visitor):
    parsed_site_name: str
    parsed_link_state = None
    parsed_internal_state = None
    def __init__(self, tree: ParseTree):
        super().__init__()

        assert tree.data == "site"
        self.visit(tree)

    def site_name(self, tree: ParseTree):
        self.parsed_site_name = str(tree.children[0])

    def link_state(self, tree: ParseTree):
        self.parsed_link_state = str(tree.children[0])

    def internal_state(self, tree: ParseTree):
        self.parsed_internal_state = str(tree.children[0])

def test_agent_pattern_from_kappa():
    a = AgentPattern.from_kappa(
        "A(b[.]{blah}, hi[_]{bleh}, c[#], d[some_site_name.some_agent_name], e[13])"
    )
