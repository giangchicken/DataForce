"""TOOL · one subcommand per part; JSONL in, JSONL out.

The same functions the routes call, over a file instead of a request body. One part per invocation,
and the file the last one wrote is what the next one reads.
"""

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from agent_toolkit.file_utils import read_jsonlines, write_jsonlines

from dataforce.services.text2text import Parts, open_parts


async def run_personal_data(
    parts: Parts, rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    from dataforce.modalities.text2text.data_quality import personal_data_scan

    return [
        {"sample_id": row["sample_id"]}
        | (
            await personal_data_scan(
                parts.verifier, row["turns"], tuple(row.get("label", ()))
            )
        ).model_dump()
        for row in rows
    ]


async def run_duplicate_data(
    parts: Parts, rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    from dataforce.modalities.text2text.data_quality import duplicate_groups

    groups = await duplicate_groups(
        parts.embedder,
        {row["sample_id"]: (row["turns"], tuple(row.get("label", ()))) for row in rows},
    )
    return [{"sample_id": key} | value.model_dump() for key, value in groups.items()]


async def run_llm_review(
    parts: Parts, rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    if parts.panel is None:
        raise SystemExit("no jury panel is configured; declare JURY_MODELS")
    return [
        {"sample_id": row["sample_id"]}
        | (await parts.panel.verdict(row["turns"], row.get("label", ""))).model_dump()
        for row in rows
    ]


async def run_sft_review(
    parts: Parts, rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    if parts.reviewer is None:
        raise SystemExit("no finetuned reviewer is configured; declare SFT_MODEL")
    return [
        {"sample_id": row["sample_id"]}
        | (await parts.reviewer.predict(row["turns"], row.get("label", ""))).model_dump()
        for row in rows
    ]


async def run_decide(parts: Parts, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from dataforce.modalities.text2text.human_review import Evidence, label_decision

    return [
        {"sample_id": row["sample_id"]}
        | label_decision(Evidence.model_validate(row.get("evidence", {}))).model_dump()
        for row in rows
    ]


PARTS = {
    "personal-data": run_personal_data,
    "duplicate-data": run_duplicate_data,
    "llm-review": run_llm_review,
    "sft-review": run_sft_review,
    "decide": run_decide,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dataforce", description=__doc__)
    parser.add_argument("part", choices=sorted(PARTS))
    parser.add_argument("--samples", type=Path, required=True, help="JSONL in")
    parser.add_argument("--into", type=Path, required=True, help="JSONL out")
    args = parser.parse_args(argv)

    rows = list(read_jsonlines(str(args.samples)))
    written = asyncio.run(PARTS[args.part](open_parts(), rows))
    args.into.parent.mkdir(parents=True, exist_ok=True)
    write_jsonlines(
        str(args.into), [json.loads(json.dumps(row, default=str)) for row in written]
    )
    print(f"{args.part}: {len(written)} rows -> {args.into}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
