from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from lark import Lark, ParseTree, Tree, Visitor, Token, Transformer_NonRecursive

from kappybara.pattern import Site, Agent, Pattern, SiteType, Partner
from kappybara.rule import Rule, KappaRule, KappaRuleUnimolecular, KappaRuleBimolecular
from kappybara.alg_exp import AlgExp


class KappaParser:
    """Don't instantiate: use `kappa_parser`"""

    def __init__(self):
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
    parsed_state: str
    parsed_partner: Partner

    def __init__(self, tree: ParseTree):
        super().__init__()

        self.parsed_agents: list[Agent] = []

        assert tree.data == "site"
        self.visit(tree)

    # Visitor method for Lark
    def site_name(self, tree: ParseTree) -> None:
        self.parsed_site_name = str(tree.children[0])

    # Visitor method for Lark
    def state(self, tree: ParseTree) -> None:
        match tree.children[0]:
            case "#":
                self.parsed_state = "#"
            case str(state):
                # TODO: check if this is a legal option as specified by the agent signature
                # this object would need to hold the agent type this site is being built for and do some checks against that
                # NOTE: Actually probably ignore the above. According to Walter Kappa models shouldn't require explicitly
                # declared agent signatures in the first place.
                self.parsed_state = str(state)
            case Tree(data="unspecified"):
                self.parsed_state = "?"
            case _:
                raise ValueError(
                    f"Unexpected internal state in site parse tree: {tree}"
                )

    # Visitor method for Lark
    def partner(self, tree: ParseTree) -> None:
        match tree.children:
            case ["#"]:
                self.parsed_partner = "#"
            case ["_"]:
                self.parsed_partner = "_"
            case ["."]:
                self.parsed_partner = "."
            case [Token("INT", x)]:
                self.parsed_partner = int(x)
            case [
                Tree(data="site_name", children=[site_name]),
                Tree(data="agent_name", children=[agent_name]),
            ]:
                self.parsed_partner = SiteType(str(site_name), str(agent_name))
            case [Tree(data="unspecified")]:
                self.parsed_partner = "?"
            case _:
                raise ValueError(f"Unexpected link state in site parse tree: {tree}")

    @property
    def object(self) -> Site:
        return Site(
            label=self.parsed_site_name,
            state=self.parsed_state,
            partner=self.parsed_partner,
        )


@dataclass
class AgentBuilder(Visitor):
    parsed_type: str
    parsed_interface: list[Site]

    def __init__(self, tree: ParseTree):
        super().__init__()

        self.parsed_type = None
        self.parsed_interface: list[Site] = []

        assert tree.data == "agent"
        self.visit(tree)

    # Visitor method for Lark
    def agent_name(self, tree: ParseTree) -> None:
        self.parsed_type = str(tree.children[0])

    # Visitor method for Lark
    def site(self, tree: ParseTree) -> None:
        self.parsed_interface.append(SiteBuilder(tree).object)

    @property
    def object(self) -> Agent:
        agent = Agent(type=self.parsed_type, sites=self.parsed_interface)
        for site in agent:
            site.agent = agent
        return agent


@dataclass
class PatternBuilder(Visitor):
    parsed_agents: list[Agent]

    def __init__(self, tree: ParseTree):
        super().__init__()

        self.parsed_agents: list[Agent] = []

        assert tree.data == "pattern"
        self.visit(tree)

    # Visitor method for Lark
    def agent(self, tree: ParseTree) -> None:
        self.parsed_agents.append(AgentBuilder(tree).object)

    @property
    def object(self) -> Pattern:
        return Pattern(agents=self.parsed_agents)


@dataclass
class RuleBuilder(Visitor):
    parsed_label: Optional[str]
    left_agents: list[Optional[Agent]]
    right_agents: list[Optional[Agent]]
    parsed_rates: list[AlgExp]
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

        rate = parse_tree_to_alg_exp(alg_exp)
        self.parsed_rates.append(rate)

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
                if rates[0].evaluate() != 0:
                    rules.append(KappaRuleBimolecular(left, right, rates[0]))
                if rates[1].evaluate() != 0:
                    rules.append(KappaRuleUnimolecular(left, right, rates[1]))
            case "ambi_fr_rule":
                assert len(rates) == 3
                if rates[0].evaluate() != 0:
                    rules.append(KappaRuleBimolecular(left, right, rates[0]))
                if rates[1].evaluate() != 0:
                    rules.append(KappaRuleUnimolecular(left, right, rates[1]))
                rules.append(KappaRule(right, left, rates[2]))

        return [r for r in rules if r is not None]


