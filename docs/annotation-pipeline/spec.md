# DataForce — Implementation Spec

**Status:** awaiting review · **Reads from:** [`objective.md`](objective.md) · **Style reference:**
the internal `agent-evaluation` service, which `agent-toolkit` was extracted from

---

## What

DataForce turns a raw, model-labelled corpus into a training-ready dataset plus the evidence for
trusting it. This spec fixes the buildable surface of that pipeline: **two axes** (a *modality* —
`text2text`, `speech2text`, … — which is a family of tasks, and a *profile* — `tool_decision`,
function calling — which is one task inside that family), **four main endpoints**
(`load_data`, `data_quality`, `ai_review`, `human_review`) each exposing its services as sub-endpoints,
and **one service per stage of the flow**, all with the same signature — records in, records out —
driven two ways from one implementation: over HTTP, and in-process.

`objective.md` says *why* and *what one record looks like*. This document says *what to build*: the
flow, the two protocols, the package layout, the request and response shapes, the question store, and
what fails a run.

---

## Context

**The tree is empty on purpose.** `src/` was deleted in `da50d46` so the build could restart from
`objective.md` without two answers available for any question, and `tests/` is deleted in this pass for
the same reason: it described the deleted package, and a spec written to keep it green would inherit a
design nobody chose. **Nothing in this document is shaped by a file that used to exist.** `config/`,
`params.yaml`, the `Makefile` and `pyproject.toml` are still the old package's and are
replaced by the rebuild, not inherited; `dvc.yaml` and `.dvc/` are gone: reproducibility is the run manifest and its policy digests
(Requirement 45), artifacts are `edge/artifacts.py`'s, and re-runs are deliberate rather than a DAG.

**No corpus is declared.** `fc_train_final.json` is out of use, and everything derived from it goes with
it: `metrics/corpus_profile.json`, `params.source.path` and `params.source.sha256`, the measured
`params.invalid_counts`, `params.gold.records`, `params.max_answer_cardinality`, and the symlinks under
`data/raw/`. **No number in this document is inherited from it.** The input is what `objective.md` §2
documents and nothing else: standard OpenAI chat-completion records carrying the tool catalog as data.
`params.yaml` keeps the *shape* of those keys — a declared source digest, and a declared expected count
per label check — populated by the first run over whatever corpus is declared, which is what makes a
later drift a decision rather than a surprise.

**The style reference is a real codebase, not a preference.** The internal `agent-evaluation` service
this project's `agent-toolkit` was extracted from settles four things this spec would otherwise invent
(it is not public, so it is cited by what it does rather than by where it lives):

- `api/main.py` holds a `create_app()` factory; `api/routers/<domain>/<feature>.py` holds one
  `APIRouter(tags=[…])` per feature; `main.py` mounts each with a URL prefix. Those are the reference's
  own paths; here the same shape sits under `edge/`, for the reason given in § *Engine and edge*.
- **URLs are kebab-case** (`/evaluate-function-calling`), module names snake_case.
- **Every field of every request, response and record model carries `Field(..., description=…)`**, and
  related fields are grouped under `# --- Section ---` comments. This is Requirement 1 below.
- A router handler is thin: call the service, map `ValueError` → `400` and anything else → `500`.

**What `agent-toolkit` already owns** and must not be re-implemented: `compute_hash`,
`normalize_text` (including `remove_tone_marks`), the four rule-based personal-data scans layer one
is built from — `phone_number_detection_by_rules`, `email_detection_by_rules`,
`otp_detection_by_rules`, `name_detection_by_rules` — and the vocabulary tables behind them,
`slot_filling`, `extract_json_from_text`, atomic `read_jsonlines` / `write_jsonlines` / `read_yaml`,
and the whole LLM client — `complete`, `complete_structured`, `count_tokens`, retries, rate limiting. Those are the ones this pipeline
reaches for and not the whole surface: I6 reads the owned names off the installed library's
`__all__`, so the rule covers every function `agent-toolkit` exports whether or not this sentence
names one.

---

## The two axes

**A modality is a concept and a profile is one module inside it.** `text2text` is a family of tasks;
`tool_decision` is one task in that family, and `summarize` and `classification` would be others in
the same one. The containment is the design and not an accident of packaging: a profile names the
concept it belongs to, and a run pairing it with any other concept hard-stops.

**The containment is a base class.** `class ToolDecision(Text2Text)` — § *The two axes*, taken in T52.
A run resolves to *one object* answering both protocols, and the edge registers it in both of the
registry's namespaces. That is what makes a second module in the family — `summarize`,
`classification` — share the concept's six members rather than reimplementing them, and it is what
lets a reader of the classes see a relationship that used to exist only as `modality: text2text` in
a manifest.

**The two protocols stay separate, and the identity is prefixed so they can.** `Modality` declares
`modality_name`/`modality_version`, `Profile` declares `profile_name`/`profile_version`, and one
object answers all four. A bare `name` on both would be one attribute where every record needs two —
`Branch(modality="text2text", profile="tool_decision")` has to say which concept read a record *and*
which module answered it. Within a run, neither axis may do the other's job: the concept reads and
displays content, the module says what an answer is, and inheritance may not let a member of one
answer for the other.

**Two registry namespaces, one object.** A name is only unique inside the `config/<axis>/` directory
it was read from, and a concept with three modules in it needs one entry per module — so the two
slots survive the hierarchy. The pair is still checked against the *manifests* at composition
(`paired_modality`), because a request body full of declarations may name a pair no class hierarchy
was consulted about.

### Modality — how content is read

**A modality names a family of input-to-output tasks, and provides the common processing framework
for that family.** `text2text`, `speech2text`, `image2text`, `video2text`. The name is the family
boundary; the five members are the framework, and the specific task inside the family is the *profile*.
This is why nothing below answers anything: what the output half declares is which tasks are *in* the
family, not an operation the modality performs. `tool_decision` is in `text2text` because a juror is
prompted with text and answers with text — its answer is a list of calls, and a list of calls emitted
by a model is text.

**The two halves name different things, and neither is a `PartType`.** The first half is the content's
*genre* and `text`, `audio`, `image`, `video` are the *media* a part can carry: `speech2text` is not
`audio2text` because an audio part can be music or a room tone and no transcription task wants those.
The second half is the representation every member then works on. Neither half is registrable on its
own, and nothing validates a name against either vocabulary — the manifest filename is the identity
(Requirement 40), which is what `objective.md` §3 writes on the record: `branch.modality ==
"text2text"`.

**All four names declared today end in `2text`, so the second half currently discriminates nothing.**
That is why it reads as redundant, and it is not: it is a declared boundary waiting for its first
sibling that does not reduce to text. `text2text` is the case where the reduction is the identity.

```python
class Modality(Protocol):
    """One input→output pair: how its content is read, embedded and scanned."""

    modality_name: str     # "text2text" — the manifest filename, never a class body
    modality_version: str  # stamped into every record's provenance; a string, not a number

    def content_parts(self, item: Mapping[str, Any]) -> list[Part]:
        """One source item's turns, as ordered parts. Text verbatim, media by reference."""

    def embedding(self, parts: Sequence[Part]) -> list[float]:
        """A vector for near-duplicate grouping, from the model the manifest names."""

    def personal_data_detectors(self) -> list[Detector]:
        """The high-recall first layer: one scan per class of personal data."""
```

Five members, closed. `Detector` is opaque here and concrete in `text2text/schema.py`
(Requirement 47).

**No member of this protocol emits an annotation tool's markup.** How a conversation is *shown* is
Label Studio's config grammar, and a modality's job is reading content, not speaking to the tool that
displays it. A `Part` already carries `role` and `text`, so the adapter that owns the tool —
`edge/label_studio.py`, the one module that imports its SDK — builds the display fragment from
`record.content` and needs nothing from this axis. That keeps the tool's grammar in one module and
leaves a modality free to be added without a page layout in it.

`Part` is not the modality's to define — a part is a piece of record content, and `build_record` on
the *other* axis takes a `Sequence[Part]` too, so it lives in `record.py` where both protocols can
reach it.

### Profile — what an answer is

**A profile is the dataset's own task.** One exists: `tool_decision` (function calling). A profile
declares the modality it composes with, and a run naming a different one hard-stops.

```python
class Profile(Protocol):
    """One dataset task: what an answer is, how two answers differ, what makes one invalid."""

    profile_name: str     # "tool_decision" — from the manifest filename
    profile_version: str  # stamped into every record's provenance; a string, not a number

    def answer_schema(self, record: Record) -> dict:
        """This record's permitted answers: `oneOf` per offered tool. Never persisted."""

    def answer_config(self, record: Record) -> AnswerConfig:
        """The capture half: the fragment that collects an answer, and the task data it owns.

        Takes the record because half of what it returns is per record: the catalog an annotator
        chooses from is this record's, and a Label Studio project holds
        one config for every task in it, so the names travel as *data* and not as markup."""

    def build_record(self, item: Mapping[str, Any], parts: Sequence[Part],
                     provenance: Provenance) -> Record:
        """One source item into one record. The only place a source shape is *validated*."""

    def label_checks(self) -> list[LabelCheck]:
        """The checks that need no opinion, each named for the defect it finds."""

    def redact_label(self, label: Answer, replacements: Mapping[str, str]) -> Answer:
        """The label with every value `pii_check` replaced in the content replaced too."""

    def answer_distance(self, a: Answer, b: Answer) -> float:
        """δ: 0.0 identical, 1.0 unrelated. Name-first, soft over arguments. `δ(∅, ∅) = 0`."""

    def answer_is_permitted(self, answer: Answer, record: Record) -> bool:
        """Does this answer belong to this record's answer space: the schema, and what it
        cannot say. `answer_schema` materialises the space and a schema cannot express *at most
        one call per tool name*, so the member is the whole question and not the schema alone."""

    def vote_consensus(self, votes: Sequence[Answer], record: Record) -> Answer | None:
        """The panel's answer; `[]` where it agreed on none; None where none is defensible."""

    def question_text(self, record: Record) -> str:
        """What an annotator is asked, in their language. No model output may appear in it."""

    def annotation_response(self, result: Sequence[Mapping[str, Any]],
                            record: Record) -> AnnotationResponse:
        """What one annotation said: its verdict, its correction where it validates, its note.

        The inverse of the capture half, and the whole of it — the half emits three controls, so
        its inverse answers for three. **The only place an annotation tool's shape is read**
        (Requirement 49), the way `build_record` is the only place a source shape is read."""

    def jury_slots(self, record: Record) -> Mapping[str, Any]:
        """What the jury prompt's slots are filled with. The template is policy's, not this."""

    def scenario_hash(self, record: Record) -> str:
        """What must not straddle a split — two records of one scenario share it."""

    def training_example(self, record: Record) -> Mapping[str, Any]:
        """The record in the shape a trainer expects."""
```

Fifteen members, closed. `Answer`, `AnswerConfig` and `LabelCheck` are opaque here; the pydantic models
behind them are `tool_decision/schema.py`, and `answer_schema` — the conversion that materialises one —
is `tool_decision/answers.py`. `AnnotationResponse` is the exception and is **concrete** in
`profiles/base.py`: a verdict, a correction and a note are the same three things for every profile
there could be, and only the correction is the profile's own vocabulary — which is why it alone is
typed `Answer`. `ports.JurorAnswer` is the same shape of value on the other side of the engine.

**`build_record` is the only place a source shape is *validated*, and not the only place one is
read.** `content_parts` reads `messages`, and inside a turn `role` and `content` — it has to, because
turns are content and reading content is what a modality is for. **The task's own vocabulary inside a
turn is the profile's**: a turn may also carry `tool_calls`, and what a call is is the whole of what
`tool_decision` declares, so that profile overrides the turn its concept writes and reads `tool_calls`
and a call's `function` and `arguments` there. A concept holds no key only one of its modules can
read. What the profile owns is every other key *and the `shape:` declaration itself*: it is the only
side that refuses an undeclared shape, and the modality assumes a chat item unconditionally. So the
declared input spans both axes with one end unvalidated, and since neither axis may hold the other's
vocabulary there is nowhere to move the check to.

**Provenance is a parameter and not a key on the item.** It was ``item["__provenance__"]`` for one
phase -- ``load_data`` put the file's digest, the offset, the clock and the run there, and this member
validated them on the way in. That is connascence of meaning between a stage and one axis, and
it cost two ``ConfigError`` branches to police. As a third argument the case *an item with no
provenance* cannot be spelled, so both branches are gone rather than caught: the cheapest error is
the one the interface makes unrepresentable.

#### The answer, and the three operations over it

**An answer is a set of calls.** A call is a tool's name *and* its arguments, because `SendStatement`
alone cannot distinguish `ky: "thang_nay"` from `ky: "thang_truoc"`, and a dataset that cannot
distinguish them teaches a model that the argument does not matter. The empty answer — call nothing —
is a member of the type, not a missing value. **At most one call per tool name:** two calls to one tool
make the answer a multiset and force δ to pairwise-match them silently, so `label_names_one_tool_twice`
quarantines instead. **A bare name string reads as the call with no arguments**, which is what makes a
names-only source a special case of this type rather than a second type.

**`answer_schema(record)` is `oneOf` per offered tool** — the name a single-value `const`, the arguments
that tool's own `parameters`, constrained *together*. `OpenTicket` carrying `LookupBalance`'s argument
is two valid halves and one invalid call, which an `enum` of names beside a free-form object cannot
say. An empty catalog materialises `maxItems: 0`: there was nothing to choose from, so the empty answer
is the only valid one.

