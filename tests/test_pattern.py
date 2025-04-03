import pytest
from kappybara.pattern import ComponentPattern, Pattern


def test_pattern_from_kappa():
    test_kappa = """
        A(a[.]{blah}, b[_]{bleh}, c[#], d[some_site_name.some_agent_name], e[13]),
        B(f[13], e[1], z[3]),
        C(x[1]),
        D(w[3]),
        E()
    """
    pattern = Pattern.from_kappa(test_kappa)

    assert ["A", "B", "C", "D", "E"] == list(
        map(lambda agent: agent.type, pattern.agents)
    )
    assert [0, 1, 2, 3, 4] == list(map(lambda agent: agent.id, pattern.agents))
    assert ["a", "b", "c", "d", "e"] == list(
        map(lambda site: site.label, pattern.agents[0].sites.values())
    )
    assert len(pattern.components) == 2


@pytest.mark.parametrize(
    "test_case",
    [
        ("A(a[.]{u})", "A(a{u}[.])", True),
        ("A(a[.]{u})", "A(a{p}[.])", False),
        ("A(a[#]{#})", "A(a{#}[#])", True),
        (
            "A(a[#]{#})",
            "A(a[.]{#})",
            False,
        ),  # Important distinction vs. embeddings/subgraph isomorphism
        ("A(a[#]{#})", "A(a[#]{u})", False),
        ("A()", "A(a{u})", False),
        ("A(a[.]{u})", "A(a[.])", False),
        ("A(a[1]{u}), A(a[1])", "A(a[1]{u}), B(a[1])", False),
        (
            "A(a1[1]{u}, a2[3]), B(b1[1], b2[2]), C(c1[2], c2[3])",
            "A(a1[1]{u}, a2[3]), C(c1[2], c2[3]), B(b1[1], b2[2])",
            True,
        ),
        (
            "A(a1[1]{u}), B(b1[1], b2[2]), C(c1[2])",
            "A(a1[1]{u}, a2[3]), B(b1[1], b2[2]), C(c1[2], c2[3])",
            False,
        ),
        (
            "A(a1[1]{u}), B(b1[1], b2[2]), C(c1[2])",
            "A(a1[1]{u}, a2[3]), B(b1[1], b2[2]), C(c1[2], c2[3])",
            False,
        ),
        (
            "A(a1[1], a2[2], a3[5]), B(b1[2], b2[3]), C(c1[3], c2[4], c3[5]), D(d1[4], d2[1])",
            "B(b1[2], b2[3]), D(d1[4], d2[1]), C(c1[3], c2[4], c3[5]), A(a1[1], a2[2], a3[5])",
            True,
        ),
        (
            "A(a1[1], a2[2], a3[5]), B(b1[2], b2[3], b3[6]), C(c1[3], c2[4], c3[5]), D(d1[4], d2[1], d3[6])",
            "A(a1[1], a2[2], a3[5]), B(b1[2], b2[3], b3[5]), C(c1[3], c2[4], c3[6]), D(d1[4], d2[1], d3[6])",
            False,
        ),
    ],
)
def test_component_isomorphism(test_case):
    """
    Test various cases of isomorphism between connected components.
    """
    a_str, b_str, expected_result = test_case

    a = ComponentPattern.from_kappa(a_str)
    b = ComponentPattern.from_kappa(b_str)

    assert a.isomorphic(b) == b.isomorphic(a)
    assert expected_result == a.isomorphic(b)


@pytest.mark.parametrize(
    "test_case",
    [
        ("A(a1[1]), A(a1[1])", 2),
        ("A(a1[1]), A(a2[1])", 1),
        ("A(a1[3], a2[1]), A(a1[1], a2[2]), A(a1[2], a2[3])", 3),
    ],
)
def test_automorphism_counting(test_case):
    kappa_str, n_automorphisms_expected = test_case

    component = ComponentPattern.from_kappa(kappa_str)

    assert component.isomorphic(component)
    assert n_automorphisms_expected == len(component.find_isomorphisms(component))


if __name__ == "__main__":
    test_kappa = """
        A(a[.]{blah}, b[_]{bleh}, c[#], d[some_site_name.some_agent_name], e[13]),
        B(f[13], e[1], z[3]),
        C(x[1]),
        D(w[3]),
        E()
    """

    p = Pattern.from_kappa(test_kappa)
