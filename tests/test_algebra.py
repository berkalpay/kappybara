import pytest

import kappybara.kappa as kappa


@pytest.mark.parametrize(
    "expression, result",
    [
        ("[true] [?] 1 [:] 0", 1),
        ("[false] [?] 1 [:] 0", 0),
        ("[max] (1, 2, 4)", 4),
        ("[min] (1, 2, 4)", 1),
    ],
)
def test_algexp_evaluation(expression, result):
    assert kappa.system(f"%obs: 'x' {expression}")["x"] == result
