from lark import ParseTree, Visitor, Token

from kappybara.rule import Rule, KappaRule, KappaRuleUnimolecular, KappaRuleBimolecular
from kappybara.grammar.pattern_builder import AgentBuilder
from kappybara.pattern import Agent, Pattern
from kappybara.site_states import *


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