**δ is name-first and soft.** Over the union of names: a name in both contributes the share of argument
keys present in both and equal; a name in one contributes zero; δ is one minus the mean. Argument
agreement is over the **union** of keys, never the left side — `len(shared) / len(left)` would call a
one-argument call a perfect match for the same call carrying five. `δ(∅, ∅) = 0` by definition, and
that is load-bearing rather than tidy: the empty answer is a large share of a real corpus, and a δ that
returns `NaN` there takes every cohesion figure, every bucket and every α with it.

Hand-worked, and asserted as an **ordering** rather than three separate numbers:

```text
δ(same call) = 0  <  δ(same tool, one of two arguments differs) = 0.5  <  δ(different tools) = 1
```

**The reduction is exact, not approximate.** With every matched call argument-less, each argument
agreement is 1 and the expression collapses to `1 − |A∩B| / |A∪B|` — plain Jaccard over names. Every
number measured before arguments existed still describes this δ, and a names-only source is the special
case rather than a different formula.

**`vote_consensus(votes, record)` is per name, then per argument.** It takes the record because
`required` is the tool's own declaration and nothing else can answer it:

1. If a strict majority of *all* votes is the empty answer, the consensus **is** the empty answer.
2. Otherwise a name is in when a strict majority of *all* votes included it.
3. Each of that call's argument keys takes the value a strict majority of the votes **naming that
   tool** gave — naming it, not voting at all, because a juror who did not call the tool has no opinion
   about its arguments. Values are compared through canonical JSON, because an argument may itself be
   an object or an array.
4. A key with no majority is absent. A call missing a key the tool declares `required` is **dropped,
   not completed**: half-building one puts a value no juror proposed into a ranking signal, and it
   would fail this record's own `answer_schema`.
5. If no call survives, the result is `None`.

Step 1 is what keeps `[]` and `None` apart. `[]` is returned only when a majority voted for it, so *the
panel agreed to call nothing* and *the panel produced nothing defensible* are two values rather than one
value read two ways. A consensus answer validates against the record's `answer_schema`, asserted
directly.

The two contracts share three names and nothing else: `name`, `version` and `Part` — the last is the
record's and is only borrowed by both. **How a turn that both speaks and acts is written down is not
one of them.** A part carries one string, so the calls a turn made are joined onto the text it spoke;
the profile that declares what a call *is* is the one that writes them there and the one that reads
them back, so the separator between the two is that profile's own constant, and one test writes a
turn through it and reads the calls back off the part so neither end can move alone. A concept cannot
hold a convention only one of its modules speaks. Neither axis may drift into the other's job.

**That sentence is about the two *contracts*, and not about the two modules.** The implementations
share more than three names — `Manifest`, `ConfigError`, `Record`, and by § *The two axes* the concept's
own class, which `ToolDecision` subclasses. Reading *and nothing else* as a rule about imports buys a
second copy of the manifest reader and a third of the canonical JSON form, each with a docstring
citing this line as its reason. What a module both axes import may not do is carry one axis's
vocabulary — which is a property of its signature, checked by I25, and not of how many axes reach it.

---

## The surface: four main endpoints, and the services under them

**A main endpoint is a phase; a sub-endpoint is one service.** `POST /data-quality` runs that phase's
three services in flow order over the posted records. `POST /data-quality/pii-check` runs exactly one.
Both take and return the same body, so they compose.

### The flow

`src/dataforce/pipeline/flow.py` is the one place this table exists in code.

| phase | stage | what it does |
|---|---|---|
| load_data | `load_data` | every source item becomes one record with identity, content and provenance |
| data_quality | `label_check` | the five checks on the label that need no opinion |
| data_quality | `pii_check` | two-layer detection, typed placeholders, `content` rewritten |
| data_quality | `duplicate_check` | exact and near-duplicate groups, split by label agreement |
| ai_review | `jury` | N independent models answer the record's own task |
| ai_review | `cohesion` | how much the jury agrees with itself, and with the existing label |
| ai_review | `triage` | the two numbers become a bucket, a stratum and a review quota |
| human_review | `question_generate` | one answerable question per flagged record, with its evidence |
| human_review | `publish` | questions written to the question store, ready for the annotation tool |
| human_review | `annotator_answers` | responses read back out of the store onto the record |
| human_review | `aggregate` | overlap becomes one verdict with a confidence and an agreement statistic |
| human_review | `curate` | the verdict becomes the record's final label, or an adjudication |
| release | `split` | train / validation / test, with no scenario on both sides |
| release | `export` | the trainer-shaped artifact, per profile |
| release | `datasheet` | one document stating how the dataset was made |

**A stage has a name, not a number.** Order is the order of these rows and nothing else states it:
`STAGES` in `flow.py` is a tuple, and a tuple already knows its order. Inserting a stage costs one row
here and one row there and renumbers nothing, because there is nothing to renumber — § *The flow* says
what that buys and what it costs.

**Declared, not built: `release`.** Its three stages are in the table so the flow is complete and the
record's `release` key has an owner; they are specified in a follow-up — see *Out of Scope*. Every other
stage in the table has a module. Scope is a named phase rather than a cut at a number for the same
reason: a cut moves when anything above it moves.

**`load_data`, not `load`.** AGENTS.md forbids a bare operation that names no object: *load what?* The
stage reads a source item and returns record data, and its name says so.

**`label_check`, not `validity`.** "Validity" names no object and no defect — everything in the pipeline
is a validity check of something. These five check **the label**, against the record's own catalog and
its own turns, and the name says which thing is being checked. It also makes the phase read as one
family: `label_check`, `pii_check`, `duplicate_check`.

### Routes

Kebab-case, matching the style reference.

```
POST /load-data                          -> LoadDataResponse
POST /data-quality                       -> RecordsResponse   # label_check -> pii_check -> duplicate_check
POST /data-quality/label-check           -> RecordsResponse
POST /data-quality/pii-check             -> RecordsResponse
POST /data-quality/duplicate-check       -> RecordsResponse
POST /ai-review                          -> RecordsResponse   # jury -> cohesion -> triage
POST /ai-review/jury                     -> RecordsResponse
POST /ai-review/cohesion                 -> RecordsResponse
POST /ai-review/triage                   -> RecordsResponse
POST /human-review                       -> RecordsResponse   # question_generate -> publish
POST /human-review/question-generate     -> RecordsResponse
POST /human-review/publish               -> RecordsResponse
POST /human-review/annotator-answers     -> RecordsResponse
POST /human-review/aggregate             -> RecordsResponse
POST /human-review/curate                -> RecordsResponse

POST /human-review/publish/sync          -> SyncResponse      # not a record-bus service
GET  /branches                           -> registered modalities and profiles, with versions
GET  /healthz                            -> liveness; no engine, no store
```

`POST /human-review` stops after `publish` on purpose: `annotator_answers`, `aggregate` and `curate`
cannot run until people have answered, so a phase endpoint that ran all five would either block or
silently produce empty verdicts.

---

## Requirements

Each is a statement a test can be pointed at.

### Code shape

1. **Every field of every data class carries a one-line description of what the key is and what it is
   used for**, in the code: `Field(..., description="…")` on a pydantic model, a trailing comment on a
   plain dataclass attribute. Related fields are grouped under `# --- Section ---` comments. This is not
   decoration — for a request or response model it is the OpenAPI text a caller reads, and for the
   record it is the only place a key's meaning is written down next to the key.
2. Every module opens with a docstring whose first word declares its kind: `DEFINITION ·` one noun and
   its shape, `LOGIC ·` conversions over that noun, `STEP ·` serves exactly one stage of the flow,
   `TOOL ·` not in the flow at all. A fifth word, `façade ·`, marks an `__init__.py` that re-exports and
   holds nothing of its own: none of the four describes a module with no content, and § *Package layout*
   below already writes it over `pipeline/__init__.py`. AGENTS.md — the break is recorded rather than
   resolved silently, here and in the top-level package docstring.
3. A service module's docstring is its row of the flow table — `STEP · <stage> · <what it does>`, with
   the stage name and the summary matching § *The flow* word for word. I3 compares them. There is no
   number in it: see § *The flow*.
4. A name states what it returns, not the operation that produced it, and no function shares a name
   with a stage.

### The record

5. Every service reads records and returns records. A service adds **exactly one key** and changes
   nothing else — except `pii_check`, which also rewrites `content` **and the `label`** together and
   bumps `content_version` (Requirement 17). Three paths besides its own key, not two: this sentence
   said `content` and `content_version` until T16, and rewriting one of the pair and not the other is
   the defect Requirement 17 is written about.
6. `record_id` is 16 lowercase hex over the canonicalised `content` parts. It does not depend on the
   record's position in the source file, and a shuffled re-ingest produces the same set of ids.
7. Order *within* a record is content; order *between* records is not.
8. A media part contributes its `sha256`, never its bytes, to `record_id`. Moving a file does not change
   an id; changing its content does.
9. `meta` is kept **verbatim**. Every key-set the source presents survives load unchanged, including
   keys no code recognises — what looks like noise now is what a later question turns out to need.
10. No record stores an answer space. `Record` has no such field, and constructing one with it raises.
11. Every key a service writes is written by exactly one service. The per-phase `<phase>_config` key is
    the single exception and is written by the **edge**, never by a service.
12. A record carries `provenance` written by `load_data`: source digest, offset, ingest time, both axis
    versions, and the run id.

### load_data

13. The input is one shape: standard OpenAI chat-completion records with `tools` carried as data. A
    record with no `tools` key is an **empty catalog**, which is a quarantine for triage — not an
    invitation to parse a catalog out of the prose.
14. Which key holds the answer is **declared**, not assumed: the manifest's `label.at` names it, so a
    source calling it `target` or `gold` needs a manifest line and no code. An undeclared key raises,
    naming the manifest and what *is* declared.
15. One tool call spelled three ways — arguments as a JSON string, the same string with keys reordered
    and whitespace added, and the object form — is one part and one `record_id`.
16. Text content is loaded byte-identical to the source; no normalisation at load. For a media modality,
    `load_data` resolves each item's URI through a resolver **that the media modality declares when it
    is built**, records `uri` + `sha256` + modality metadata, and never opens a file from engine code. A
    media part without a reference cannot be constructed. No such port is declared today, because no
    media modality exists to demand one: a port with no adapter is a guess about a caller that has
    not arrived, and the seam is the protocol, not the unused type.

### data_quality

17. `pii_check` replaces detected values with **stable typed placeholders** scoped per record
    (`<OTP_1>`), never deletes them, and a value used twice keeps one placeholder.
    **Content and label are rewritten together.** A value found in `content` is replaced everywhere it
    also appears in `label`, through the profile's `redact_label(label, replacements)`, under the same
    placeholder. Redacting one and not the other is worse than redacting neither: it manufactures a
    `label_assistant_mismatch` failure downstream, and `export` emits a training example whose input
    reads `<OTP_1>` and whose target reads the original value — teaching a model to produce an
    identifier that is absent from its input. That is a data-poisoning defect wearing a privacy
    defect's clothes, and it is why this is one requirement and not two.
18. Detection runs two layers: `agent-toolkit`'s rule-based scans, one per class of personal data,
    tuned for recall (and permitted to be noisy), then a model pass over a bounded window that sets
    precision. Every scan finds the written form **and** the form a speaker dictates, and every
    pattern behind one holds the toned and the tone-stripped spelling together, so `khong chin` and
    `không chín` are one scan over the raw text and no second pass has to keep an offset through a
    normalisation.
19. Spans are recorded against the content they were found in — `content_version` *before* the rewrite —
    and each names `part`, `start`, `end`, `class`, `verified`, `placeholder`.
20. The placeholder→original map is returned to the edge, written outside version control, and read by
    no service.
21. With `enable_redact: false` (the default), `pii_check` reports and leaves `content` untouched; the
    downstream personal-data scan then fails, so nothing ships. Turning it on is an edit to
    `params.yaml`, which makes the decision attributable.
22. `label_check` runs the five declared checks, and each check's count is compared against
    `params.invalid_counts[<check>]`. Those numbers are populated by
    the first run over a declared source, and the comparison is a line in `metrics.json` — a number a
    human reads in a diff, not a stop.
23. `duplicate_check` reports two groups per record: `duplicate_content_same_label` and
    `duplicate_content_diff_label`. Near-duplicates use the modality's `embedding`, which the
    deployment attaches rather than the run downloading: two runs give identical groups for as long as
    that endpoint serves the same weights under the name `embedding.model` records. The run manifest
    carries the name, and cannot say which weights answered to it — which is the whole of what was
    given up when a static model was replaced by a hosted one that is better on this corpus and is
    already running. **Two records are compared for near-duplication only where they
    pose the same task** — the same `scenario_hash` — because two identical prompts offering different
    tools are not duplicates *for this task*: the answer space differs, so a model choosing between
    them is being asked two different questions. An *exact*-content pair is compared regardless, since
    `record_id` is over content alone and a shared one is already a fact about the corpus.

### ai_review

24. `jury` records one vote per model: the model name, whether the existing label is right, the model's
    own answer, and its reasoning. A vote whose answer is not in the record's answer space is an
    **invalid vote**, counted and never silently dropped. *In the answer space* is the profile's
    `answer_is_permitted` and not the materialised schema alone, because a schema cannot say *at most
    one call per tool name* and `vote_consensus` already refuses an answer on that ground — two
    readings of *valid* on one record is how `invalid_votes: 0` comes to sit beside a null
    `final_prediction`.
