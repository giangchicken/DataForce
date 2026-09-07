"""logic · what the human left, and the record that gets stored.

The record keeps what arrived and adds what the review made of it. `messages`, `tools` and `label`
are the sample as it was posted; `new_messages`, `new_tools` and `new_label` are the versions that
ship -- the human's edits applied, then every confirmed value replaced by its placeholder.
`new_tools` is `None` where the human left the catalog alone, because an unmodified catalog has no
new version to carry.

**The row therefore holds the raw content as well as the redacted content.** Keeping both is what
makes a review auditable -- you can see what was changed and by whom -- and it means the redaction
protects a reader of `new_*` and not the database itself. Anything with the row has the values.

`reviewed_record` is that composition on its own so it can be tested without a database;
`stored_record` is it plus the write.
"""

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from dataforce.errors import ConfigError


def span_values(scan: Mapping[str, Any]) -> tuple[tuple[str, str], ...]:
    """Each span's value and its placeholder, longest value first.

    Longest first so a shorter value inside a longer one cannot cut it. A span whose offsets are
    not integers is skipped -- it names no value to replace.
    """
    text = scan.get("review_text") or ""
    pairs = [
        (text[span["start"] : span["end"]], span["placeholder"])
        for span in scan.get("spans") or ()
        if isinstance(span.get("start"), int) and isinstance(span.get("end"), int)
    ]
    return tuple(
        sorted((pair for pair in pairs if pair[0]), key=lambda pair: -len(pair[0]))
    )


def replaced_node(node: Any, pairs: Sequence[tuple[str, str]]) -> Any:
    """One subtree with every value replaced by its placeholder.

    Applied to the whole subtree, because a value replaced in one field and left in another is not
    replaced.
    """
    if isinstance(node, str):
        for value, placeholder in pairs:
            node = node.replace(value, placeholder)
        return node
    if isinstance(node, Mapping):
        return {key: replaced_node(value, pairs) for key, value in node.items()}
    if isinstance(node, (list, tuple)):
        return [replaced_node(value, pairs) for value in node]
    return node


def reviewed_record(
    sample: Mapping[str, Any],
    *,
    messages: Any = None,
    tools: Any = None,
    label: Any = None,
    scan: Mapping[str, Any] | None = None,
    llm: Mapping[str, Any] | None = None,
    sft: Mapping[str, Any] | None = None,
) -> Mapping[str, Any]:
    """The record as the review left it: what arrived, and what ships beside it.

    Each of `messages`, `tools` and `label` is what the human edited it to, or None where they left
    it alone. Redaction runs after the edit, so a value the human typed is redacted too.
    """
    pairs = span_values(scan or {})
    edited_tools = tools if tools is not None else sample.get("tools")
    return {
        "id": sample.get("id"),
        "messages": sample.get("messages"),
        "tools": sample.get("tools"),
        "label": sample.get("label"),
        "new_messages": replaced_node(
            messages if messages is not None else sample.get("messages"), pairs
        ),
        "new_tools": replaced_node(edited_tools, pairs) if tools is not None else None,
        "new_label": replaced_node(
            label if label is not None else sample.get("label"), pairs
        ),
        "personal_data": scan,
        "duplicate": None,
        "abnormal": None,
        "llm": llm,
        "sft": sft,
    }


def unreplaced_values(
    record: Mapping[str, Any], pairs: Sequence[tuple[str, str]]
) -> tuple[str, ...]:
    """Every value still present in what ships, in the order declared.

    Read over `new_messages`, `new_tools` and `new_label` only. The originals hold the raw content
    on purpose, so checking the whole record would fail by design and prove nothing.
    """
    shipped = str(
        {key: record.get(key) for key in ("new_messages", "new_tools", "new_label")}
    )
    return tuple(value for value, _ in pairs if value in shipped)


def stored_record(
    record: Mapping[str, Any],
    *,
    write: Callable[[str, Mapping[str, Any]], Mapping[str, Any]],
) -> Mapping[str, Any]:
    """The row as it landed, keyed by the record's own id.

    `write` is handed in rather than imported: the store is an adapter and this is logic, so the
    direction only runs one way and the edge is what connects the two.

    Raises `ConfigError` on a record with no id, and on one whose shipped version still holds a
    value its own scan says it replaced -- a rule nothing checks is a rule the store does not have.
    """
    record_id = record.get("id")
    if not isinstance(record_id, str) or not record_id:
        raise ConfigError("a record with no id cannot be stored")
    left = unreplaced_values(record, span_values(record.get("personal_data") or {}))
    if left:
        raise ConfigError(
            f"{record_id}: {len(left)} replaced value(s) are still in what ships"
        )
    return write(record_id, record)