class LarkTreetoAlgExp(Transformer_NonRecursive):
    """
    Transforms a Lark ParseTree (rooted at 'algebraic_expression') into an AlgExp.

    NOTE: We use a `Transformer` to parse algebraic expressions, as opposed to `Visitor`
    as with most other Lark objects, because we want to preserve the tree structure of
    the original `ParseTree`, and this is the most convenient way to do so.

    TODO: This doesn't need to use `Transformer_NonRecursive` anymore; I made some changes
    to the Lark grammar that make it easier to parse. If we switch back to using regular
    `Transformer` we can clean up all the methods below to avoid having to explicitly call
    `transform` on all the children.
    """

    def algebraic_expression(self, children):
        children = [self.transform(c) for c in children]
        assert len(children) == 1
        return children[0]

    # --- Literals ---
    def SIGNED_FLOAT(self, token):
        return AlgExp("literal", value=float(token.value))

    def SIGNED_INT(self, token):
        return AlgExp("literal", value=int(token.value))

    # --- Variables/Constants ---
    def declared_variable_name(self, children):
        child = self.transform(children[0])
        return AlgExp("variable", name=child.value.strip("'\""))

    def reserved_variable_name(self, children):
        child = self.transform(children[0])
        return AlgExp("reserved_variable", value=child)

    def pattern(self, children):
        tree = Tree("pattern", children)
        pattern = PatternBuilder(tree).object
        assert (
            len(pattern.components) == 1
        ), "The pattern {pattern} must consist of a single component, since it is part of an AlgExp."
        component = pattern.components[0]

        return AlgExp("component_pattern", value=component)

    def defined_constant(self, children):
        child = self.transform(children[0])
        return AlgExp("defined_constant", name=child.value)

    # --- Operations ---
    def binary_op_expression(self, children):
        children = [self.transform(c) for c in children]
        left, op, right = children
        return AlgExp("binary_op", operator=op, left=left, right=right)

    def binary_op(self, children):
        return children[0]

    def unary_op_expression(self, children):
        children = [self.transform(c) for c in children]
        op, child = children
        return AlgExp("unary_op", operator=op, child=child)

    def unary_op(self, children):
        return children[0]

    def list_op_expression(self, children):
        children = [self.transform(c) for c in children]
        op_token, *args = children
        return AlgExp("list_op", operator=op_token.value, children=args)

    # --- Parentheses ---
    def parentheses(self, children):
        children = [self.transform(c) for c in children]
        return AlgExp("parentheses", child=children[0])

    # --- Ternary Conditional ---
    def ternary(self, children):
        children = [self.transform(c) for c in children]
        cond, true_expr, false_expr = children
        return AlgExp(
            "ternary", condition=cond, true_expr=true_expr, false_expr=false_expr
        )

    # --- Boolean Logic ---
    def comparison(self, children):
        children = [self.transform(c) for c in children]
        left, op, right = children
        return AlgExp("comparison", operator=op.value, left=left, right=right)

    def logical_or(self, children):
        children = [self.transform(c) for c in children]
        left, right = children
        return AlgExp("logical_or", left=left, right=right)

    def logical_and(self, children):
        children = [self.transform(c) for c in children]
        left, right = children
        return AlgExp("logical_and", left=left, right=right)

    def logical_not(self, children):
        children = [self.transform(c) for c in children]
        return AlgExp("logical_not", child=children[0])

    # --- Boolean Literals ---
    def TRUE(self, token):
        return AlgExp("boolean_literal", value=True)

    def FALSE(self, token):
        return AlgExp("boolean_literal", value=False)

    # --- Default Fallthrough ---
    def __default__(self, data, children, meta):
        # TODO fix
        # if isinstance(node, Tree):
        #     raise NotImplementedError(f"Unsupported AlgExp type: {node.data}")
        # return node
        return Tree(data, children, meta)


def parse_tree_to_alg_exp(tree: Tree) -> AlgExp:
    """
    Convert a Lark ParseTree (rooted at algebraic_expression) to AlgExp.
    Since there isn't extra logic when converting algebraic expressions,
    we can convert from the Lark representation in-place, without creating
    a new object, hence the different design pattern (Transformer instead of Visitor)
    """
    return LarkTreetoAlgExp().transform(tree)