25. `cohesion` computes two numbers and makes no model call: agreement of the jury with itself, and
    agreement of the jury with the existing label. Re-running it costs nothing.
26. `triage` turns those numbers into a bucket, a stratum and a quota using thresholds from
    `params.thresholds.triage`. Re-tuning thresholds re-runs `triage` alone (§ *ai_review*).
27. Thresholds live in configuration. The triage logic contains no numeric literal other than `0` and
    a display cap, so changing a bucket boundary is a committed, attributable edit to `params.yaml`
    whose digest the run manifest records.
28. No jury call is made to an offshore endpoint unless the cross-border data-transfer review is
    recorded in the declared policy. This one is a precondition on opening the engine, not on a
    record: it is checked once at composition and raises `ConfigError`, because it is a fact about the
    configuration rather than about any record.

### human_review

29. `question_generate` produces one question at a time about one record, carrying the evidence and the
    glossary, with an enumerated answer set. Answering *incorrect* requires the corrected value.
30. **No model output may reach an annotator.** The generated annotation config and question payload
    contain no vote, no cohesion number, no bucket.
31. **The annotation config is composed in the Label Studio adapter, and no modality emits markup.**
    `edge/label_studio.py` builds the display fragment from the record's own parts — a `Part` carries
    `role` and `text` — and encloses the profile's capture half unchanged. The tool's config grammar is
    written in that one module, so adding a modality adds no page layout and the capture half stays the
    only fragment an axis owns.
32. `publish` writes questions to the question store through a port supplied at the edge and records the
    receipt on the record. It does not talk to Label Studio.
33. `annotator_answers` reads responses out of the store. It does not talk to Label Studio either.
34. `aggregate` produces one verdict per record with a method name, a confidence, and the overlap it was
    computed from; incomplete overlap uses Krippendorff's α.
35. `curate` writes the final label with `status`, the validators who produced it, and — where they
    disagreed — who adjudicated.

### Running it

36. No engine module opens a file, names a path, or imports the edge. `edge/` **is** the edge — both
    shells live in it, so the rule is one condition and not a list; **everything else is the engine**, and the arrow points one way. `Engine` is a type the engine owns;
    `open_engine`, which reads the files that fill it, is not.
37. Importing `dataforce.modalities.text2text` and `dataforce.profiles.tool_decision` from a directory
    holding no `config/` succeeds and writes nothing.
38. No module under `pipeline/` imports a concrete modality or profile, and **nothing above an
    implementation names one** — neither an axis's `base.py` nor its `__init__.py`. Importing the
    protocol never drags an implementation in behind it. Both axes arrive through a registry, and
    `edge/bootstrap.py` is the only module that names one.
39. A registry is instance state. Two registries in one process hold different implementations, and
    registering a second implementation of one name is refused.
40. Identity is never assigned in a class body. `name`, `version` and `modality` come from
    `config/<axis>/<name>.yaml`, whose **filename is its identity**, and `version` must be a string.
41. **No stage removes a record.** Quarantine is a value on the record, deduplication is a group
    annotation, and a rejected record travels the whole flow carrying why. `output == input` at every
    stage, structurally — not asserted, because there is nothing to assert against.
42. **A service states its preconditions as the upstream keys it requires, and reads them off the
    record.** `pii_check` requires `data_quality.label_check`; `export` requires
    `data_quality.pii_check.decision == "redacted"`. A record that does not satisfy a precondition is
    skipped and marked, never dropped and never a reason to stop the run.
43. **A run always completes.** What went wrong is on the records and in the run's metrics; nothing
    halts a batch of 20,000 because 3 records are bad. The only exceptions raised are `ConfigError` —
    a declaration that is wrong or missing, raised before any record is read.
44. Corpus-level numbers are a **fold at the edge, for reading** — written to `metrics.json` by
    `edge/artifacts.py`, never computed by a service and never compared against a threshold that stops
    anything. A count that has moved is something a human sees in a diff, not a crash.
45. A run records every policy file it read with its digest, both axis versions, and every artifact
    digest. Two runs of one unchanged configuration produce byte-identical run manifests; a changed
    policy file changes the manifest.
46. HTTP and an in-process caller reach the same function, and produce the same record.
47. **A type named in an axis protocol is opaque at the base and concrete in the implementation.**
    `Answer`, `AnswerConfig` and `LabelCheck` are aliases in `profiles/base.py`; `Detector` is the
    alias in `modalities/base.py`; the pydantic models that satisfy them live in
    that axis implementation's `schema.py`. **`Answer` is the one whose satisfying model is a
    composite:** `tool_decision/schema.py` holds `Call`, and an answer is a set of them — what
    *crosses* the boundary is `record.StoredAnswer`, because a stage hands `record.label` straight to
    `answer_distance` and may not import the implementation (I2). So the implementation names the
    parsed form `Calls` and not `Answer`: a second `Answer` inside the axis made one word mean two
    shapes, and a reader following this requirement got the wrong type for all four operations. Neither `base.py` imports a concrete implementation. `Part`
    belongs to neither axis — it is a piece of record content — so it is defined in `record.py`, which
    both protocols may import.
48. **The order of a phase's stages is engine knowledge.** `POST /data-quality` runs three services in
    the order `pipeline/flow.py` declares, folded by `pipeline/runner.py`. No router names a stage
    sequence, and `edge/cli.py` dispatches over the same table rather than hand-writing one subcommand body
    per stage.
49. **`annotation_response` is the only place an annotation tool's shape is read**, the way
    `build_record` is the only place a source shape is read. It takes one annotation's `result` list and
    the record, and returns the verdict, the corrected value — which validates against that record's
    `answer_schema` or is `None` — and the note. A corrected value that does not validate is never
    coerced, and what the person actually typed is kept verbatim in the store's `result`: the same
    treatment `jury` gives an invalid vote, and for the same reason. **The record carries the
    conclusion and not the attempt** — `AnnotatorResponse` has no `valid` beside its
    `corrected_value`, so *tried and failed* and *did not try* read alike on the bus and are told
    apart in the store. It answers for all three controls because a caller reading one of them
    itself would be a second reader of this shape, and the caller is a pipeline stage.
50. **A skip is not an answer and not a missing row.** Label Studio's `was_cancelled` is stored as
    `was_skipped`, counted, and excluded from `aggregate`'s overlap. An annotator declining a question
    is evidence about that question.
51. **The jury's task statement is a policy file, filled by the profile.** The template lives in
    `config/prompts/` so its digest reaches the run manifest (Requirement 45); the profile supplies the
    values through `jury_slots(record)` and `agent-toolkit`'s `slot_filling` does the filling. Prompt
    text in code is a prompt change no manifest records.
52. **The composed annotation config uses only community-edition tags.** `<Chat>` renders a
    conversation the way a chat corpus wants and is Enterprise-only, so `edge/label_studio.py` emits
    `<Paragraphs layout="dialogue">`. A per-record catalog is a dynamic choice list, because a project
    has one config for every task.


---

## Design

### Repository layout

Every entry at the root, and the job it holds. A directory whose job is not written down is a directory
the next person guesses at, and a guess is how one acquires a second place to put things.

| Entry | What it holds, and why it is its own thing |
|---|---|
| `src/dataforce/` | The package, drawn module by module in § *Package layout* below. A `src/` layout, so a test imports the installed package and not the working tree: the thing under test is the thing that ships |
| `tests/` | Five directories, one per kind of check — § *Testing Strategy* says what each proves. Outside the package, so nothing that ships can reach a fixture |
| `docs/annotation-pipeline/` | `objective.md` — why, and what one record looks like · `spec.md` — this file, what to build · `plan.md` — the order to build it in · `workflow.md` — how a run is driven end to end |
| `config/` | What a run declares. `modalities/<name>.yaml` and `profiles/<name>.yaml` each carry an axis's identity in the filename, so it is not assigned anywhere else; `prompts/<axis>/<name>/<file>.vN.txt` holds every template a service sends to a model, versioned in the filename so a digest reaches the run manifest. § *Configuration* |
| `config/templates/` | Nothing, and nothing references it. An empty directory is the flexibility nobody asked for that AGENTS.md forbids; it goes with the next task that touches `config/`. Recorded here rather than left to be found |
| `params.yaml` | Every threshold the pipeline reads at runtime. Code holds none: a number here is committed, reviewable and recorded by digest in the run manifest, so a change to it is attributable and a run that used the old value stays identifiable |
| `data/` | What a run writes: `raw/` the source, then `interim/`, `processed/`, `release/`, `quarantine/`, and `run.json` — one run, one manifest, at the root of what it wrote. **Committed: none of it.** `raw/` is the privacy tier (I13) and the rest are artifacts the manifest identifies by digest. Ignored tier by tier rather than as `data/`, so one tier can be un-ignored on its own |
| `deploy/` | `docker-compose.yml` — Label Studio 1.23.0, pinned because the sync is written against a release. Optional: it is the one endpoint that needs an instance, and no credential is in the file. The project itself is created by a person, because a project's settings *are* the rung |
| `AGENTS.md` | The conventions and design principles this repository is held to. A rule cited in a review or a commit message resolves here |
| `README.md` | The front door: what this repository is, which spec to read first, and the build order across all of them |
| `Makefile` | `make check` — ruff, `mypy --strict`, pytest without `-m integration`. What CI runs and what must pass before a commit. `make integration` is the half that needs a network |
| `pyproject.toml` | Dependencies, package metadata, and the configuration for every tool `make check` runs, in one file rather than four dotfiles |
| `uv.lock` | The resolved versions, so two machines install the same tree |
| `.python-version` | The interpreter `uv` picks when told nothing |
| `alembic.ini` | Three lines: where the migrations are and how one path is split. No DSN — `migrations/env.py` reads `DATAFORCE_DATABASE_URL` through `edge/store/session.py`, and the placeholder Alembic generates is a credential-shaped line in a public repository. No logging config either; `edge/observability.py` owns that |
| `migrations/` | The store's schema, one revision at a time, and `env.py` — the only module outside `src/` that imports the package. Outside it because a migration is not part of what ships; it is the tool that moves a database from one version of what ships to the next |
| `.github/workflows/ci.yml` | `make check` on every push. The file does not do that yet — it still runs a `dvc repro` step for a tool that was deleted, and imports a module that was renamed; both are Phase 0 residue, and `plan.md` T34 carries the fix |
| `.gitignore` | The privacy tier and the artifact tiers, each with the reason it is listed |

### Package layout

`core/` is gone. It held five things and only `errors.py` earned the package: `artifacts/` was the
previous design's per-phase file shapes, and `record.py` and `manifest.py` are used by every layer —
which makes them the package's own top level, not a sub-package. A package with one useful module is
that module. `flow.py` comes back, not because the test that read it comes back, but
because a deleted test is no verdict on a module.

**The edge is called `edge/`.** It was called `api/`, which was a lie: the package also held
`policy.py`, `artifacts.py` and `store/` — every file, socket and clock in the system — and `cli.py`
importing from something named `api` was the proof. "Edge" is the word this document already reasons
in. HTTP keeps the style reference's shape inside it, and `cli.py` is **in** it: the same argument that
renamed the package puts the second shell inside it rather than beside it (§ *Package layout*).

**`Engine` is a type; `open_engine` is a reader.** Putting both at the edge forced every service —
`def pii_check(engine: Engine, …)` — to import the edge, which Requirement 36 forbids and I1 catches on
the first run. The abstraction belongs to the inner layer, so `Engine` and `Registry` are
`dataforce/engine.py`, holding a resolved pair and no I/O; the composition root that reads config to
build one is `edge/bootstrap.py`. `ports.py` moves for the same reason: `QuestionStore` is what the
*engine* demands of the edge, so an adapter cannot be where it is declared. It named three and held
one when that sentence was written, because a port with no adapter is a guess about a future caller —
a port with no adapter is deleted rather than kept as a placeholder. It holds three now, and each arrived with what made it real: `PersonalDataVerifier`
with `pii_check`, `JuryPanel` with `jury`, and `QuestionStore` with its adapter and its three tables
in T23. That last one is the exception the rule allows: its two members are what `publish` and
`annotator_answers` demand, and neither stage exists yet — what it has instead of a caller is an
adapter that is exercised, which is the half a guess never has.

