import pytest

from kappybara.site_states import *


@pytest.mark.parametrize(
    "test_pair",
    [
        (EmptyState(), EmptyState()),
        (UndeterminedState(), UndeterminedState()),
        (WildCardPredicate(), WildCardPredicate()),
        (BoundPredicate(), BoundPredicate()),
        (SiteTypePredicate("a", "A"), SiteTypePredicate("a", "A")),
    ],
)
def test_state_comparison_eq(test_pair):
    a, b = test_pair
    assert a == b
