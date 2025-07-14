from kappybara.system import KappaSystem
from kappybara.mixture import ComponentMixture
from kappybara.pattern import Agent, Component, Pattern
from kappybara.rule import Rule
from kappybara.alg_exp import AlgExp
from kappybara.grammar import (
    kappa_parser,
    parse_tree_to_alg_exp,
    AgentBuilder,
    PatternBuilder,
    RuleBuilder,
)


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


def rules(kappa_str: str) -> list[Rule]:
    """
    Forward-reverse rules (with a "<->") really represent two separate rules,
    which is why this doesn't quite work as a class method for `Rule`.
    """
    input_tree = kappa_parser.parse(kappa_str)
    assert input_tree.data == "kappa_input"
    rule_tree = input_tree.children[0]
    return RuleBuilder(rule_tree).objects


def rule(kappa_str: str) -> Rule:
    # TODO: namespace these fncs so variable names aren't as sensitive?
    r = rules(kappa_str)
    assert len(r) == 1, "The given rule expression represents more than one rule."
    return r[0]


def alg_exp(kappa_str: str) -> AlgExp:
    input_tree = kappa_parser.parse(kappa_str)
    assert input_tree.data == "kappa_input"

    alg_exp_tree = input_tree.children[0]
    assert alg_exp_tree.data == "!algebraic_expression"

    return parse_tree_to_alg_exp(alg_exp_tree)


def system(kappa_str: str) -> KappaSystem:
    input_tree = kappa_parser.parse(kappa_str)
    assert input_tree.data == "kappa_input"

    variables: dict[str, AlgExp] = {}
    observables: dict[str, AlgExp] = {}
    rules: list[Rule] = []
    system_params: dict[str, int] = {}
    inits: list[tuple[AlgExp, Pattern]] = []

    for child in input_tree.children:
        tag = child.data

        if tag in ["f_rule", "fr_rule", "ambi_rule", "ambi_fr_rule"]:
            new_rules = RuleBuilder(child).objects
            rules.extend(new_rules)

        elif tag == "variable_declaration":
            name_tree = child.children[0]
            assert name_tree.data == "declared_variable_name"
            name = name_tree.children[0].value.strip("'\"")

            alg_exp_tree = child.children[1]
            assert alg_exp_tree.data == "algebraic_expression"
            value = parse_tree_to_alg_exp(alg_exp_tree)

            variables[name] = value

        elif tag == "plot_declaration":
            raise NotImplementedError

        elif tag == "observable_declaration":
            label_tree = child.children[0]
            assert isinstance(label_tree, str)
            name = label_tree.strip("'\"")

            alg_exp_tree = child.children[1]
            assert alg_exp_tree.data == "algebraic_expression"
            value = parse_tree_to_alg_exp(alg_exp_tree)

            observables[name] = value

        elif tag == "signature_declaration":
            # TODO
            raise NotImplementedError

        elif tag == "init_declaration":
            alg_exp_tree = child.children[0]
            assert alg_exp_tree.data == "algebraic_expression"
            amount = parse_tree_to_alg_exp(alg_exp_tree)

            pattern_tree = child.children[1]
            if pattern_tree.data == "declared_token_name":
                raise NotImplementedError
            assert pattern_tree.data == "pattern"
            pattern = PatternBuilder(pattern_tree).object

            inits.append((amount, pattern))

        elif tag == "declared_token":
            raise NotImplementedError

        elif tag == "definition":
            reserved_name_tree = child.children[0]
            assert reserved_name_tree.data == "reserved_name"
            name = reserved_name_tree.children[0].value.strip("'\"")

            value_tree = child.children[1]
            assert value_tree.data == "value"
            value = int(value_tree.children[0].value)

            system_params[name] = value

        elif tag == "pattern":
            raise NotImplementedError

        else:
            raise TypeError(f"Unsupported input type: {tag}")

    system = KappaSystem(None, rules, observables, variables)

    for init in inits:
        amount = int(init[0].evaluate(system))
        pattern = init[1]
        system.mixture.instantiate(pattern, amount)

    return system