```
src/dataforce/              the package; its docstring states the import direction and the five module kinds
  __init__.py               DataForce — a raw, model-labelled corpus into a training-ready dataset, and the evidence for it.
  errors.py                 DEFINITION · ConfigError — the one exception this codebase defines.
  record.py                 DEFINITION · Record, and Part — the bus, and the content it carries.
  manifest.py               DEFINITION · Manifest — one axis's declaration, already parsed.
  declarations.py           LOGIC · the manifest declarations an axis reads, checked where they are read.
  engine.py                 DEFINITION · Engine, Registry and ServiceResult — what a service takes and returns; no I/O.
  ports.py                  DEFINITION · QuestionStore, PersonalDataVerifier and JuryPanel — what the engine demands of the edge.

  pipeline/                 the flow: one module per stage, and the fold that runs a phase's stages in order
    __init__.py             façade · the flow's table, its fold, and the phases under it; holds nothing of its own.
    flow.py                 DEFINITION · PHASES and STAGES — the flow table, in code, once.
    runner.py               LOGIC · run_phase — a phase's stages folded over records, in the table's order.
    params.py               LOGIC · the params.yaml declarations a stage reads, checked where they are read.
    load_data.py            STEP · load_data · every source item becomes one record with identity, content and provenance.

    data_quality/           three stages, so a directory rather than a module
      __init__.py           façade · the data_quality phase's three stages; holds nothing of its own.
      label_check.py        STEP · label_check · the five checks on the label that need no opinion.
      pii_check.py          STEP · pii_check · two-layer detection, typed placeholders, `content` rewritten.
      duplicate_check.py    STEP · duplicate_check · exact and near-duplicate groups, split by label agreement.

    ai_review/              three stages (§ *ai_review*)
      __init__.py           façade · the ai_review phase's three stages; holds nothing of its own.
      jury.py               STEP · jury · N independent models answer the record's own task.
      cohesion.py           STEP · cohesion · how much the jury agrees with itself, and with the existing label.
      triage.py             STEP · triage · the two numbers become a bucket, a stratum and a review quota.

    human_review/           five stages, of which the phase endpoint runs the first two
      __init__.py           façade · the human_review phase's five stages; holds nothing of its own.
      question_generate.py  STEP · question_generate · one answerable question per flagged record, with its evidence.
      publish.py            STEP · publish · questions written to the question store, ready for the annotation tool.
      annotator_answers.py  STEP · annotator_answers · responses read back out of the store onto the record.
      aggregate.py          STEP · aggregate · overlap becomes one verdict with a confidence and an agreement statistic.
      curate.py             STEP · curate · the verdict becomes the record's final label, or an adjudication.

  modalities/               one directory per implementation, beside the protocol they answer
    __init__.py             façade · the modality axis: the protocol, and nothing that implements it.
    base.py                 DEFINITION · the Modality protocol; Detector, opaque.

    text2text/              the only modality built; *Out of Scope* says why there is no empty `speech2text/`
      __init__.py           façade · the text2text modality; the object a composition root registers, and the encoder it is built with.
      schema.py             DEFINITION · the text2text shape: what a detector is.
      pii_detector.py       LOGIC · layer one for the declared language: one library scan per class of personal data.
      text_embeddor.py      LOGIC · the document one vector is taken over, and the name of the model that takes it.
      modality.py           LOGIC · Text2Text — the object that answers the Modality protocol, and the turn it reads.

  profiles/                 the same shape as `modalities/`, and nothing shared between the two axes
    __init__.py             façade · the profile axis: the protocol, and nothing that implements it.
    base.py                 DEFINITION · the Profile protocol; Answer, AnswerConfig and LabelCheck, opaque.

    tool_decision/          the only profile built; the first dataset's task
      __init__.py           façade · the tool_decision profile; the object a composition root registers.
      schema.py             DEFINITION · the tool_decision shapes: a call, an answer, and what constrains one.
      answers.py            LOGIC · the answer space, and the three operations over an answer: distance, permitted, consensus.
      annotations.py        LOGIC · what one annotation said, decoded from the controls the capture half emitted.
      records.py            LOGIC · the answer a record carries: the one that ships, the one its turns restate, the redacted one.
      profile.py            LOGIC · ToolDecision — the object that answers the Profile protocol.

  edge/                     everything that touches a file, a socket or a clock (Requirement 36)
    __init__.py             façade · the edge: everything that touches a file, a socket or a clock.
    main.py                 TOOL · create_app(), CORS, one include_router per main endpoint.
    bootstrap.py            LOGIC · open_engine — the composition root; the only builder of an Engine.
    policy.py               LOGIC · config/<axis>/*.yaml, params.yaml and prompts into declarations.
    artifacts.py            TOOL · the one place a record file, metrics.json or a run manifest is read or written.
    observability.py        TOOL · the stdout handler, and the three keys every event carries.
    label_studio.py         TOOL · the Label Studio adapter: the config it composes, questions out, annotations back, idempotent in both directions.

    routers/                one router per main endpoint; a package only where that endpoint has models of its own
      __init__.py           façade · one router per main endpoint, and the body three of them share.
      schemas.py            DEFINITION · RecordsRequest and RecordsResponse — the body every record route shares.
      data_quality.py       TOOL · one APIRouter for /data-quality: the main endpoint, and one sub-endpoint per service.
      ai_review.py          TOOL · one APIRouter for /ai-review: the main endpoint, and one sub-endpoint per service.

      load_data/            a package, because this endpoint has models nothing else speaks
        __init__.py         façade · the /load-data router and the two models only it speaks.
        router.py           TOOL · one APIRouter for /load-data: one service, so one route and nothing under it.
        schemas.py          DEFINITION · LoadDataRequest and LoadDataResponse — the one route the modality reshapes.

      human_review/         a package, for the same reason: `/publish/sync` is not a record route
        __init__.py         façade · the /human-review router and the one model only it speaks.
        router.py           TOOL · one APIRouter for /human-review: the main endpoint, and one sub-endpoint per service.
        schemas.py          DEFINITION · SyncResponse — the one model /human-review adds to the shared body.

    store/                  the question store's adapter: SQLite by default, Postgres by URL (§ *The question store*)
      __init__.py           façade · the question store: the adapter behind the QuestionStore port.
      models.py             DEFINITION · the store's rows: what a published question and a returned answer look like.
      repository.py         LOGIC · the QuestionStore adapter, over a SQLAlchemy session.
      session.py            TOOL · the store's connection and its lifetime.

    cli.py                  TOOL · one subcommand per stage, dispatched over the flow table; JSONL in, JSONL out.
```

Every module above states its own kind (Requirement 2), and the line beside it in this drawing *is* that
module's docstring — not a second description that can drift from it. I19 compares the two, in both
directions, so a module added without a row and a row left behind after a rename each fail the build.

The test suite mirrors it:

```
tests/
  guards/            the architectural rules, written before any service, each proved against a violation
  stages/            one module per stage: its reads, its writes, the records it skips
  properties/        I8 and I11 together, over one corpus, through every built service
  shells/            I15: the same input in-process and over HTTP
  integration/       -m integration: a live panel, a real store, a declared corpus
```

A phase with one stage is one module (`load_data.py`); a phase with several is a directory. Nothing is
split until a second consumer needs half of it.

**A router is a package only when it has models of its own.** Every route but `/load-data` takes
records and returns records, so `RecordsRequest` and `RecordsResponse` are one module —
`routers/schemas.py` — and not four copies of one shape (§ *Request and response models*). `load_data/` and `human_review/`
stay packages because each speaks something no other router does; `data_quality` and `ai_review` speak
nothing of their own and are one module each, which is AGENTS.md's rule and the same rule `pipeline/`
already runs on. The cost is stated: giving `ai_review` a model of its own later promotes a module to a
package. That is one `git mv` and it is visible in review, which is cheaper than three copies of a
shape that must stay identical.

**`edge/cli.py` is a dispatch over `flow.py`**, not one hand-written subcommand body per stage: every
service has one signature and Requirement 46 makes the in-process call the same call, so the CLI stays
roughly one screen however many stages exist. `record.py` does not split at all — there is no boundary
in it; it is one type, and it is long because
Requirement 1 puts a description on every field, which is the file doing its job.

**There is no empty `speech2text/` directory.** The seam is real and specified — `modalities/base.py`,
the media part shape, and the pair naming — and a directory holding nothing adds none of it, which
is the flexibility-nobody-asked-for that AGENTS.md forbids. What is out of scope is listed in *Out of
Scope*, not mimed in the tree.

Every implementation of either axis has a `schema.py` (`DEFINITION ·`) that imports nothing from its
own package, an `__init__.py` that holds nothing of its own, and modules named for what they produce.
A shape is a shape and a conversion over it is logic — they change for different reasons, so the
dependency runs one way and never back. So `answer_schema` — a record turned into a JSON Schema — is
logic, while the answer models it constrains are `schema.py`.

**The file list is not fixed.** I4 constrains the direction of an import and not the number of
files: a guard that required exactly three modules would make AGENTS.md's own remedy — a `utils.py`
that has outgrown its exemption gets a real name — a build failure, and a rule that forbids its own
remedy sends every later addition into `utils.py`. `utils.py` is the one module name AGENTS.md
exempts by name, under exactly one condition — conversions over the shapes in the `schema.py` beside
it — and I4's second half is that condition. Neither package has one: `text2text/` is
`pii_detector.py`, `text_embeddor.py` and `modality.py`, and `tool_decision/` is `answers.py`,
`annotations.py`, `records.py` and `profile.py`.

**An axis façade re-exports its protocol and nothing else.** `dataforce/modalities/__init__.py` holds
`Modality` and not `text2text`. Re-exporting the implementation would make `import dataforce.modalities`
load it, so a stage that imports only the protocol would pull a concrete axis in behind it and I2 —
which reads the stage's imports — would see a clean line. The registry would still be there and would
no longer be the only way in. `edge/bootstrap.py` names the implementations, because registering them
is what a composition root is for (Requirement 38, I16).

**Import direction, stated once in the package docstring:** `edge/` may import the engine; the engine
may not import it. One package, one direction, one condition in the scan.

### The record

The bus. **Every key carries its meaning next to it** — Requirement 1, applied to the record itself.
This corrects `objective.md` §3's illustrative JSON, which uses Python `True`, leaves several values as
prose, and nests `human_review` inside `ai_review`.

```jsonc
{
  // --- Identity ---
  "record_id":  "3f9a1c0b7e4d2856",   // 16 hex over canonicalised content; the join key everywhere
  "source_id":  "s4471",              // the id the source gave this item; for tracing back, never for joining
  "branch":     { "modality": "text2text",      // which pair read this record's content
                  "profile":  "tool_decision" },// which task defines its answer

  // --- Provenance: what made this record, travelling with it ---
  "provenance": { "source_file_sha256": "a1b2c3d4…",          // which file, by content, not by name
                  "offset": 4471,                             // position in that file, for re-reading one item
                  "ingested_at": "2026-08-22T00:00:00Z",      // when load_data ran
                  "modality": "text2text@1",                  // stamped pair version; a bump is visible per record
                  "profile":  "tool_decision@1",
                  "run_id":   "r_2026-08-22T00:00:00Z_9f3c" },// joins this record to its run manifest

  // --- Content: the conversation, in order ---
  "content": [                        // ordered parts; order is content, so it is covered by record_id
    { "type": "text",                 // both kinds are drawn; a text2text record holds only this one
      "role": "user",                 // who spoke; every turn is context and none of it is an answer
      "text": "Mã xác nhận của mình là <OTP_1>." },
    { "type": "audio",                // what a media modality writes instead: the file, by reference
      "role": "user",
      "uri":    "data/raw/4471.wav",  // where it sits; never in record_id, so moving it changes nothing
      "sha256": "b2c3d4e5…" }         // what record_id covers, so changing the file changes the id
  ],
  "content_version": 2,               // bumped only by pii_check; says which text the spans point into

  // --- The answer, and everything else the source carried ---
  "label": [ { "name": "SendStatement",                        // the training target. Nothing else is.
               "arguments": { "ma_khach": "<OTP_1>",           // checked against the tool's JSON Schema
                              "ky": "thang_nay" } } ],
  "meta":  { "human_checked": true }, // the source's own keys, verbatim; read only where declared

  // --- data_quality ---
  "data_quality": {
    "data_quality_config": { },       // the resolved config and its digest; written by the edge, read by services
    "label_check":     { "passed": true,          // did every check on the label hold
                         "failed_checks": [],     // which named checks did not, for triage
                         "quarantined": false },  // downstream services skip it; it is never removed
    "pii_check":       { "decision": "redacted",          // redacted | reported | withheld
                         "content_version_scanned": 1,    // which content the spans below index into
                         "spans": [ { "part": 0,          // index into `content`
                                      "start": 24,        // character offset, inclusive
                                      "end": 30,          // character offset, exclusive
                                      "class": "OTP",               // the typed class, which picks the placeholder
                                      "verified": true,             // did layer two confirm layer one's hit
                                      "placeholder": "<OTP_1>" } ],
                         "classes": ["OTP"],              // distinct classes found, for the corpus-level report
                         "unverified": 0 },               // hits layer two could not confirm; export's precondition reads this
    "duplicate_check": { "duplicate_content_same_label": [],  // same content, same label: safe to drop one
                         "duplicate_content_diff_label": [] } // same content, different label: one of them is wrong
  },

  // --- ai_review ---
  "ai_review": {
    "ai_review_config": { },          // resolved panel config and its digest; written by the edge
    "jury":     { "panel_version": 2,               // which panel composition produced these votes
                  "prompt_version": "jury_vote.v1", // which prompt; a change invalidates comparison
                  "llm_votes": [ { "model_name": "…",       // which juror
                                   "label_is_right": true,  // its verdict on the existing label
                                   "answer": [],            // its own answer, in the profile's answer shape
                                   "reasoning": "…",        // why, for the human who reads a disagreement
                                   "valid": true } ],       // is its answer in this record's answer space
                  "invalid_votes": 0,       // count of `valid: false`; a panel this noisy is visible in metrics.json
                  "plurality": [],          // the panel's most-common answer
                  "final_prediction": [] }, // what the panel is taken to have said; may differ from plurality
    "cohesion": { "self_agreement": 0.83,   // how much the jurors agree with each other
                  "label_agreement": 0.42,  // how much they agree with the existing label
                  "method": "…" },          // the estimator over δ, so two runs' pairs are comparable
    "triage":   { "bucket": "…",            // which cell of the two numbers this record falls in
                  "stratum": "…",           // the sampling group the bucket belongs to
                  "selected_for_review": true, // does a human see it
                  "reason": "…" }           // which rule selected it, so a quota can be audited
  },

  // --- human_review ---
  "human_review": {
    "human_config":      { },         // annotators and the question generator; written by the edge
    "question_generate": [ { "question_id": "…",    // stable id; the join key to the store and to answers
                             "question_name": "…",  // the short label an annotator sees
                             "content": "…",        // the question itself, in the annotator's language
                             "enum": [] } ],        // the permitted answers; free text is not one of them
    "publish":           { "stored": [],            // question_ids written to the store
                           "store_run_id": "…",     // which publish run wrote them, for idempotency
                           "published_at": "…" },
    "annotator_answers": { "responses": [ { "annotator_id": "u_14",    // who answered
                                            "question_id": "…",       // which question
                                            "verdict": "…",           // one of the question's enum values
                                            "corrected_value": null,  // what they proposed instead, where it validated
                                            "note": null,             // free text, never parsed
                                            "submitted_at": "…" } ] },
    "aggregate":         { "verdict": "…",          // the one verdict the overlap agreed on
                           "method": "plurality_verdict_mean_1_minus_delta", // how it was reached, since that is arguable
                           "confidence": 0.94,      // how much to trust it downstream
                           "overlap": 2,            // how many annotators saw this record
                           "alpha": 0.81 },         // Krippendorff's α for the incomplete-overlap design
    "curate":            { "status": "original",    // original | corrected | unresolved
                           "label": [],             // the final label; this is what ships
                           "validators": [],        // who produced it
                           "adjudicated_by": null,  // who broke a tie, where there was one
                           "decided_at": "…" }
  },

  // --- release (declared, not yet specified) ---
  "release": { }
}
```

