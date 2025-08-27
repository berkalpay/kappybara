import pytest
from kappybara.system import System


@pytest.mark.parametrize(
    "expression, result",
    [
        ("[true] [?] 1 [:] 0", 1),
        ("[false] [?] 1 [:] 0", 0),
        ("[max] (1) (4)", 4),
        ("[min](1)(4)", 1),
    ],
)
def test_expression_evaluation(expression, result):
    assert System.from_ka(f"%obs: 'x' {expression}")["x"] == result
