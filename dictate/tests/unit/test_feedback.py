"""Which notifications reach the desktop."""

import pytest
from hamcrest import assert_that, equal_to, is_

from dictate.feedback import FAILURE, STATE, should_notify


@pytest.mark.parametrize(
    ("level", "kind", "sent"),
    [
        ("all", STATE, True),
        ("all", FAILURE, True),
        ("failures", STATE, False),
        ("failures", FAILURE, True),
        ("none", STATE, False),
        ("none", FAILURE, False),
    ],
)
def test_the_level_decides(level: str, kind: str, *, sent: bool) -> None:
    assert_that(should_notify(level, kind), is_(equal_to(sent)))
