"""logic · what this task's label can be measured by.

Every measurement here says `tool`, which is why none of them is the modality's. Every one is also
a **pure function of a label and a catalog** -- nothing here is handed a session, and that is what
keeps this `logic` and reachable from `services/`, which is where these figures are composed into
one answer. The `GROUP BY`s over the same corpus are `sample_building.py`, with the rest of what
holds a session.
"""

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from agent_toolkit.string_utils import extract_json_from_text

from .utils import list_required_parameters, read_named_function


def list_called_tools(label: Sequence[Any] | None) -> tuple[str, ...]:
    called = (read_named_function(entry) for entry in label or ())
    return tuple(function["name"] for function in called if function is not None)


def read_call_arguments(function: Mapping[str, Any]) -> Mapping[str, Any]:
    """What one call supplies, whether it wrote its arguments as an object or as JSON text."""
    arguments = function.get("arguments")
    if isinstance(arguments, str):
        arguments = extract_json_from_text(arguments)
    return arguments if isinstance(arguments, Mapping) else {}


def validate_label_calls(label: Sequence[Any] | None, catalog: Sequence[Any]) -> bool:
    required_by_tool: dict[str, set[str]] = {}
    for offered in catalog:
        function = read_named_function(offered)
        if function is None:
            continue
        parameters = function.get("parameters") or {}

        if isinstance(parameters, Mapping):
            required_by_tool[function["name"]] = list_required_parameters(parameters)
    for entry in label or ():
        called = read_named_function(entry)
        if called is None or called["name"] not in required_by_tool:
            return False
        if not required_by_tool[called["name"]] <= set(read_call_arguments(called)):
            return False
    return True


def count_tool_calls(
    labels: Sequence[Sequence[Any] | None], catalogs: Sequence[Sequence[Any]]
) -> Mapping[str, int]:
    counted: Counter[str] = Counter()
    for label, catalog in zip(labels, catalogs, strict=True):
        offered = (read_named_function(entry) for entry in catalog)
        counted.update(
            {function["name"]: 0 for function in offered if function is not None}
        )
        counted.update(list_called_tools(label))
    return dict(sorted(counted.items()))


def list_offered_tools(catalogs: Sequence[Sequence[Any]]) -> tuple[str, ...]:
    offered = (read_named_function(entry) for catalog in catalogs for entry in catalog)
    return tuple(
        sorted({function["name"] for function in offered if function is not None})
    )
