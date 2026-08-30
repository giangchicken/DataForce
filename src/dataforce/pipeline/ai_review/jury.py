"""STEP · jury · N independent models answer the record's own task.

The one stage in this phase that costs money, which is the whole of why the phase is three stages
(Decision 3): a bucket boundary that moves re-runs ``triage`` alone, and a panel that has answered
once is never asked again for it.

**The panel is a port and the judgment is not.** A model call opens a socket and no engine module
may (I1, ``ports.py``), so the edge holds the composition, the task statement out of
``config/prompts/`` and the retries, and hands back what each juror said. What a vote is *worth*
stays here, because ``vote_consensus`` is a profile member that refuses an answer the profile does
not permit -- and a schema cannot say *at most one call per tool name*. Let the panel decide
validity by the schema alone and a record can carry five valid votes and no prediction, with
nothing on it to say which of the two readings was wrong.

**Every vote is kept** (Requirement 24). An answer outside this record's answer space is written
down with ``valid: false`` and counted in ``invalid_votes``, never dropped: a panel that is noisy
about one record is evidence about that record, and a dropped vote makes a noisy panel look like a
small one. The two are still told apart -- a juror whose call never came back is *absent*, and a
juror who answered nothing usable is *present and invalid*.

**Only a usable vote is counted toward what the panel said.** ``plurality`` and
``final_prediction`` are folds over the valid votes, because an answer the profile refuses is an
answer no consensus could be built from anyway. ``plurality`` is what most of them gave and
``final_prediction`` is what the profile makes of them per name and per argument, and the two
differ on purpose: a majority calling the right tool with three different arguments has a plurality
of one vote and a defensible consensus.

**A quarantined record is not judged, and neither is one nothing has checked.** Paying a panel to
weigh a record already known broken buys nothing, and a record that never reached ``label_check``
is a record every later service skips for the same reason ``pii_check`` gives -- the absence, not
the verdict.

**No panel is a `ConfigError`, and it is the one thing here that stops a run.** Layer two's absence
leaves ``pii_check`` a layer one to run; this stage's absence leaves nothing, and writing a key
that says the panel agreed on nothing would be a lie about a call nobody made. It is a fact about
the configuration rather than about any record, so it is raised before the first one.
"""

from collections.abc import Iterable, Sequence

from dataforce.engine import Engine, ServiceResult
from dataforce.errors import ConfigError
from dataforce.ports import JurorAnswer, JuryPanel
from dataforce.record import JurorVote, PanelVerdict, Record, StoredAnswer

# The key this stage owns, under `ai_review`: one key, one writer.
STAGE = "jury"


def needs_jury(record: Record) -> bool:
    """This stage's precondition: the record has a label verdict, and it did not fail.

    Named for the decision and not for the state, because at the call site the state reads as the
    past tense of this stage -- *judged* is what a record is on the way out. `pii_check`'s
    `label_check_has_run` keeps the state form for the opposite reason: what it has to make visible
    is that the *value* is not its condition, and this one reads a value.

    Two absences and one verdict, and only the verdict is in § *Per-service contracts*' cell. A
    record `label_check` never saw is skipped here for `pii_check`'s reason rather than for this
    one -- nothing has read its label, so there is nothing to say the panel would be judging.
    """
    verdict = record.data_quality.label_check
    return verdict is not None and not verdict.quarantined


def answered(engine: Engine, panel: JuryPanel, record: Record) -> Sequence[JurorAnswer]:
    """What the panel said about this record, or nothing where the call did not come back.

    A failed panel is read as *no votes*, for the reason § *Error Behavior* gives layer two: a call
    that failed after the library's own retries is a missing answer and not a reason to stop a run
    of twenty thousand records (Requirement 43). The record carries the consequence -- no votes, a
    `final_prediction` of null, and a triage bucket that sends it to a person -- which is a great
    deal louder than a log line.

    The record does not leave: what crosses is the filled slots and this record's materialised
    answer space, which is Requirement 51's own division of the prompt.

    **Both profile calls are made outside the `try`**, on `pii_check`'s line: what is being caught
    is a call across the seam, and a profile that raised would be a bug on this side of it read as
    a panel that did not answer. Neither can raise today -- `catalog_of` skips a malformed entry
    rather than refusing it -- which makes this a fence and not a fix.

    **A `ConfigError` is not caught**, because it is the one exception this codebase raises and it
    means *a human must change configuration*. An adapter that cannot reach its endpoint
    raises on record 1 and on all twenty thousand: swallowed, the run completes with every record
    scoring `0.0` and landing in `contested`, which is a corpus-shaped lie. Every other failure is
    one missing panel answer and the record carries the consequence.
    """
    slots = engine.profile.jury_slots(record)
    space = engine.profile.answer_schema(record)
    try:
        return panel.votes(slots, space)
    except ConfigError:
        raise
    except Exception:
        return ()


