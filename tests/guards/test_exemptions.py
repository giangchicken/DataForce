"""P30 · the escape hatch, and the list it is kept on.

A rule with no exemption gets bypassed entirely: the import moves to a helper, or someone deletes
the check. So a line may excuse itself from one invariant by naming that invariant, a reason, an
owner and a date -- and this module is the review, so the hatch does not quietly become the door.

    # guard-exempt: I2 · why · who owns it · 2026-08-23

An exemption excuses the invariant it names and no other; `test_engine_opens_nothing.py` proves
that half, where the rule being excused is.
"""

from .tree import exemptions, malformed_exemptions, module_from_source, modules_in

WELL_FORMED = "import os  # guard-exempt: I1 · the reason · the owner · 2026-08-23"
CEILING = 5


def test_no_exemption_is_missing_its_reason_its_owner_or_its_date() -> None:
    """A hatch without an owner is a hatch nobody can close."""
    assert malformed_exemptions(modules_in()) == []


def test_the_list_is_short() -> None:
    """P30: short, dated and shrinking. Raising this number is a decision, not a fix."""
    standing = exemptions(modules_in())

    assert len(standing) <= CEILING, f"{len(standing)} exemptions: {standing}"


def test_a_well_formed_exemption_is_read_as_one() -> None:
    """P29, for the mechanism itself."""
    assert exemptions([module_from_source(WELL_FORMED)]) != []
    assert malformed_exemptions([module_from_source(WELL_FORMED)]) == []


def test_an_exemption_missing_a_field_is_caught_rather_than_ignored() -> None:
    """The failure mode that matters: a half-written annotation that silently excuses nothing --
    or, worse, is read as excusing everything."""
    for missing in (
        "import os  # guard-exempt: I1",
        "import os  # guard-exempt: I1 · the reason",
        "import os  # guard-exempt: I1 · the reason · the owner",
        "import os  # guard-exempt: the reason · the owner · 2026-08-23",
        "import os  # guard-exempt: I1 · the reason · the owner · someday",
    ):
        module = module_from_source(missing)

        assert malformed_exemptions([module]) != [], missing
        assert exemptions([module]) == [], missing
