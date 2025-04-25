"""
Helper objects for building out in-memory representations
of Kappa objects parsed from .ka files
"""

from lark import ParseTree, Tree, Visitor, Token
from typing import List

from kappybara.pattern import Site, Agent, Pattern
from kappybara.site_states import *


@dataclass
class SiteBuilder(Visitor):
    parsed_site_name: str
    parsed_internal_state: "InternalStatePattern"
    parsed_link_state: "LinkStatePattern"

    def __init__(self, tree: ParseTree):
        super().__init__()

        self.parsed_agents: List[Agent] = []

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
                # NOTE: Actually probably ignore the above. According to Walter Kappa models shouldn't require explicitly
                # declared agent signatures in the first place.
                self.parsed_internal_state = str(internal_state)
            case Tree(data="unspecified"):
                self.parsed_internal_state = UndeterminedState()
            case _:
                raise ValueError(
                    f"Unexpected internal state in site parse tree: {tree}"
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
                raise ValueError(f"Unexpected link state in site parse tree: {tree}")

    @property
    def object(self) -> Site:
        return Site(
            label=self.parsed_site_name,
            internal_state=self.parsed_internal_state,
            link_state=self.parsed_link_state,
        )


@dataclass
class AgentBuilder(Visitor):
    parsed_type: str
    parsed_interface: List[Site]

    def __init__(self, tree: ParseTree):
        super().__init__()

        self.parsed_type = None
        self.parsed_interface: List[Site] = []

        assert tree.data == "agent"
        self.visit(tree)

    # Visitor method for Lark
    def agent_name(self, tree: ParseTree):
        self.parsed_type = str(tree.children[0])

    # Visitor method for Lark
    def site(self, tree: ParseTree):
        self.parsed_interface.append(SiteBuilder(tree).object)

    @property
    def object(self) -> Agent:
        """NOTE: `id` defaults to 0 and should be reassigned."""
        agent = Agent(id=0, type=self.parsed_type, sites=self.parsed_interface)
        for site in agent.sites.values():
            site.agent = agent
        return agent


@dataclass
class PatternBuilder(Visitor):
    parsed_agents: List[Agent]

    def __init__(self, tree: ParseTree):
        super().__init__()

        self.parsed_agents: List[Agent] = []

        assert tree.data == "pattern"
        self.visit(tree)

        # The agents get visited in reverse order
        self.parsed_agents.reverse()

    # Visitor method for Lark
    def agent(self, tree: ParseTree):
        self.parsed_agents.append(AgentBuilder(tree).object)

    @property
    def object(self) -> Pattern:
        # Reassign agent id's so they're unique in this Pattern
        for i in range(len(self.parsed_agents)):
            self.parsed_agents[i].id = i
        return Pattern(agents=self.parsed_agents)