def juror_votes(
    engine: Engine, record: Record, said: Sequence[JurorAnswer]
) -> tuple[JurorVote, ...]:
    """Every juror's answer with the one thing the panel does not decide added: is it usable.

    A juror that decoded nothing carries `None`, and it is written down as the empty answer with
    `valid: false` -- because the empty answer is a real vote (*call nothing*) and would otherwise
    be counted as one. That is the one place the two shapes are not the same fact.
    """
    return tuple(
        JurorVote(
            model_name=juror.model_name,
            label_is_right=juror.label_is_right,
            # Explicit rather than `or ()`, because None and the empty answer are exactly
            # what this function is here to tell apart.
            answer=() if juror.answer is None else juror.answer,
            reasoning=juror.reasoning,
            valid=juror.answer is not None
            and engine.profile.answer_is_permitted(juror.answer, record),
        )
        for juror in said
    )


def plurality_of(engine: Engine, votes: Sequence[JurorVote]) -> StoredAnswer:
    """The answer most of the usable votes gave, ties going to the juror that voted first.

    Grouped by the profile's δ rather than by `==`, for `duplicate_check`'s reason: δ is over the
    *set* of names, so two jurors naming the same two tools in a different order voted for one
    answer -- and `==` on the stored form would split them and hand the plurality to whichever
    single dissenting vote came first.

    `()` where no vote was usable, which is also *the panel agreed to call nothing* -- the vote
    count beside it is what tells a reader which. `final_prediction` is where that distinction is
    load-bearing, and it has a null for it.
    """
    grouped: list[list[StoredAnswer]] = []
    for vote in votes:
        if not vote.valid:
            continue
        for same in grouped:
            if engine.profile.answer_distance(same[0], vote.answer) == 0.0:
                same.append(vote.answer)
                break
        else:
            grouped.append([vote.answer])
    return max(grouped, key=len)[0] if grouped else ()


def panel_verdict(engine: Engine, panel: JuryPanel, record: Record) -> PanelVerdict:
    """One record's panel: every vote it cast, what most of them said, and what it is taken to say.

    The panel is a parameter rather than something read off the engine again, because `jury` has
    already refused a run without one -- passing it down is what makes *no panel here* a state
    nothing below this line can be in.

    `panel_version` and `prompt_version` are read off the panel rather than returned per record: a
    composition is a fact about the run, and both reach the record because a change to either
    invalidates every comparison drawn across them.
    """
    votes = juror_votes(engine, record, answered(engine, panel, record))
    usable = [vote.answer for vote in votes if vote.valid]
    return PanelVerdict(
        panel_version=panel.panel_version,
        prompt_version=panel.prompt_version,
        llm_votes=votes,
        invalid_votes=sum(1 for vote in votes if not vote.valid),
        plurality=plurality_of(engine, votes),
        final_prediction=engine.profile.vote_consensus(usable, record),
    )


def jury(engine: Engine, records: Iterable[Record]) -> ServiceResult:
    """Every record a panel would judge, one key richer: what N models said about its label.

    There is no side output. A vote is a value on the record and the run manifest already carries
    which panel produced it -- the records are the report (Requirement 44).
    """
    panel = engine.jury_panel
    if panel is None:
        raise ConfigError(
            "ai_review needs a jury panel and this engine was opened without one; "
            "the edge supplies it at composition"
        )
    return ServiceResult(
        records=tuple(
            record.model_copy(
                update={
                    "ai_review": record.ai_review.model_copy(
                        update={STAGE: panel_verdict(engine, panel, record)}
                    )
                }
            )
            if needs_jury(record)
            else record
            for record in records
        )
    )