### Per-service contracts

**Reads** is the set of keys a service may look at; anything else is none of its business. **Writes** is
the one key it owns. **Skips when** is the precondition it reads off the record: a record that does not
satisfy it is marked and passed on untouched, never dropped and never a reason to halt the run.

#### `load_data`

| stage | reads | writes | skips when |
|---|---|---|---|
| `load_data` | the raw item, under the declared label key | the whole record: identity, `branch`, `provenance`, `content`, `content_version = 1`, `label`, `meta` | never — it is the first stage. A source digest that does not match `params.source.sha256` raises `ConfigError` before any record is read |

The catalog is **not** copied onto the record as an answer space; `answer_schema` materialises it from
the record when asked and never persists it. A stored space is a second thing that can disagree with the
first, and it is the copy that goes stale.

**`load_data` is the one stage whose input is not the bus**, so it is the one exception to the single
signature § *Engine and edge* states below. A source item is not a record, and there is no record to
hand the stage that makes them, so it takes the items plus the three things only the edge can know --
the digest of the file they came out of, the ingest clock, and the run id (Requirement 12). `POST
/load-data` is its own route for the same reason, `pipeline/flow.py`'s `FROM_SOURCE` is where
`run_phase` reads it, and asking a phase endpoint to fold this one is a `ConfigError` rather than a
`TypeError` about keyword arguments. Handing the three in rather than reading them is also what makes
both shells produce one record (Requirement 46, I15): nothing in the engine has a clock.

**An item that cannot be read is counted, not raised.** Three things below this stage raise
`ConfigError` while records are being read — see § *Error Behavior* — and this is the only caller of
either axis, the only place that knows an item's offset, and therefore the only place that can turn
one into data. It catches, records the offset and the message, and hands them to the edge as side
output for the quarantine tier; the run completes (Requirement 43). What that gives up is stated:
where the *declaration* is wrong rather than the item, that is configuration scope and
stop, and a manifest naming a label key no item carries instead produces twenty thousand counted
items and no records. This stage cannot tell those apart at item 1 and does not guess — what it can
know is per item, so per item is the scope it reports.

#### `data_quality`

| stage | reads | writes | skips when |
|---|---|---|---|
| `label_check` | `content`, `label`, `meta` | `data_quality.label_check` | never; a record that fails a check is marked `quarantined` and travels on |
| `pii_check` | `content`, `label`, `data_quality.label_check` | `data_quality.pii_check`, **and rewrites `content` and `label` together, bumping `content_version`** | `data_quality.label_check` is absent — Requirement 42's precondition, and the only thing it skips. A **quarantined** record is still scanned: personal data in a record that failed a label check is still personal data, and this cell said "never" because no *verdict* is a reason to skip. A hit layer two cannot confirm raises `unverified`, which `export`'s precondition reads |
| `duplicate_check` | `content`, `label`, and the catalog in `meta` through `scenario_hash` | `data_quality.duplicate_check` | never; duplicates are grouped on the record, never removed |

The five label checks are the profile's, not the engine's — `label_checks()` is a profile member:
`label_assistant_mismatch` (the label contradicts the turn that restates it), `label_not_in_catalog`
(it names a tool this record does not offer), `empty_catalog` (there was nothing to choose from),
`label_cardinality_anomaly` (it names more tools than the profile permits), `label_names_one_tool_twice`
(a target of `["X", "X"]` trains a model to call X twice). Each carries a declared expected count in
`params.invalid_counts`, and a check reading 0 is what tells you when it stops reading 0.

**A duplicate needs both axes, and neither needed a new member.** The content side is the
modality's — a shared `record_id` for identical content, the declared `embedding` for near-identical —
and the answer side is the profile's δ: `answer_distance(a, b) == 0` is *the same answer* by the
profile's own definition, which a `==` on the stored form would get wrong for a bare name and for the
same call with reordered argument keys. `scenario_hash` is neither side: it names the task a record
poses, which is why it is the blocking key for the near pass. **The cost of that block, stated:**
pairwise cosine over one batch is quadratic and the block is what a real corpus divides it by, so a
corpus where every record offers one catalog is one block and the quadratic comes back. The exit then
is a signature to block on or an index — not a smaller batch, which would change the groups.

**PII, in two layers.** Layer one is `agent-toolkit`'s rule-based scans, one per class: a phone
number, an email address, a one-time code, a personal name. Each finds the written form and the form
a speaker dictates — digits as words, `@` and `.` said aloud — which is the half an off-the-shelf
scrubber misses, and each pattern behind one carries the toned and the tone-stripped spelling
together, so a single pass over the raw text catches `khong chin` and `không chín` both. It is tuned
for recall and is *allowed* to be noisy: a long digit run is also a price, a date, an order reference.
Layer two is a model pass over a bounded window that marks each hit verified or not. The
placeholder→original map is returned to the edge and written to a path the edge chooses, which
`.gitignore` covers.

**The classes are the modality's and the words are the library's.** `personal_data_detectors()`
returns one detector per class — `PHONE`, `EMAIL`, `OTP`, `NAME` — each naming the class its hits are
recorded under and carrying the scan that finds them. So the vocabulary a record's spans are written
in belongs to this axis, and every word a language reads a digit, an `@` or a name aloud with belongs
to the library, beside the `normalize_text` whose tone-stripping is the other half of the same
concern: a modality provides a task family's *framework* and cannot also decide the family's
language, and an English `text2text` corpus registering this one would otherwise get Vietnamese digit
words and nothing usable. What the manifest declares is one word — `language: vi` — and it is one
word rather than a block of vocabulary because the words for the digits do not vary between two
Vietnamese corpora, so declaring them per corpus buys a reader, a validation and a fixture for a fact
nobody should be able to get wrong. `vi` and `en` are written down; a language with no entry is a
`ConfigError` when the detectors are built, not a fallback, because scanning a Spanish corpus with
Vietnamese digit words finds nothing and finding nothing looks exactly like a clean corpus.

**A scan returns values, a span needs offsets, so the stage locates every value it is handed.**
`pii_check` searches the part for each reported value across any run of whitespace and takes the
matched slice of the raw text as the hit. That is what makes a name reported with single spaces a hit
where the transcript wrapped it over a line, keeps the offsets Requirement 19 records true offsets
into `content`, and keeps the replaced value the one that is actually in the text — the property that
makes a hit replaceable at all. A reported value no span can be found for is not a hit, which is
unreachable while every scan returns what it matched.

**Stated cost: an identifier with no cue word in front of it is not a class layer one has.** A bare
`480215` is an order number as often as a customer code, and a scan claiming it flags every invoice in
the corpus; `mã xác nhận 480215` is an `OTP` and is caught. What recall layer one has over
identifiers is a measurement over a declared corpus, which is the pilot's, and a class to add is a
rule added in `agent-toolkit` — reviewable in a diff there, and shared by every consumer of it.

**Layer two is a port, and its window is one part.** `PersonalDataVerifier.confirmed_personal_data`
takes the part's text and the values layer one flagged inside it, and returns the subset it confirms,
each under the class it confirms it as — a subset and never a superset, which is § *PII, in two layers*. So a
digit run a cue word put in front of and that is also long enough to be a number — flagged `OTP` and
`PHONE` both — is decided by the layer that can read the sentence around it. A value confirmed
in *any* part of a record is confirmed for that record: recall-first, and it is what keeps *one
placeholder per value* (Requirement 17) true across parts. No verifier and a verifier that failed are
the same answer for the same reason — the run completes and the record says `unverified`.

**Only a confirmed hit is replaced, and the decision says what happened.** Layer two exists to set
precision, so a hit it clears — the long digit run that is an order reference — stays in the text; if everything layer
one flagged were replaced anyway, layer two would buy a number and nothing else. That gives the
`decision` field its three values: `reported` with `enable_redact: false`, whatever was found
(Requirement 21); `redacted` where redaction is on and every hit was confirmed, *including* a record
with no hits at all, which is what `export`'s precondition needs to pass for a clean record; and
`withheld` where redaction is on and at least one hit could not be confirmed — the confirmed ones are
still replaced, and the record is held back by a precondition rather than by a count nobody reads.
`content_version` is bumped only where the text actually changed.

**Placeholders are numbered per class, per record, in the order the scan first met the value.** A gap
in the numbering is a value layer two cleared, and the spans say which — that is information, not a
defect.

#### `ai_review`

| stage | reads | writes | skips when |
|---|---|---|---|
| `jury` | `content`, `label`, materialised answer schema, `jury_slots` | `ai_review.jury` | `data_quality.label_check.quarantined` — no point paying a panel to judge a record already known broken; and a record `label_check` never saw at all, for the reason its own row gives |
| `cohesion` | `ai_review.jury`, `label` | `ai_review.cohesion` | `ai_review.jury` is absent |
| `triage` | `ai_review.cohesion` | `ai_review.triage` | `ai_review.cohesion` is absent |

Three stages rather than one, because they fail and re-run for different reasons: `jury` costs money and
is cached, `cohesion` is pure arithmetic, and `triage` is re-run on **exactly one** threshold re-tuning
pass after the pilot. A bucket whose precision the pilot cannot establish gets **no quota**.

**`triage` reads the two numbers and nothing from `data_quality`.** This cell said `data_quality`
until T21 and could not be true: a quarantined record has no `jury` key, so no `cohesion` key, so it
never reaches this stage — and Requirement 26 says the bucket is made of *those numbers*. Two other
statements said the same false thing, which is what makes it worth a paragraph rather than a
deletion. `record.py`'s `failed_checks` described itself as being read by triage, and it cannot be.
And `duplicate_check` writes `duplicate_content_diff_label` — *same content, different label: one of
them is wrong* — which is the strongest per-record argument in `data_quality` that a person should
look, and **nothing reads it anywhere.** Routing it is a change to Requirement 26 and not a defect in
this stage, so it is named here and in § *Out of Scope* rather than quietly implemented.

**Both cohesion numbers are δ, over the usable votes.** Agreement is `1 - answer_distance`, so a
jury that called the right tool with one argument wrong scores above one that called the wrong tool —
which a count of `label_is_right` would not, and every bucket is written on these two numbers
(§ *The answer, and the three operations over it*). An invalid vote is not measured: a distance to a point outside the answer space is
evidence about the panel's plumbing, which `invalid_votes` already carries. **A panel with fewer than
two usable votes scores `0.0` and not `1.0`** — absent evidence reads as absent agreement, because a
single juror scored as unanimous is a broken panel that `triage` would route away from the person who
should see it. `method` names the estimator rather than the distance, since the δ is already
identified per record by the profile version in `provenance`.

**The panel is a port and the judgment is not.** `JuryPanel` holds the composition, the task statement
out of `config/prompts/` and the retries, because a model call opens a socket and no engine module makes
one; what crosses is the filled slots and this record's materialised answer space, never the record.
What comes back is what each juror said, and whether a vote is *usable* is decided here, by the profile.
Letting the panel decide it by the schema alone would put two readings of *valid* on one record —
Requirement 24. An engine opened with no panel is a `ConfigError` from `jury` before the first record:
layer two's absence leaves `pii_check` a layer one to run, and this one leaves nothing.

#### `human_review`

| stage | reads | writes | skips when |
|---|---|---|---|
| `question_generate` | `content`, `label`, `ai_review.triage` (selection only) | `human_review.question_generate` | `triage.selected_for_review` is false. The glossary is a precondition on the *run*, checked at composition |
| `publish` | `human_review.question_generate`, profile capture half | `human_review.publish` | there is no question to publish |
| `annotator_answers` | `human_review.publish`, and the store through `annotation_response` | `human_review.annotator_answers` | nothing in the store names this record's questions |
| `aggregate` | `human_review.annotator_answers` | `human_review.aggregate` | fewer responses than the rung's overlap floor; the record keeps its answers and gets no verdict |
| `curate` | `human_review.aggregate`, `human_review.annotator_answers`, `label` | `human_review.curate` | there is no verdict, and — through a hand-made body only — no answers under one. A verdict that the label is wrong with no corrected value is **not** a skip: it is written as `status: "unresolved"` |

