import pytest

import kappybara.kappa as kappa


@pytest.mark.parametrize("test_case", [("[max] (1, 2, 4)", 4), ("[min] (1, 2, 4)", 1)])
def test_list_op(test_case):
    alg_exp_str, expected = test_case
    exp_str = f"%obs: 'val' {alg_exp_str}"
    system = kappa.system(exp_str)

    assert system.observables["val"].evaluate() == expected


@pytest.mark.parametrize(
    "test_case", [("[true] [?] 1 [:] 0", 1), ("[false] [?] 1 [:] 0", 0)]
)
def test_conditional(test_case):
    alg_exp_str, expected = test_case
    exp_str = f"%obs: 'val' {alg_exp_str}"
    system = kappa.system(exp_str)

    assert system.observables["val"].evaluate() == expected
