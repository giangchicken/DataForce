"""Stages 0-4: what can be checked about a corpus without an opinion about it.

Validity, privacy, uniqueness -- with `load` and `embed` as what makes checking them
possible. The phase ends with a corpus; `ai_review` is the first opinion about it.

One module per stage, named for the stage, because a stage is exactly the unit a person
re-runs: `dataforce run remove_invalid`. `core/flow.py` names this phase and the stages
it covers, and a guard checks these filenames against the core spec's stage table.
"""