`question_generate` reads `triage` **only to decide which records get a question**. Nothing it reads
from `ai_review` reaches the payload, which is what Requirement 30 asserts.

**`curate` reads the answers as well as the verdict, because `aggregate` does not carry a person or a
correction.** A verdict, a confidence and three counts are what a fold produces; who decided, when,
and what they proposed instead are on the responses. The alternative was four more fields on
`OverlapVerdict`, copied from the key beside it — one more place for the same fact.

**An overlap is a number of people, not a number of submissions.** Nothing upstream enforces that:
the store has no unique `(question_id, annotator_id)`, and the sync writes every annotation the tool
returned. So `aggregate` and `curate` both fold over one answer per annotator — the last each of them
submitted — through `aggregate.one_answer_each`. Deduplicated at the fold rather than forbidden at
the store, because a person revising their own answer is legitimate and the second row *is* the
revision; what is not legitimate is counting it as a second opinion. Everything the numbers are read
for is about independent observers: `confidence` would take a self-pair for a corroboration, an
overlap floor of two would be cleared by one person twice, and Krippendorff's α is **defined** over
coders, so a unit holding one person twice is not a weak measurement of agreement but not a
measurement of one. `curate` needs it for a second reason — `vote_consensus` wants a strict majority
per tool name, and one person answering twice would otherwise outvote two who answered once.

**`aggregate` writes one number that is not about its record.** `overlap` and `confidence` are the
record's; `alpha` is Krippendorff's α over the batch, which is a fact about the annotation *design*
and is written identically on every record the run aggregated. A record aggregated alone therefore
carries the α of a corpus of one, and two records are comparable on it only inside one run. It is on
the record because the records are the report (Requirement 44), and the alternative — computing it at
the edge — would put the one statistic the pilot exists to read outside the artifact the pilot reads.

**α is over the verdict and not over the correction.** It compares every value to every other to
price the disagreement chance alone would produce, so it needs one value space every unit shares:
the three verdicts are that space, and a *correction* is an answer to one record's own catalog. A
coincidence matrix over answers from different records would be pricing the chance of agreeing about
two different questions. The corrections feed `confidence` instead, per record, through the profile's
δ — which is where Requirement 34's *agreement is not string equality* actually bites.

**`publish` and `annotator_answers` are two stages because a person answers between them.** They read
like halves of one exchange with the store, and whether to merge them is a fair question to ask of any
pair that talks to the same thing. Three answers. They cannot run in one call — `POST /human-review`
stops after `publish` for exactly this reason — so one module would still owe two routes, two
subcommands and two record keys, and each key has one writer. They re-run for different reasons,
the same argument that keeps `ai_review` at three: republishing costs a write and a re-sync, re-reading
answers is free and idempotent. And they read different things — `publish` reads
`human_review.question_generate` and the two config halves, `annotator_answers` reads the store.

**The shape they appear to share has three owners, and each is already one module.** The permitted
answers are the profile's capture half, and the inverse of that half is `annotation_response`, a member
of the same profile — I18 round-trips the pair, so adding a verdict value is one directory's edit and
neither stage names a value. `question_id` is minted by `question_generate`; `publish` echoes it into
`stored`, `annotator_answers` joins on it, and `edge/store/models.py` keys on it — one author and three
readers, so merging two of the readers leaves the author outside the merge. Idempotency is the two unique
constraints in the store's tables and `store_run_id` on the record: a table's guarantee, not a stage's.
Temporal decomposition would be one of those three decisions cut across the two stages. None of them is
cut — § *Per-service contracts*.

### Engine and edge

The engine computes; the edge supplies everything that came from a file, a socket or a clock.

```python
engine = open_engine(profile="tool_decision", modality="text2text",
                     config_root=Path("config"), params=Path("params.yaml"))
```

`Engine` is `dataforce/engine.py` — a resolved pair, a registry, thresholds, and the digests of the
policy files that produced them. It opens nothing. `open_engine` is `edge/bootstrap.py`: it reads the
two manifests, the thresholds and the prompt templates through `edge/policy.py`, builds the one
object that answers both axes (§ *The two axes*), registers it in both namespaces, and returns one. The type is the engine's because every service names it; the reader is the edge's
because it reads. Naming no modality takes the profile at its word; naming a different one raises
`ConfigError` saying which modality the profile composes with.

An engine can also be built with **no filesystem anywhere** — both axes handed `Manifest` objects and a
template string — which is what makes a web handler and an in-process caller the same caller.

Every service has one signature:

```python
def pii_check(engine: Engine, records: Iterable[Record]) -> ServiceResult: ...
```

`ServiceResult` carries `records` and any **side output** the edge must persist — for `pii_check` the
placeholder map, for `publish` the rows to store. The engine returns side output; it never writes it.
There is no third field: **the records are the report.** Anything corpus-level is a fold over them,
computed at the edge when a human wants to read it.

### Request and response models

`edge/routers/schemas.py` holds the pair every record route shares. A router keeps a `schemas.py` of
its own only for what nothing else speaks — `load_data/` for the two below, `human_review/` for
`SyncResponse`. Every field described, because that description is what a caller reads in `/docs`.

```python
class RecordsRequest(BaseModel):
    """Body for every service route except /load-data. Records in, records out."""

    # --- Which pair to run under ---
    branch: Branch = Field(
        ...,
        description=(
            "Which modality and profile to resolve. Must match the records' own `branch`; "
            "a mismatch is a 400 rather than a silently different run."
        ),
    )

    # --- Optional per-call configuration ---
    config: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Overrides for this phase's resolved config. Recorded verbatim into the "
            "record's <phase>_config key, so a run is reproducible from the record alone."
        ),
    )

    # --- The bus ---
    records: list[Record] = Field(
        ...,
        description="The records to run this service over, unchanged except for the key it owns.",
    )
```

`POST /load-data` is the one route that takes no records, and the one place the modality axis changes
the shape of the request:

```jsonc
{
  "branch": { "modality": "text2text", "profile": "tool_decision" },
  "items":  [ ],                                       // source items inline — the normal case for text2text
  "source": { "uri": "data/raw/<declared source>.json",// or a reference, for a file too large to post
              "sha256": "a1b2c3d4…" }                  // checked before a record is read
}
```

`items` and `source` are mutually exclusive and one is required. **For `text2text`, `items` inline is
the normal case** — the content is already in the body and nothing needs reading. For `speech2text`,
`image2text` and `video2text`, each item references its media by URI; `load_data` resolves it through a
resolver the modality declares, records `uri` + `sha256` + duration or dimensions, and the engine never
opens it. That port arrives with the first media modality and not before.

**Response:**

```jsonc
{
  "records": [ ],                     // the bus, one key richer; always as many out as went in
  "metrics": { "skipped": 0,          // how many records this service passed over untouched, and why
               "counts":  { } },      // the fold a human reads; no threshold, no verdict
  "run":     { "run_id": "…",         // joins to every record's provenance
               "producer": { },       // both axis versions
               "policy":   { } }      // every policy file read, by digest
}
```

**A service route returns `200` with every record it was given**, because a bad record is a marked
record rather than a failed request. `ConfigError` is `400` — an unknown profile or modality, a
declaration that is missing, a source digest that does not match — and it is raised before any record is
touched. A malformed body is pydantic's `422`. Anything else is `500`.

### The question store

`publish` writes to a database we own; a separate sync moves questions into Label Studio and answers
back out. Three tables, owned by `edge/store/`, every column carrying its purpose in the model.

| table | columns |
|---|---|
| `question` | `question_id` pk · `record_id` · `run_id` · `modality` · `profile` · `payload` json · `created_at` |
| `publication` | `question_id` fk · `external_system` · `external_project_id` · `external_task_id` · `status` · `pushed_at` · unique (`question_id`, `external_system`) |
| `annotator_answer` | `answer_id` pk · `question_id` fk · `annotator_id` · `result` json · `was_skipped` · `lead_time_seconds` · `submitted_at` · `external_annotation_id` unique |

- The engine knows none of this. `publish` hands rows across the `QuestionStore` port — declared in
  `dataforce/ports.py`, because a port is what the engine demands, not what an adapter offers — and
  `edge/store/repository.py` writes them. The DSN is read at the edge from `DATAFORCE_DATABASE_URL`.
- **`result` is one column and not three.** This table drew `verdict`, `corrected_value` and `note`
  until T23. Requirement 49 makes `annotation_response` *the only place an annotation tool's shape is
  read*, and decomposing an annotation into three columns needs a second reader of that shape — in the
  layer furthest from the capture half that defines it, and with no record to validate a corrected
  value against. So the store holds the control values verbatim and the profile is the only thing that
  reads meaning into them. What it costs is that *how many annotators said incorrect* stops being one
  SQL query and becomes a fold over records, which Requirement 44 already says it is. The envelope is a
  different fact and stays decomposed: `was_skipped` and `lead_time_seconds` are the tool's own
  metadata, they answer nothing, and the pilot reads them as instruments.
- **The port is two members, and Requirement 32 is why there is a port at all.** `stored_questions`
  returns a receipt — which question ids the store holds, under which write, when — and `answers_to`
  returns every answer to a set of question ids. Whether a stage reaches the store through a port or
  hands rows back as side output was open until T23: only the first shape lets `publish` record its own
  receipt, because a receipt names a write that has already happened, and that key has one writer.
- **Writing a question the store already holds is a no-op**, because a `question_id` is a pure function
  of the question: a second publish of an unchanged corpus is the same rows. Insert-if-absent and not an
  upsert — an existing row records what was *published*, and overwriting its payload would rewrite a
  question a person may already have answered. `store_run_id` is a digest of the ids written rather than
  a fresh id per call, so a re-run's record is identical except for `published_at`. The no-op is
  `ON CONFLICT DO NOTHING` and not a read of which ids are held: that read is a check with a window in
  it, and two publishes of one batch both see nothing, both insert, and the second raises about a row
  that says exactly what it wanted to say. It is the rule the sync's own module states, kept here too.
- **SQLite by default, Postgres by URL.** SQLAlchemy 2.0 declarative models, Alembic migrations. The
  two are named rather than assumed: `store_engine` reads the backend out of the DSN and refuses a
  third when the pool is built, because `ON CONFLICT` is the one thing the adapter spells twice and a
  backend the tests have never run against would reach that fork with nothing to do.
- `POST /human-review/publish/sync` pushes unpublished questions into Label Studio through
  `label-studio-sdk`, writes the returned task ids into `publication`, then pulls new annotations into
  `annotator_answer`. It is idempotent in both directions: the two unique constraints are what make it
  so. `edge/label_studio.py` is the sync and the only module that imports the SDK, which it does
  *inside* its builder — the extra is optional and an install without it must fail at that one
  endpoint rather than at startup.
- **Each `publication` row is committed as its task is created, one at a time.** Batching them into
  one transaction would roll back the rows for tasks that already exist, and the next sync would
  create those tasks a second time — which no constraint can catch, because the row that would have
  caught it is the one that was rolled back. The row *is* the record that the task exists.
- **The sync touches no record.** It moves rows between the store's three tables and an instance; the
  bus never enters it, so a failed sync cannot leave a record saying something that did not happen.
- Running the sync is optional. Every other endpoint works with no Label Studio anywhere.
- `was_skipped` is Label Studio's `was_cancelled`: the annotator saw the question and declined it.
  That is not a verdict and not a missing row — a skip is evidence about the *question*, and the pilot
  reads the skip rate to decide whether a question is answerable at all. `lead_time_seconds` is its
  `lead_time`, kept for the same reason: both are instruments, and Phase 8 measures the instruments.

### The annotation config, and what comes back

Requirement 31 says `edge/label_studio.py` composes the config. This is what it must emit, because the
tool on the other end is real and its input is not ours to choose. Everything below is
community-edition Label Studio; nothing here needs Enterprise.

**The display fragment is `<Paragraphs>`, not `<Chat>`.** The `<Chat>` tag renders a conversation
exactly the way a chat corpus wants and is **Enterprise and Starter Cloud only**, so it cannot be the
community path. `<Paragraphs layout="dialogue" nameKey="role" textKey="content">` takes a JSON array of
message objects and is a first-class community tag, and the adapter fills that array from
`record.content`: one object per part, `role` and `text` as they already sit on a `Part`. **No axis is
asked for it.** A media modality changes which tag this module writes and changes no protocol, which
is the seam working: a modality that had to emit this tag would be shipping a page layout with every
new family, and this module already owns the tool.

**The capture half is one required verdict and a gated correction.** A composed config:

```xml
<View>
  <!-- display fragment — the adapter's, from record.content -->
  <Paragraphs name="conversation" value="$conversation"
              layout="dialogue" nameKey="role" textKey="content"/>
  <Header value="$question"/>

  <!-- capture half — the profile's, enclosed verbatim -->
  <Choices name="verdict" toName="conversation" choice="single-radio"
           required="true" requiredMessage="Answer the question before submitting.">
    <Choice value="correct"/><Choice value="incorrect"/><Choice value="unsure"/>
  </Choices>

  <View visibleWhen="choice-selected" whenTagName="verdict" whenChoiceValue="incorrect">
    <Choices name="corrected_names" toName="conversation" choice="multiple"
             value="$tool_names" required="true"/>
    <TextArea name="corrected_arguments" toName="conversation" rows="4"/>
  </View>

  <TextArea name="note" toName="conversation" rows="2"/>
</View>
```

