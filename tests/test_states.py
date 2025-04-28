import pytest

import kappybara.site_states as states


@pytest.mark.parametrize(
    "test_pair",
    [
        (states.Empty(), states.Empty()),
        (states.Undetermined(), states.Undetermined()),
        (states.Wildcard(), states.Wildcard()),
        (states.Bound(), states.Bound()),
        (states.SiteType("a", "A"), states.SiteType("a", "A")),
    ],
)
def test_state_comparison_eq(test_pair):
    a, b = test_pair
    assert a == b
