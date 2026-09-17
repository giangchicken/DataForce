"""logic · what this task's label can be measured by.

Every measurement here says `tool`, which is why none of them is the modality's.
"""

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from agent_toolkit.string_utils import extract_json_from_text

from ..utils import named_function, required_parameters


def called_tools(label: Sequence[Any] | None) -> tuple[str, ...]:
    """The tool names one label calls, in the order it calls them.

    An entry that names no tool is left out: it is not a call, and `schema_valid_label` is what
    says the row is broken.
    """
    called = (named_function(entry) for entry in label or ())
    return tuple(function["name"] for function in called if function is not None)


def call_arguments(function: Mapping[str, Any]) -> Mapping[str, Any]:
    """What one call supplies, whether it wrote its arguments as an object or as JSON text."""
    arguments = function.get("arguments")
    if isinstance(arguments, str):
        arguments = extract_json_from_text(arguments)
    return arguments if isinstance(arguments, Mapping) else {}


def schema_valid_label(label: Sequence[Any] | None, catalog: Sequence[Any]) -> bool:
    """Whether every call names a tool this row was offered and supplies its required params.

    BFCL's AST check turned on the corpus rather than on a model: a label calling a tool the
    sample never offered is a broken row, not a hard example. An empty label is valid.
    """
    required_by_tool: dict[str, set[str]] = {}
    for offered in catalog:
        function = named_function(offered)
        if function is None:
            continue
        parameters = function.get("parameters") or {}
        # A tool whose parameters will not read is a tool no call can be cleared against, so it
        # is left out of the catalog here and a call naming it is invalid.
        if isinstance(parameters, Mapping):
            required_by_tool[function["name"]] = required_parameters(parameters)
    for entry in label or ():
        called = named_function(entry)
        if called is None or called["name"] not in required_by_tool:
            return False
        if not required_by_tool[called["name"]] <= set(call_arguments(called)):
            return False
    return True


def call_counts(labels: Sequence[Sequence[Any] | None]) -> Mapping[int, int]:
    """How many labels make each number of calls.

    `0` is the no-call sample, counted rather than read as a row missing its label, and `2` or
    more is one turn answered by several calls at once.
    """
    counted = Counter(len(called_tools(label)) for label in labels)
    return dict(sorted(counted.items()))


def tool_coverage(
    labels: Sequence[Sequence[Any] | None], catalogs: Sequence[Sequence[Any]]
) -> Mapping[str, int]:
    """Every tool the corpus offers, and how many calls each of them carries.

    **The zeros are the finding**, the same way an empty cell of the coverage matrix is: a tool
    offered a thousand times and never called is a tool the corpus cannot teach. The tail is the
    other half -- two tools carrying most of the calls trains a model that knows two tools.

    A tool called without ever being offered is in here too, with its count. Nothing drops it;
    `schema_valid` is what marks the row that made that call.
    """
    counted: Counter[str] = Counter()
    for label, catalog in zip(labels, catalogs, strict=True):
        offered = (named_function(entry) for entry in catalog)
        counted.update(
            {function["name"]: 0 for function in offered if function is not None}
        )
        counted.update(called_tools(label))
    return dict(sorted(counted.items()))
