"""Parse the `TOOLS:` block, and turn one source item into a canonical record.

The marker tokens -- `{trigger}`, `{hold_other}`, `{hold_missing}`, `{constraint}`,
`{turn_trigger}`, `{or}` -- are at once the deterministic rule source, the
annotator's only evidence, and the thing most easily destroyed in passing. Every
clause here is therefore captured as the source wrote it: this parser finds where
a clause starts and never rewrites what follows.

The catalog-name convention is settled here, and it decides two of the four
validity counts. A name is whatever stands between brackets on a line of its own:
`card.search_faq`, `end-call`, `calculate BMI` and one name carrying a literal tab
are real entries with real bodies, and a stricter pattern reads 841 empty catalogs
and 722 out-of-catalog labels that are artifacts of the pattern rather than facts
about the corpus. Measured over the whole file: all 105,880 bracketed lines are
followed by `Mục đích`, and all 14,411 names appearing in labels resolve.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from agent_toolkit.string_utils import compute_hash

from dataforce.shared.errors import ConfigError
from dataforce.shared.record import (
    Part,
    Producer,
    Record,
    Source,
    TextPart,
    compute_rid,
)

__all__ = [
    "PROVENANCE_KEY",
    "Catalog",
    "Parameter",
    "Tool",
    "adapt",
    "answer_space_for",
    "catalog_fingerprint",
    "catalog_names",
    "parse_catalog",
]

# Where the load stage puts the two things only it knows: which file this item came
# from, and which modality and profile were resolved to read it. Required rather
# than defaulted, so a record without provenance cannot be constructed at all.
PROVENANCE_KEY = "__provenance__"

# A catalog fingerprint, in hex characters. Long enough that two different catalogs
# colliding is not a thing that happens to 21,172 records.
_FINGERPRINT_LENGTH = 16

_TOOLS_HEADER = "TOOLS:"
_NAME = re.compile(r"^[ \t]*\[([^\]\n]+)\][ \t]*$", re.MULTILINE)
_PARAM = re.compile(r"^[ \t]+([^\s(*]+)(\*?)[ \t]*\(([^)]*)\)[ \t]*:[ \t]*(.*)$")

# The clause labels, as the corpus writes them. All 105,880 entries carry the
# first three; 6,798 carry no `require:` and no `params:` at all.
_PURPOSE = "Mục đích:"
_CALL_WHEN = "Khi nào gọi:"
_HOLD_WHEN = "Khi nào KHÔNG gọi:"
_REQUIRE = "require:"
_PARAMS = "params:"


@dataclass(frozen=True)
class Parameter:
    """One parameter of one tool. `description` carries `{constraint}` clauses."""

    name: str
    type: str
    required: bool
    description: str


@dataclass(frozen=True)
class Tool:
    """One catalog entry, with every clause as the source wrote it."""

    name: str
    purpose: str
    call_when: str
    hold_when: str
    require: tuple[str, ...]
    params: tuple[Parameter, ...]


@dataclass(frozen=True)
class Catalog:
    """The tools one record offers, in the order the record offers them."""

    tools: tuple[Tool, ...]

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(tool.name for tool in self.tools)

    @property
    def is_empty(self) -> bool:
        return not self.tools


def _clause(body: str, label: str) -> str:
    """Everything after `label` on its line, verbatim. Empty when absent."""
    for line in body.splitlines():
        if line.startswith(label):
            return line[len(label) :].strip()
    return ""


def _parameters(body: str) -> tuple[Parameter, ...]:
    """The indented lines after `params:`, each `name* (type): description`."""
    found: list[Parameter] = []
    in_params = False
    for line in body.splitlines():
        if line.startswith(_PARAMS):
            in_params = True
            continue
        if not in_params:
            continue
        matched = _PARAM.match(line)
        if matched is None:
            continue
        name, star, declared, description = matched.groups()
        found.append(
            Parameter(
                name=name,
                type=declared.strip(),
                required=star == "*",
                description=description,
            )
        )
    return tuple(found)


def _tool(name: str, body: str) -> Tool:
    require = _clause(body, _REQUIRE)
    return Tool(
        name=name,
        purpose=_clause(body, _PURPOSE),
        call_when=_clause(body, _CALL_WHEN),
        hold_when=_clause(body, _HOLD_WHEN),
        require=tuple(part.strip() for part in require.split(",") if part.strip()),
        params=_parameters(body),
    )


def parse_catalog(system: str) -> Catalog:
    """The catalog a system message offers.

    A message with no `TOOLS:` header and one whose header is followed by no entry
    both give an empty catalog rather than an exception: whether that is a
    genuinely toolless prompt or a parser miss is not the parser's to decide, and
    `empty_catalog` is a quarantine for triage rather than a verdict.
    """
    if _TOOLS_HEADER not in system:
        return Catalog(tools=())
    block = system.split(_TOOLS_HEADER, 1)[1]
    found = list(_NAME.finditer(block))
    # One entry runs from its own name line to the next one, or to the end.
    bounds = [*(match.start() for match in found), len(block)]
    return Catalog(
        tools=tuple(
            _tool(match.group(1), block[bounds[index] : bounds[index + 1]])
            for index, match in enumerate(found)
        )
    )


def catalog_fingerprint(names: Sequence[str]) -> str:
    """What makes two records the same scenario: the tools they were offered.

    Order-sensitive, because the catalog is presented to the model in order and two
    orderings are two prompts. `source_index` is not this: it is unique per record,
    measured, and so gives no leakage protection at all.
    """
    return compute_hash("|".join(names), "sha256")[:_FINGERPRINT_LENGTH]


def answer_space_for(catalog: Catalog) -> dict[str, Any]:
    """This record's answer space: an array of names drawn from its own catalog.

    The `enum` is requirement 5's catalog constraint, and the jury hands this
    straight to `complete_structured`, which is why no stage validates an answer
    against a catalog itself.
    """
    return {
        "type": "array",
        "items": {"type": "string", "enum": list(catalog.names)},
    }


def catalog_names(record: Record) -> list[str]:
    """The catalog a record was adapted with, read back off its answer space."""
    if record.answer_space is None:
        raise ConfigError(
            f"record {record.rid} carries no answer space; "
            "it was not adapted by the tool_decision profile"
        )
    names: list[str] = record.answer_space["items"]["enum"]
    return names


def _provenance(raw: Mapping[str, Any]) -> tuple[Source, Producer]:
    """Where this item came from and what read it, both supplied by the stage."""
    try:
        given = raw[PROVENANCE_KEY]
        return Source(**given["source"]), Producer(**given["producer"])
    except KeyError as missing:
        raise ConfigError(
            f"a raw item reached adapt() without {PROVENANCE_KEY}[{missing}]; the "
            "load stage supplies the source file's digest, this item's offset, the "
            "read time, and the modality and profile it resolved"
        ) from None


def _system_text(parts: Sequence[Part]) -> str:
    """The system turn, which is where the catalog is. Empty if there is none."""
    return next(
        (
            part.text
            for part in parts
            if isinstance(part, TextPart) and part.role == "system"
        ),
        "",
    )


def adapt(raw: Mapping[str, Any], parts: list[Part]) -> Record:
    """One canonical record, keeping every field this profile does not own.

    `meta` is the source's own `meta` plus whatever else the item carried, because
    what looks like noise now is what a later question turns out to need. The label
    is kept in source order: it means a set, and δ reads it as one, but rewriting it
    here would put export's `meta.label` out of step with the assistant message that
    invariant 4 asserts it equals.
    """
    catalog = parse_catalog(_system_text(parts))
    source, producer = _provenance(raw)
    unowned = {
        key: value
        for key, value in raw.items()
        if key not in ("messages", "meta", PROVENANCE_KEY)
    }
    meta = {**unowned, **(raw.get("meta") or {})}
    return Record(
        rid=compute_rid(parts),
        source=source,
        producer=producer,
        content=list(parts),
        answer_space=answer_space_for(catalog),
        label=meta.get("label"),
        meta=meta,
    )
