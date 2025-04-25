import pytest
from pathlib import Path

from kappybara.pattern import Pattern
from kappybara.grammar.kaparse import kappa_parser
from kappybara.rule import KappaRuleUnimolecular, KappaRuleBimolecular
from kappybara.grammar.rule_builder import rules_from_kappa
import kappybara.kappa as kappa


# Parser


def test_parse_file():
    kappa_file_path = str(Path(__file__).parent / "wnt_v8.ka")

    kappa_parser.parse_file(kappa_file_path)
    n_rules_expected = 121
    n_agents_expected = 10


def test_parse():
    test_kappa = """
    A(s[.]), S(a[.]) -> A(s[1]), S(a[1])    @	1
    """

    test_kappa = """
    A(s[.])
    """

    ka = kappa_parser.parse(test_kappa)
    print(ka)


# Patterns


def test_pattern_from_kappa():
    test_kappa = """
        A(a[.]{blah}, b[_]{bleh}, c[#], d[some_site_name.some_agent_name], e[13]),
        B(f[13], e[1], z[3]),
        C(x[1]),
        D(w[3]),
        E()
    """
    pattern = kappa.pattern(test_kappa)

    assert ["A", "B", "C", "D", "E"] == list(
        map(lambda agent: agent.type, pattern.agents)
    )
    assert [0, 1, 2, 3, 4] == list(map(lambda agent: agent.id, pattern.agents))
    assert ["a", "b", "c", "d", "e"] == list(
        map(lambda site: site.label, pattern.agents[0].sites.values())
    )
    assert len(pattern.components) == 2


# Rules


def test_rule_from_kappa():
    rule_str = "A(a{p}), B(), . -> A(a{u}), B(), C() @ 1.0"

    rules = rules_from_kappa(rule_str)
    assert len(rules) == 1


@pytest.mark.parametrize(
    "rule_str",
    [
        "A(a{p}), B(), . <-> A(a{u}), B(), C() @ 1.0, 2.0",
        "A(b[.]), A(b[.]) <-> A(b[1]), A(b[1]) @ 100.0, 1.0",
    ],
)
def test_fr_rule_from_kappa(rule_str):
    rules = rules_from_kappa(rule_str)
    assert len(rules) == 2


def test_ambi_rule_from_kappa():
    rule_str = "A(a{p}), B(b[1]), C(c[1]) -> A(a{u}), B(b[.]), C(c[.]) @ 1.0 {2.0}"

    rules = rules_from_kappa(rule_str)
    assert len(rules) == 2
    assert isinstance(rules[0], KappaRuleBimolecular)
    assert isinstance(rules[1], KappaRuleUnimolecular)
    assert rules[0].stochastic_rate == 1.0
    assert rules[1].stochastic_rate == 2.0


def test_uni_rule_from_kappa():
    rule_str = "A(a{p}), B(b[1]), C(c[1]) -> A(a{u}), B(b[.]), C(c[.]) @ 0.0 {2.0}"

    rules = rules_from_kappa(rule_str)
    assert len(rules) == 1
    assert isinstance(rules[0], KappaRuleUnimolecular)
    assert rules[0].stochastic_rate == 2.0


def test_bi_rule_from_kappa():
    rule_str = "A(a{p}), B(b[1]), C(c[1]) -> A(a{u}), B(b[.]), C(c[.]) @ 1.0 {0.0}"

    rules = rules_from_kappa(rule_str)
    assert len(rules) == 1
    assert isinstance(rules[0], KappaRuleBimolecular)
    assert rules[0].stochastic_rate == 1.0


def test_ambi_fr_rule_from_kappa():
    rule_str = (
        "A(a{p}), B(b[1]), C(c[1]) <-> A(a{u}), B(b[.]), C(c[.]) @ 1.0 {2.0}, 3.0"
    )

    rules = rules_from_kappa(rule_str)
    assert len(rules) == 3
    assert isinstance(rules[0], KappaRuleBimolecular)
    assert isinstance(rules[1], KappaRuleUnimolecular)
    assert rules[0].stochastic_rate == 1.0
    assert rules[1].stochastic_rate == 2.0
    assert rules[2].stochastic_rate == 3.0