`visibleWhen` + `required` is how *"answering incorrect requires the corrected value"* (Requirement 29)
becomes a thing the tool enforces rather than a thing we hope for. `value="$tool_names"` is a **dynamic
choice list**: the catalog is per record and a Label Studio project has one config for every task, so a
static `<Choice>` list cannot express it. `randomize="true"` is available on `<Choices>` and is worth
setting where an option's position could bias an answer.

**The task payload** is the basic Label Studio JSON format — one `data` dict whose keys are the `$`
names above, and nothing else:

```json
{"data": {
  "question_id": "q_7f3a…",
  "question": "Câu hỏi cho người gán nhãn…",
  "conversation": [{"role": "user", "content": "…"}, {"role": "assistant", "content": "…"}],
  "tool_names": [{"value": "LookupBalance"}, {"value": "SendStatement"}, {"value": "OpenTicket"}]
}}
```

Dynamic choices read *objects*, not strings — `{"value": "LookupBalance"}` — which is the kind of
detail a parser written from memory gets wrong. **Each half owns its own keys**, and they are
disjoint: `conversation` is the adapter's, `tool_names` is the capture half's, and `question_id`
and `question` are neither axis's — `publish` adds them, because neither axis knows a question.
**The store's `payload` therefore holds the two halves `publish` can reach, and the adapter joins its
own key on as the task is created** — the tag that reads `$conversation` is written in the same module
that composes the array, and a stage that wrote either would be composing half a page for a tool it
is not allowed to know about. That join is where the sync route lands it; until then the store's
payload is the whole of what a task would carry minus the conversation.
That is why `answer_config` takes a record: half of what it returns is per record. `question_id` rides
inside `data` because Label Studio
assigns its own task ids and we must map an annotation back to the question that produced it;
`publication` records the pair, and `data.question_id` is what makes the mapping survive a project
rebuild. Requirement 30 is asserted on this dict: no vote, no cohesion number, no bucket appears in it.

**What comes back** is `annotation.result`, a list of one object per control that was answered:

```json
[
 {"from_name": "verdict", "to_name": "conversation", "type": "choices",
  "value": {"choices": ["incorrect"]}},
 {"from_name": "corrected_names", "to_name": "conversation", "type": "choices",
  "value": {"choices": ["SendStatement"]}},
 {"from_name": "corrected_arguments", "to_name": "conversation", "type": "textarea",
  "value": {"text": ["{\"SendStatement\": {\"ma_khach\": \"<OTP_1>\", \"ky\": \"thang_nay\"}}"]}}
]
```

A `textarea` value is `{"text": [...]}` — **a list**, because `maxSubmissions` permits more than one.
A control the annotator never touched is absent from the list rather than present and empty. The
annotation also carries `completed_by`, `lead_time` and `was_cancelled`; a `was_cancelled` annotation
is a skip and carries no verdict.

**The rungs are project settings, not prose.** Smoke is `maximum_annotations: 1`. Pilot is
`maximum_annotations: 2` with `overlap_cohort_percentage: 100` — that *is* "two annotators at 100%
overlap", and `aggregate`'s overlap floor reads the same number so the two cannot drift. The two
count slightly different things — `maximum_annotations` is a ceiling on *submissions* per task and
the floor is a count of *people* — and they agree because Label Studio does not hand one task to the
same annotator twice. Where they part is exactly where the floor is right and the ceiling is not. That floor
is `params.thresholds.aggregate.overlap_floor`, and the two moving together is a discipline until
there is a project to read: a project collecting one answer and a floor of two produces a corpus
where nothing is ever aggregated and nothing says why.

**The capture half also declares which verdict endorses the label.** `answer_config().endorsing_verdict`
is `correct`, and `curate` reads it rather than naming a value — so a fourth verdict is one
directory's edit, which is what § *Per-service contracts* promises. Every other verdict leaves the label to a
correction, and no correction anyone can act on is `unresolved`.

**The cost, stated.** A set of calls with typed arguments has no widget in community Label Studio, so
`corrected_arguments` is a JSON object an annotator types. That is a real burden on the person doing
the work and a real source of malformed input, which is why `annotation_response` validates against
the record's own `answer_schema` and returns `None` rather than a half-parsed answer. It is also the
strongest argument for the annotation platform `objective.md` §9 defers — recorded here so the pilot's
skip rate and lead time are read as evidence about *that* decision, not only about the questions.

### Configuration

`config/<axis>/<name>.yaml` for identity and declarations, `config/prompts/…` for templates,
`params.yaml` for every threshold. **`config/gates.yaml` is deleted** — the numbers it held were
comparison targets for gates that no longer exist; the ones that survive are triage boundaries and
panel settings, which belong in `params.yaml` with the rest.
`config/modalities/text2text.yaml` carries the modality's identity in its filename, so the pair's name is
not assigned anywhere else; the profile manifest's `modality:` names the same string.
`params.invalid_counts` lists the five label-check names with no values, and `params.source` is empty —
both stay that way until a corpus is declared. `params.thresholds` is the same shape with one
exception: `duplicate_check.near_duplicate_cosine` carries a value, because a similarity has no
defensible default — 0 groups every record with every other and 1 groups nothing — so the stage
refuses to guess and the number is provisional with its re-measurement named beside it, the way the
profile manifest's `max_calls` is, and `aggregate.overlap_floor` carries one for a different reason:
it is a rung's setting rather than a measurement, `1` is the Smoke rung, and a floor nobody declared
would read as zero and fold a verdict out of no answers. The two empty blocks belong to `jury`, which
reads no threshold, and to the pilot, which has not run.

**`config/model/<model>.json` is the fourth file a run reads, and the one it does not record.** It is
where a deployment attaches an endpoint it already serves — `model`, `base_url`, `api_key` — read
through `agent-toolkit`'s `JsonDirConfigResolver`, on an instance rather than through
`set_config_resolver`, whose process-wide global is the same defect Requirement 39 makes a registry
instance state to avoid. It is not a policy file, and adding it to the run manifest's digests would
break I14 in a way nobody would predict: the file holds the key, so two people pointed at one
endpoint with two keys would produce two manifests for one configuration and a rotated key would read
as a changed configuration. What is recorded instead is `embedding.model` inside the modality
manifest, whose digest is already there. The file is git-ignored and a `<model>.json.example` beside
it is what the repository ships, so a checkout composes only once a deployment has
attached one — an absent file is a `ConfigError` naming the path, before the first record.

