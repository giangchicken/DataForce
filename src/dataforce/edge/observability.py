"""TOOL · the stdout handler, and the three keys every event carries.

Every engine module emits through ``logging.getLogger(__name__)`` and nothing else -- a logger call
opens no file and names no path, which is what keeps it inside Requirement 36. *Where* those records
go is the edge's decision, and this is the module that makes it.

**One module because there are two shells.** ``edge/main.py`` and ``edge/cli.py`` each install a
handler at start-up. Written twice, the format and the three mandatory keys -- ``run_id``,
``record_id``, and the stage that emitted it -- would be a contract with two copies and no owner. An
event that cannot be joined to a run and a record is a sentence in a log file rather than data, so
the contract needs somewhere to live.

Not the report. ``ServiceResult`` carries records and side output; ``metrics.json`` is a fold over
them at the edge. This stream is for watching a run *while it runs* (spec.md § *Observability*).
"""
