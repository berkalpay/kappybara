from pathlib import Path
from lark import Lark, ParseTree, Tree, Visitor, Token
from typing import List

from kappybara.site_states import *
from kappybara.pattern import Site, Agent, Pattern
from kappybara.rule import Rule, KappaRule, KappaRuleUnimolecular, KappaRuleBimolecular


class KappaParser:
    """Don't instantiate: use `kappa_parser`"""

    def __init__(self) -> None:
        self._parser = Lark.open(
            str(Path(__file__).parent / "kappa.lark"),
            rel_to=__file__,
            parser="earley",
            # The basic lexer isn't required and isn't usually recommended
            lexer="dynamic",
            start="kappa_input",
            # Disabling these slightly improves speed
            propagate_positions=False,
            maybe_placeholders=False,
        )

    def parse(self, text: str) -> ParseTree:
        return self._parser.parse(text)

    def parse_file(self, filepath: str) -> ParseTree:
        with open(filepath, "r") as file:
            return self._parser.parse(file.read())


kappa_parser = KappaParser()


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


@dataclass
class RuleBuilder(Visitor):
    parsed_label: Optional[str]
    left_agents: list[Optional[Agent]]
    right_agents: list[Optional[Agent]]
    parsed_rates: list[float]
    tree_data: str

    def __init__(self, tree: ParseTree):
        super().__init__()

        self.parsed_label = None
        self.left_agents = []
        self.right_agents = []
        self.parsed_rates = []

        assert tree.data in ["f_rule", "fr_rule", "ambi_rule", "ambi_fr_rule"]
        self.tree_data = tree.data

        self.visit(tree)

    # Visitor method for Lark
    def rate(self, tree: ParseTree) -> None:
        assert tree.data == "rate"

        alg_exp = tree.children[0]
        assert alg_exp.data == "algebraic_expression"
        if (
            len(alg_exp.children) > 1
            or not isinstance(alg_exp.children[0], Token)
            or alg_exp.children[0].type != "SIGNED_FLOAT"
        ):
            raise NotImplementedError("Generic algebraic expressions not implemented.")
        else:
            self.parsed_rates.append(float(alg_exp.children[0]))

    # Visitor method for Lark
    def rule_expression(self, tree: ParseTree) -> None:
        assert tree.data in ["rule_expression", "rev_rule_expression"]
        mid_idx = next(
            (i for i, child in enumerate(tree.children) if child in ["->", "<->"])
        )  # Locate the arrow in the expression

        for i, child in enumerate(tree.children):
            if i == mid_idx:
                continue

            if child == ".":
                agent = None
            elif child.data == "agent":
                agent = AgentBuilder(child).object

            if i < mid_idx:
                self.left_agents.append(agent)
            else:
                self.right_agents.append(agent)

    # Visitor method for Lark
    def rev_rule_expression(self, tree: ParseTree) -> None:
        self.rule_expression(tree)

    @property
    def objects(self) -> list[Rule]:
        rules = []
        left = Pattern(self.left_agents)
        right = Pattern(self.right_agents)
        rates = self.parsed_rates

        match self.tree_data:
            case "f_rule":
                assert len(rates) == 1
                rules.append(KappaRule(left, right, rates[0]))
            case "fr_rule":
                assert len(rates) == 2
                rules.append(KappaRule(left, right, rates[0]))
                rules.append(KappaRule(right, left, rates[1]))
            case "ambi_rule":
                # TODO: check that the order of the rates is right
                assert len(rates) == 2
                if rates[0] != 0:
                    rules.append(KappaRuleBimolecular(left, right, rates[0]))
                if rates[1] != 0:
                    rules.append(KappaRuleUnimolecular(left, right, rates[1]))
            case "ambi_fr_rule":
                assert len(rates) == 3
                if rates[0] != 0:
                    rules.append(KappaRuleBimolecular(left, right, rates[0]))
                if rates[1] != 0:
                    rules.append(KappaRuleUnimolecular(left, right, rates[1]))
                rules.append(KappaRule(right, left, rates[2]))

        return [r for r in rules if r is not None]
