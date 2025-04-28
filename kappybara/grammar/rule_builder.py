from lark import ParseTree, Tree, Visitor, Token
from typing import List

from kappybara.rule import Rule, KappaRule, KappaRuleUnimolecular, KappaRuleBimolecular
from kappybara.grammar import kappa_parser
from kappybara.grammar.pattern_builder import AgentBuilder
from kappybara.pattern import Agent, Pattern
from kappybara.site_states import *


def rule_from_kappa(kappa_str: str) -> Rule:
    rules = rules_from_kappa(kappa_str)

    assert len(rules) == 1, "The given rule expression represents more than one rule."
    return rules[0]


def rules_from_kappa(kappa_str: str) -> list[Rule]:
    """
    Forward-reverse rules (with a "<->") really represent two separate rules,
    which is why this doesn't quite work as a class method for `Rule`.
    """
    input_tree = kappa_parser.parse(kappa_str)
    assert input_tree.data == "kappa_input"

    rule_tree = input_tree.children[0]
    return RuleBuilder(rule_tree).objects


@dataclass
class RuleBuilder(Visitor):
    parsed_label: Optional[str]
    left_agents: List[Optional[Agent]]
    right_agents: List[Optional[Agent]]
    parsed_rates: List[float]
    tree_data: str

    def __init__(self, tree: ParseTree):
        super().__init__()

        self.parsed_label = None
        self.left_agents: List[Agent] = []
        self.right_agents: List[Agent] = []
        self.parsed_rates = []

        assert tree.data in ["f_rule", "fr_rule", "ambi_rule", "ambi_fr_rule"]
        self.tree_data = tree.data
        self.visit(tree)

    # Visitor method for Lark
    def rate(self, tree: ParseTree):
        assert tree.data == "rate"

        alg_exp = tree.children[0]
        assert alg_exp.data == "algebraic_expression"

        if (
            len(alg_exp.children) > 1
            or not isinstance(alg_exp.children[0], Token)
            or alg_exp.children[0].type != "SIGNED_FLOAT"
        ):
            raise NotImplementedError(
                "Generic algebraic expressions not implemented yet. We'll need a full system for parsing/evaluating such expressions."
            )
        else:
            rate = float(alg_exp.children[0])
            self.parsed_rates.append(rate)

    # Visitor method for Lark
    def rule_expression(self, tree: ParseTree):
        assert tree.data in ["rule_expression", "rev_rule_expression"]
        # Find the location of the arrow in the expression
        mid_idx = next(
            (i for i, child in enumerate(tree.children) if child in ["->", "<->"])
        )

        for i, child in enumerate(tree.children):
            if i == mid_idx:
                continue

            if child == ".":
                agent = None
            elif child.data == "agent":
                agent: Optional[Agent] = AgentBuilder(child).object

            if i < mid_idx:
                self.left_agents.append(agent)
            else:
                self.right_agents.append(agent)

    # Visitor method for Lark
    def rev_rule_expression(self, tree: ParseTree):
        self.rule_expression(tree)

    @property
    def objects(self) -> list[Rule]:
        rules = []
        left: Pattern = Pattern(self.left_agents)
        right: Pattern = Pattern(self.right_agents)
        rates: List[float] = self.parsed_rates

        match self.tree_data:
            case "f_rule":
                assert len(rates) == 1
                rule = KappaRule(left, right, rates[0])
                rules.append(rule)
            case "fr_rule":
                assert len(rates) == 2
                rule_f = KappaRule(left, right, rates[0])
                rule_r = KappaRule(right, left, rates[1])
                rules.extend([rule_f, rule_r])
            case "ambi_rule":
                # TODO: check that the order of the rates is right
                assert len(rates) == 2
                if rates[0] != 0:
                    rule_bi = KappaRuleBimolecular(left, right, rates[0])
                    rules.append(rule_bi)
                if rates[1] != 0:
                    rule_uni = KappaRuleUnimolecular(left, right, rates[1])
                    rules.append(rule_uni)
            case "ambi_fr_rule":
                assert len(rates) == 3
                if rates[0] != 0:
                    rule_bi = KappaRuleBimolecular(left, right, rates[0])
                    rules.append(rule_bi)
                if rates[1] != 0:
                    rule_uni = KappaRuleUnimolecular(left, right, rates[1])
                    rules.append(rule_uni)
                rule_r = KappaRule(right, left, rates[2])
                rules.append(rule_r)

        return [r for r in rules if r is not None]