**Every key a manifest declares has a reader, and the reader validates it.** The modality's are
`embedding.model`, `embedding.exclude_roles` and `language`; the profile's are `shape`,
`answer_control`,
`max_calls`, `label.at`, `roles.target` and `prompts.question`, plus `gold.from`, whose only reader is
the pilot's gold accuracy in T31. A declaration is read once, at composition, so a wrong *type* is
still a `ConfigError` there: `exclude_roles: system` — one character from `[system]` — used to become
a frozenset of five letters, so no role matched and every vector silently included the instruction
turn, and `max_calls: 2.7` used to truncate to 2. Four keys were declared with no reader at all
(`roles.instruction`, `roles.conversation`, a `meta:` rename map from our names to the source's, whose
five values were the retired corpus's) and are deleted: Requirement 9 keeps `meta` verbatim, so a
rename map has no future reader either.

The profile manifest also declares **`max_calls`** — the cardinality ceiling. `answer_schema`
materialises it as `maxItems` and `label_cardinality_anomaly` reads the same number, so the check and
the space an answer is validated against cannot disagree. It is provisional, and the manifest records
what re-measures it: the distribution of `len(label)` over a declared corpus.

And it declares **`answer_control`**, which decides what an annotator can physically
express and therefore what a measured agreement figure means. It is `names_and_json_arguments`: the
names come from a dynamic choice list over this record's catalog, so they cannot be mistyped, and only
the arguments are typed by hand. `per_name_arguments` — a rendered argument form per chosen tool — is
what we would want and cannot have, because a Label Studio project holds one config for every task
while our catalog is per record. Stamping the value here is what lets a later agreement number be read
against the surface it was measured on.

---

## Versions

| Thing | Version | Why / source |
|---|---|---|
| Python | 3.12 (`>=3.12,<3.13`) | unchanged; `.python-version` |
| FastAPI | `>=0.141.1` | current release, PyPI |
| Uvicorn | `>=0.52.4` | current release, PyPI |
| SQLAlchemy | `>=2.0.52,<2.1` | current 2.0.x, PyPI; 2.0 declarative style |
| Alembic | `>=1.19.1` | current release, PyPI |
| label-studio-sdk | `>=2.1.1` | current release, PyPI; used only by the sync |
| Label Studio (server) | 1.23.0 | the release the sync is written against, not a Python dependency. **Community edition** — Requirement 52 is what that costs. `deploy/` gets the compose file with T26, the first task that needs an instance |
| pydantic | `>=2.13` | unchanged; `Field(description=…)` is Requirement 1's mechanism |
| agent-toolkit | `@v0.2.0` git tag | the pin resolves by tag and `uv.lock` records the commit, so `uv.lock` is the record of which build a run got. `v0.2.0` is the first tag holding the four personal-data scans and the five vocabulary tables behind them, which is what layer one is built from; `v0.1.0` was moved once, which is why a tag name here is not a tree |
| openai | `>=3.2` | the embeddings call `duplicate_check` groups through; `agent-toolkit` exposes none, so this is the one direct use, under one I6 exemption |
| ~~model2vec~~ | removed | the deployment serves `bge-m3` on an endpoint it already runs, so no run downloads a model — Requirement 23 |
| ~~dvc / pandera / pandas~~ | removed | none of the three had a job in this design, and the three of them carried 76 packages into the lock |

`fastapi`, `uvicorn`, `sqlalchemy` and `alembic` are runtime dependencies. `label-studio-sdk` goes in an
optional `[label-studio]` extra, so the pipeline installs without it.

---

## Invariants

Each names the check that holds it, not a file that used to.

| # | Invariant | How it is checked |
|---|---|---|
| I1 | The engine opens no file and names no path | AST scan over every engine module, plus a subprocess import from an empty directory |
| I2 | `pipeline/` imports no concrete axis | AST scan for any import matching a registered implementation |
| I3 | Code's phase and stage names are the flow's, this document's, and the record's | the § *The flow* table is parsed out of this file and its `(phase, stage, summary)` rows compared in order against `PHASES` and `STAGES` in `pipeline/flow.py`; module filenames and `STEP ·` docstrings are compared to the same source; and each phase's stages are compared to the keys `Record.<phase>` holds, in both directions, a `<phase>_config` key excepted. Changing any side alone fails the build. That last comparison closes a triangle I3 and I20 left open: a stage renamed everywhere but on its phase model made `metrics.json` report it as `0` for ever, and no guard could see it |
| I4 | An axis implementation's `schema.py` imports no sibling, and a `utils.py` beside it holds only conversions over those shapes | two halves, over both axis packages. `schema.py` must exist and import nothing from its own package — generalised from *imports no `utils`*, because a `schema.py` importing `detectors.py` is the same defect under a new filename and the old spelling could not see it. Then, for any module named `utils.py`, every top-level function must reference a name `schema.py` defines: AGENTS.md grants that filename "only for conversions over the shapes in the `schema.py` beside it", and this is that condition, checked. *Every*, not *most* — the convention says "and nothing else", and a threshold would be a tuned literal with no measurement behind it. The second half reports one finding per module so one exemption annotation can excuse it; both implementations carried one between T55 and T56, and neither has a `utils.py` now, so this half binds the next axis someone writes. **The file-set half is gone**: it required exactly three files, which made the convention's own remedy — give the module a real name — a build failure |
| I5 | Identity comes from the manifest filename, never a class body | AST scan for `name`/`version`/`modality` and their `modality_`/`profile_` prefixed forms assigned in a `ClassDef` |
| I6 | Nothing re-implements an `agent-toolkit` function or imports a dependency it owns | AST scan for every function the installed library exports — read off the `__all__` of each front door, so a name the document forgets is still owned — plus the four owned roots and `hashlib` — the one import a second `record_id` would come through. One annotated exemption stands, in `profiles/tool_decision/answers.py`: the library owns validation and exposes it only inside `complete_structured`, and Requirement 49 validates a human's corrected answer with no model call — a hand-written twin of a schema we materialise ourselves is the pair of definitions this rule exists to prevent |
| I7 | Every field of every data class has a description | two halves, because Requirement 1 names two kinds of data class: model introspection over every pydantic field's `description`, and an AST scan for the trailing comment on every field of a `@dataclass` or a `NamedTuple`, read over every line the declaration spans |
| I8 | One writer per record key | run every service over one record; assert each diff is exactly one key |
| I9 | `record_id` is stable across a shuffled re-ingest and sensitive to content | property test over a synthetic corpus |
| I10 | No answer space is ever stored | `Record` has no such field; constructing one raises |
| I11 | No stage removes a record | run every service; assert `len(out) == len(in)` and that the id sets are equal |
| I12 | No model output reaches an annotator | assert on the `publish` payload and the generated config |
| I13 | The placeholder map is never read by a service and never committed | AST scan plus a `.gitignore` assertion |
| I14 | Two runs of one unchanged configuration produce identical run manifests **apart from the `run_id` that names them** | run twice under one id, compare bytes. The exception is not a weakening: `minted_run_id` stamps a clock, so two real runs never share an id, and the sentence without this clause is one no run can satisfy. The id is an argument to `run_manifest` rather than read inside it precisely so the rest of the manifest is comparable, and the id's own suffix is a digest of the policy digests — so *unchanged configuration* is still visible in the one field that moves |
| I15 | HTTP and in-process produce the same record | same input both ways, asserted equal |
| I16 | Nothing above an axis implementation names one | AST scan over each axis's `base.py` **and** its `__init__.py`. A façade that re-exports its implementations makes every importer of the axis load them, and no scan of the consumer can see that: the consumer's line is clean and the coupling is one hop away |
| I17 | A phase's stage order exists once | AST scan: no module under `edge/routers/` or `edge/cli.py` names two stages in sequence; both call `run_phase` |
| I18 | The annotation format round-trips | compose the config and payload for a fixture, feed back a synthetic `result` in Label Studio's shape, assert `annotation_response` returns the answer that went in — and that a `textarea` string, not a list, fails |
| I19 | Every module is in § *Package layout*, described the way it describes itself | the tree is parsed out of this file: every row names a module that exists, every module has a row, and each row's text is that module's own docstring line |
| I20 | The record's keys are the keys § *The record* draws | the JSONC drawing is parsed out of this file and compared key by key against `Record`'s fields, nested models included. `label` and `meta` are free-form and named as exceptions: the drawing shows example contents of those two, not keys |
| I21 | Each axis protocol has the members its section writes down | the `Protocol` block is parsed out of this file and compared to the runtime members, and the count both that section and the module's own docstring state in words is compared to the same number |
| I23 | An axis implementation's public surface is exactly its protocol's members | AST scan over each axis package: every class its façade exports has, as methods and `self.…` assignments, precisely the protocol's member set. I21 compares the protocol to the document and so cannot see a member that is only in the *class* — a public method in neither contract, which is how `final_label` shipped as a fifteenth |
| I24 | Every JSON serialisation in the package is the same one | two halves. AST scan for every `json.dumps` / `json.dump` in the tree, whose keyword set must be exactly `sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=False` — those three are part of what a `record_id` is, and since T56 the form is written **once**, as `record.canonical_json`, which `record_id_for` and both axes call. I9 cannot see a change here: it re-derives both sides of its comparison through the same call, so a flip that re-keys the whole corpus moves its expectations with it. The second half runs `canonical_json` over values chosen to tell each option apart, because a scan of the source alone would be satisfied by a function nobody calls |
| I25 | `declarations.py` names no manifest key | AST scan over that module's string literals, docstrings aside, against every string either axis assigns to a module-level constant — derived from the tree rather than listed here, so the two cannot drift into agreeing while both are wrong. The four functions take `*path: str` and every key stays in the axis that means it, which is what answers § *The two axes*' objection to a shared reader: there is nothing in it for either axis to learn about the other |
| I22 | Every module's docstring opens with one of the five kinds | AST scan over the tree. The five words are read out of Requirement 2 rather than listed a second time, so a sixth kind becomes legal by being written down. `dataforce/__init__.py` is the one exception and says so in its own docstring |

---

## Error Behavior

| Situation | Behaviour |
|---|---|
| Source digest ≠ `params.source.sha256` | `ConfigError` before a record is read — the one place a run refuses to start |
| Undeclared label key | `ConfigError` naming the manifest, the key, and what *is* declared |
| A `language:` no scan has a vocabulary for | `ConfigError` naming the languages there are, raised where the detectors are built and so before any record is read. Left to the scan it would arrive as a missing table on the first record, and a layer one that finds nothing looks exactly like a clean corpus |
| An item whose `messages` is not a list, whose turn declares no `role`, or whose `meta` lacks the declared label key | `ConfigError` from `content_parts` or `build_record`, raised **while** records are being read — which Requirement 43 does not permit. Neither signature has a value channel for *this item is unreadable*, and `Record.label` is required so a missing label cannot default to *call nothing*. **`load_data` catches all three**, counts the item against its offset and returns them as side output for the quarantine tier, so a run still completes; both axis modules record the break and § *Per-service contracts* row 0 records what it costs. A fourth raise stood beside these until T14 and was deleted rather than caught — provenance is a parameter of `build_record` now, so an item without it cannot be constructed |
| A turn's `content` is a content-block array, or any other non-string | read, never refused: a text block contributes its text and any other block its canonical JSON, so nothing leaves `record_id`. Requirement 13 declares the OpenAI chat-completion shape and this is that shape, so such an item is a declared item and becomes a record |
| Unknown profile or modality | `ConfigError` listing the registered ones; an empty registry says "none" |
| Profile and modality disagree | `ConfigError`: "composes with modality 'text2text'" |
| A record fails a check | it is marked on its own key and travels on; the run continues and the count lands in `metrics.json` |
| A record does not satisfy a service's precondition | that service skips it, writes no key for it, and counts it in `metrics.skipped`; every later service sees the same absence and skips too |
| A declared count has moved | a line in the `metrics.json` diff. **Nothing stops.** This is the cost of Requirement 22 |
| A jury vote does not validate | counted as an invalid vote, kept with `valid: false`, never silently dropped; a noisy panel shows up as a high `invalid_votes` fold |
| A model call fails after retries | `agent-toolkit` owns retry and rate limiting; an exhausted call is one missing vote, and `cohesion` computes over the votes that arrived |
| The whole panel fails for one record | read as *no votes*, for the reason above: the record carries no vote, a null `final_prediction` and a bucket that sends it to a person, and the run completes |
| A port raises `ConfigError` mid-run | it is **not** caught. Both model ports promise not to raise, and `ConfigError` is the one exception this codebase defines: it means a human must change configuration, so an adapter that cannot reach its endpoint stops the run rather than raising it twenty thousand times. Caught, `jury` completes with every record scoring `0.0` and landing in `contested`, and `pii_check` completes with every hit `unverified` — one fails silent and one fails safe, and neither says why |
| `ai_review` run on an engine with no panel | `ConfigError` from `jury` before the first record. It is a fact about the configuration, not about a record, and writing a key that says the panel agreed on nothing would be a lie about a call nobody made |
| `enable_redact: false` and personal data found | `pii_check` reports, `content` untouched, `decision: "reported"`. The run completes. `export`'s precondition is what keeps it out of a release — and export is not built yet, so **until it is, nothing prevents a reported-but-unredacted corpus reaching an artifact** |
| Label Studio unreachable during sync | the sync fails; no record key changes, no `publication` row is written, every other endpoint is unaffected |
| A question is synced twice | the unique constraint makes the second a no-op |

---

## Observability

A run over twenty thousand records that reports nothing until it finishes is a run nobody can
supervise, and the first thing anyone asks of it — *where is it, and is it going wrong* — has no
answer. So the events are part of the design, not something added when a run first hangs.

**The engine emits; the edge decides where.** Every module uses the standard library's
`logging.getLogger(__name__)` and nothing else. That writes to a stream the application does not own,
open or rotate, which is what keeps it inside Requirement 36: a logger call opens no file and names no
path. I1's scan permits `logging` by name and forbids what it always forbade — `open`, `Path`,
`os.environ`, a socket, a clock.

**Every event carries the same three keys**, because an event that cannot be joined to a run and a
record is a sentence in a log file rather than data: `run_id`, `record_id` (absent only for
composition-time events), and the stage that emitted it. That contract is one module —
`edge/observability.py` — and not a paragraph two shells each implement: `edge/main.py` and
`edge/cli.py` install the handler it builds, nothing else configures logging, and no module writes to
a file.

**What is worth an event, and at what level.** `INFO` once per stage per batch — started, finished, how
many records, how many skipped by precondition. `WARNING` per record for the things a human must
eventually look at: a record quarantined, a precondition unmet, a vote that did not validate, a
corrected value that did not parse, a PII hit layer two could not confirm. `ERROR` only for the one
exception this codebase raises, `ConfigError`, which happens before any record is read. There is no
`DEBUG` per record — twenty thousand records times fifteen stages is three hundred thousand lines, and
a log nobody reads is not observability.

**Events are not the report.** `ServiceResult` still carries records and side output and nothing else:
what happened is on the records, and `metrics.json` is a fold over them at the edge. The event stream
is for watching a run *while it runs*; the records are for reading it afterwards. Conflating the two is
how a log becomes a database.

---

## Testing Strategy

There is no test suite. It is written against this document, in this order, and `make check` (ruff,
`mypy --strict`, pytest) must pass before each step lands.

**The suite mirrors the layout** — `tests/guards/`, `tests/stages/`, `tests/properties/`,
`tests/shells/`, `tests/integration/`. Steps 1–4 below are those first four directories, in order.

1. **The guards first (I1–I7, I16–I17, I19)**, before any service. Each is an AST or introspection
   check proved against synthetic source, so the guard fails before it is ever needed. Writing them after the services is how
   a codebase acquires the thing the guard forbids.
2. **One test module per stage**, asserting that stage's reads/writes/skips-when row: it writes its key,
   writes nothing else, returns as many records as it was given, and skips exactly the records its
   precondition excludes.
3. **The bus property (I8) and the conservation property (I11)**, once and together: build a corpus,
   run every built service, and assert that each step's diff is exactly one key and that the
   set of `record_id`s is identical at every step.
4. **Both shells (I15)**: the same input through `pii_check(engine, records)` and
   `POST /data-quality/pii-check`, asserted equal.
5. **Fixtures are invented, never extracted from real data**, in `objective.md` §2's
   shape. There is no corpus-wide test until a source is declared; when one is, it asserts the label-check
   counts against `params.invalid_counts` under `-m integration` and nowhere else.
6. **PII gets adversarial fixtures**: spoken digits with and without tone marks, `a còng`, `chấm`, a
   code behind its cue word, a name behind its title, a name the transcript wrapped over a line, a value
   used twice in one record (one placeholder), and a long digit run that is an order reference rather
   than a phone number — layer one flags it, layer two clears it.
7. **The store**: SQLite in `tmp_path`, idempotency asserted by running the sync twice against a fake
   Label Studio client.
8. **No network in `make check`.** Every jury test uses a stubbed panel; the live panel is the Smoke rung,
   under `-m integration`.
9. **What is stubbed is run for real somewhere.** `make check` substitutes two backing services — SQLite
   for Postgres and a stub for the panel — and both substitutions are where a dev/production divergence
   would hide. `make integration` runs the store tests against a real Postgres, the sync against a real
   Label Studio, and the panel against real models. Neither suite is optional: the fast one is the one
   that runs on every commit, and the slow one is the one that is allowed to be believed.

---

## Out of Scope

- **`release`** — `split`, `export`, `datasheet`. Declared in the flow so it is complete and
  `record.release` has an owner; specified in a follow-up. Nothing before it may assume its shape.
- **The web view.** One Vite + TypeScript SPA over these same endpoints, on the style reference's
  pattern — `objective.md` §9 calls it a later task, and this spec keeps it one.
- **Real `speech2text`, `image2text`, `video2text`.** The seam is specified — media parts, the pair
  naming, and Requirement 16's resolver behaviour — and unenforced. The resolver *port* is deliberately
  not declared until a modality demands one. Only `text2text` is built.
- **A second profile inside `text2text`.** `summarize`, `classification` and the rest of the family
  are what this axis exists to hold — a modality is a family of tasks and a profile is one task in it
  (§ *The two axes*) — and only `tool_decision` is built. Deferred rather than excluded, and named
  here because the omission is louder than the modality one: **sixteen protocol members have been
  designed against a single example.** What is unknown is not whether a second profile fits, but
  whether all sixteen members are a *profile's* surface or whether some are `tool_decision`'s own,
  leaked into the protocol because nothing else was ever asked to implement them. The second profile
  is the measurement; until one exists, adding a seventeenth member is a guess about a task nobody has
  written, and the count staying closed is what keeps the guess from being made.
- **Our own annotation platform.** Deferred, not cancelled; the pilot decides.
- **Model training and evaluation, synthetic data generation, active learning, fine-tuning a juror,
  Confident Learning**, and automatic write-back to any source file. Export produces an artifact; putting
  it anywhere is a human step.
- **Routing a duplicate pair that disagrees to a person.** `duplicate_check` writes
  `duplicate_content_diff_label` — *same content, different label: one of them is wrong* — and nothing
  reads it. It is the strongest per-record argument in `data_quality` that a human should look, and
  Requirement 26 says a triage bucket is made of the two cohesion numbers, so routing it is a change to
  that requirement rather than a gap in `triage`. Named here so the group is a known unread signal
  instead of a forgotten one; the pilot is where it is worth arguing, since a bucket needs measured
  precision before it earns a quota.
- **Caching the panel.** § *ai_review* and § *Per-service contracts* both assert that `jury` costs money
  per record and **must be cached** — it is the whole reason `ai_review` is three stages — and no module
  owns it in either document. A cache is I/O, so it cannot be the engine's; T27 is where it lands, and
  until it does, re-running `jury` re-pays the panel in full and nothing says so at the call site.
- **The two blocking prerequisites that are not code**: the cross-border data-transfer review before the
  first offshore jury call, and the written glossary before the first generated question. Both are
  preconditions on *opening the engine*, checked once at composition and raised as `ConfigError`; this
  spec requires them to be *recorded* and does not perform them.
