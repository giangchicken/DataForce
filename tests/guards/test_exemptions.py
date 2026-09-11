"""The escape hatch, and the list it is kept on.

A rule with no exemption gets bypassed entirely: the import moves to a helper, or someone deletes
the check. So a line may excuse itself from one rule by naming that rule, a reason, an owner and a
date -- and this module is the review, so the hatch does not quietly become the door.

    # guard-exempt: H-8 · why · who owns it · 2026-08-23

The ID is `AGENTS.md`'s, which is the only scheme anything defines: `E-4` is what a break has to
carry. An exemption excuses the rule it names and no other.
"""

from .tree import exemptions, malformed_exemptions, module_from_source, modules_in

WELL_FORMED = "import os  # guard-exempt: T-6 · the reason · the owner · 2026-08-23"
BY_RULE = "import os  # guard-exempt: H-8 · the reason · the owner · 2026-09-07"
CEILING = 5


def test_no_exemption_is_missing_its_reason_its_owner_or_its_date() -> None:
    """A hatch without an owner is a hatch nobody can close."""
    assert malformed_exemptions(modules_in()) == []


def test_the_list_is_short() -> None:
    """The exemption list: short, dated and shrinking. Raising this number is a decision, not a fix."""
    standing = exemptions(modules_in())

    assert len(standing) <= CEILING, f"{len(standing)} exemptions: {standing}"


def test_a_well_formed_exemption_is_read_as_one() -> None:
    """Proved red, for the mechanism itself."""
    assert exemptions([module_from_source(WELL_FORMED)]) != []
    assert malformed_exemptions([module_from_source(WELL_FORMED)]) == []


def test_an_exemption_may_name_a_rule_of_agents_md_rather_than_an_invariant() -> None:
    """`test_import_direction.py` enforces `H-8`, so `H-8` is what a line there has to name."""
    assert exemptions([module_from_source(BY_RULE)]) != []
    assert malformed_exemptions([module_from_source(BY_RULE)]) == []


def test_an_exemption_missing_a_field_is_caught_rather_than_ignored() -> None:
    """The failure mode that matters: a half-written annotation that silently excuses nothing --
    or, worse, is read as excusing everything."""
    for missing in (
        "import os  # guard-exempt: T-6",
        "import os  # guard-exempt: T-6 · the reason",
        "import os  # guard-exempt: T-6 · the reason · the owner",
        "import os  # guard-exempt: the reason · the owner · 2026-08-23",
        "import os  # guard-exempt: T-6 · the reason · the owner · someday",
        "import os  # guard-exempt: h-8 · the reason · the owner · 2026-09-07",
        "import os  # guard-exempt: I6 · the reason · the owner · 2026-09-07",
        "import os  # guard-exempt: X-9 · the reason · the owner · 2026-09-07",
    ):
        module = module_from_source(missing)

        assert malformed_exemptions([module]) != [], missing
        assert exemptions([module]) == [], missing
