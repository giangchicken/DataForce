# A value a call passes is a slot, and a slot can be filled again

## What

A ninth step for `tool_decision`, and one act inside it.

**The step.** Once the label is settled, every value the sample's tool calls pass becomes a numbered
slot — `<SVCCALCULATEINTEREST__PRINCIPAL_AMOUNT_1>` where `800 triệu` stood — so that one labelled
conversation can be re-filled with a hundred different amounts afterwards and teach a model the
argument rather than the number. Two detectors find them: a model reading the conversation for
every mention of an argument's value, and a rule scan searching for the value the call spells out.
**The model is the larger half, measured** — this corpus is transcribed speech, and a call passing
`1000000000` sits beside a turn saying *một tỷ*. A confirmation reads the numbered spans back, one
at a time, and only what it confirms reaches the reviewer. What happens to the claims afterwards is
the arithmetic the personal-data step already runs — the same containment rule, the same tick per
place, the same replacement, the same outcome — with one exception that is the heart of this step:
**a placeholder is numbered per slot and not per value**, so *một tỷ* and `1000000000` wear the one
name and can only be re-filled together.

**The act.** From that slotted sample, a model writes **one** new conversation using the same
catalog and the same slots. The reviewer edits it, runs the three cards over it, ticks its facets,
and one Submit writes the source and every generated conversation — **one row each**, never a row
holding a list of conversations.

What is *not* here: filling the slots back in. This step makes a corpus fillable; multiplying it is
somebody else's program reading the exported file, and § *Out of Scope* says so.

## Context

### What is already true, measured

Taken on 2026-09-28 at `21edf7d`, over `tool_decision_dataset` — 40 stored rows.

- The `personal_data` facet carries **32 distinct kinds**. Three of them (`EMAIL`, `NAME`, `PHONE`)
  are kinds a rule scan declares. **Twelve** are shaped `<TOOL>__<ARG>`. The rest —
  `CAR_PRICE`, `DOWN_PAYMENT`, `INTEREST_RATE`, `LOAN_TERM`, `WEIGHT`, `DELIVERY_OPTION` — are
  argument values too, named without the prefix.
- Of the twelve, eleven name a tool standing in that row's own catalog and one of that tool's own
  arguments. The twelfth, `SEARCH_PLACE_27D__DISTRICT_LOCATION`, names the tool and an argument
  it does not have — and **that one is the interesting one, because it is deliberate and it is the
  pattern.** The argument is `location`; the turn said a district and not the whole location, so
  the reviewer wrote a qualifier in front of the argument's name. The same row carries
  `SEARCH_PLACE_27D__LOCATION` beside it, and the two are one argument mentioned two ways. The
  corpus holds the same move on the personal-data side: `WRONG_PHONE` and `WRONG_ID_NUMBER` are a
  phone number and an ID the customer said incorrectly, filed so that the class **reads and is
  understood without opening the row**.
- So a class is not always `<TOOL>__<ARG>`, and the step is not always a search. A conversation
  mentions an argument's value in part (`PART_PHONE_NUMBER`), wrongly (`ERROR_PHONE_NUMBER`), or
  as one component of it (`DISTRICT_LOCATION`) — and none of those three stands in the record
  character for character beside the value the call passed. **Nothing that only searches for the
  argument's value can find them**, which is why this step has two detectors and not one.
- Inside the calls themselves, **31 of 44 argument values already stand as a slot placeholder** and
  13 are still bare. Thirty of the 40 rows carry no bare argument value at all.
- The placeholders for those kinds stand under `messages` 23 times and under `label` 6 times, and
  under `tools` never.
- **Of the 13 bare values a verbatim search finds 7 and misses 6.** Five of the six are `faq_code`
  — `gia_thiet_bi`, `thoi_gian_lap_dat`, `bao_hanh` — an enum slug nobody utters: the turn asks
  *giá thiết bị bao nhiêu* and the call passes the code for it. The sixth is
  `nationality: Việt Nam`. So the search reaches a little over half of what is left to reach, and
  what it misses it misses completely rather than narrowly.
- **The corpus is speech, and that is what decides the detectors.** Row `b81aac81` calls
  `SvcCalculateinterest(principal_amount=1000000000, interest_rate=7.5, time_period=10)` over a
  turn reading *anh vay một tỷ lãi suất bảy phẩy năm một năm trong vòng mười năm*. Not one of the
  three values stands in the conversation as a single character of itself. A step that only
  searched would be blind to every number this corpus says out loud, which is most of its
  arguments.

**And the same row settles what a placeholder is.** This is what the reviewer left, by hand:

```
messages.4   anh vay <SVCCALCULATEINTEREST__PRINCIPAL_AMOUNT_1> lãi suất …
  the call   {"principal_amount": <SVCCALCULATEINTEREST__PRINCIPAL_AMOUNT_1>, …}
```

`một tỷ` and `1000000000` share no character, and the reviewer gave them **one placeholder**. Card
1's arithmetic cannot produce that — `name_placeholders` keys by value, so two distinct values are
two distinct names, always. The reviewer is right and that arithmetic is wrong for this step:
whatever re-fills that slot has to move the words in the turn and the number in the call together,
to the same amount. Two names are two things a filler can set apart, and a conversation saying
*một tỷ* while its own call passes `3000000000` is the one defect this step exists to prevent.

So the step specified here is one a reviewer has already been performing **by hand**, through card
1's *Offer this kind* box, on three quarters of the corpus. This does not invent a practice; it
gives one that exists a step of its own, a scan that proposes instead of a box that is typed into,
and a facet that does not count an interest rate as personal data.

**Six rows carry the consequence today** — a kind on `personal_data` that is a scale kind:

| row | the kinds |
|---|---|
| `cab00d87…` | `CAR_PRICE`, `DOWN_PAYMENT`, `INTEREST_RATE`, `LOAN_TERM` |
| `f448ebb7…` | `DELIVERY_OPTION`, `WEIGHT` |
| `fa519155…` | `SVC_TRACKFITNESSPROGRESS_1D6__ACTIVITY`, `…__CALORIES_BURNED`, `…__DURATION` |
| `1722d009…` | `CALCULATE_DELIVERY_COST_9E8__DELIVERY_OPTION`, `…__WEIGHT` |
| `b81aac81…` | `SVCCALCULATEINTEREST__INTEREST_RATE`, `…__PRINCIPAL_AMOUNT`, `…__TIME_PERIOD`, `SVCGETCONTACTINFO__NAME` |
| `d0d01db5…` | `SEARCH_PLACE_27D__DISTRICT_LOCATION`, `…__LOCATION`, `…__NAME` |

### What the code already has

The arithmetic. `profile/tool_decision/data_quality.py` holds nine functions that are about
*values, classes and spans* and mention personal data only in a field name:
`walk_record_strings`, `find_spans_in_text`, `name_placeholders`, `find_and_number_spans`,
`replace_spans_in_text`, `replace_node`, `group_spans_by_path`, `order_claims_by_class`,
`decide_replacement_outcome`. None of them is a judgement about a value; every one is a fact about
where a string stands in a document, and both steps need all nine. `C-7` — *do not split before a
second consumer needs half of it* — is why they move into a module of their own now and did not
before.

**What this step does not already have is the two detectors in front of them, and those are its
own.** Reading a settled label's arguments back into a conversation, spotting a mention that shares
no characters with the value, and naming a class a person can read at a glance are three questions
nothing in `data_quality/` asks or should learn to.

## Requirements

### The step

1. **Scaling is a step of its own and it runs after the label is settled.** Measured: a slot
   placeholder stands inside `label` 6 times across the corpus, against 23 times inside `messages`
   — and the label is what card 2 is for. A scan run before the reviewer settled the label would
   read a call they were about to replace.
2. **Two detectors over the same text — a model and a rule scan.** The same shape the
   personal-data step has, for a different reason and in the opposite proportion.
   - **The model is the larger half, and § *Context* measures why.** A turn says *một tỷ* where the
     call passes `1000000000`, says half the phone number, says it wrongly, or says a district out
     of a longer location. In each of those the turn holds the argument and holds none of its
     characters in a row, so a search finds nothing. This corpus is transcribed speech: the spoken
     form of a number and its written form share nothing at all, which makes the model not a
     supplement here but where most of the answer comes from.
   - **The rule scan is the label read back into the conversation**, kept for what it is certain
     about. It takes the argument values the settled label and the turns' own calls carry — values
     the reviewer has already looked at on card 2 — and searches for each one verbatim. Where a
     value *is* spelled out there is nothing for a model to be wrong about, and the measurement
     puts that at 7 of the 13 places left to find.

   **The two are not unioned afterwards; the model answers into the slots the search opened.** The
   rule scan is what decides a slot exists, because a slot is an argument of a call and only a call
   can say so. The model adds values to one, or opens a qualified one beside it, and can do neither
   out of nothing — so there is no overlap to settle and no class for the two to disagree about.
   The model picker travels with card 3's button, like every other check's.
3. **Neither detector answers an offset.** A detector answers a value and the slot it belongs to;
   where that value stands, how many times, which nested span is dropped and which `<CLASS_N>` it
   gets are found by searching afterwards, through the one function that does it for both steps. A model counting
   characters is a model nothing here can check, and a value it did not copy character for
   character out of the text it was shown is dropped, because no offset can be found for it. This
   is what puts a `start` and an `end` on every row of card 3's table whichever detector claimed
   it — the reviewer reads one table and cannot tell, which is the point.
4. **A confirmation is asked over the numbered spans, span by span.** The same second pass the
   personal-data step makes, and it is what sets the precision: only a span it confirms reaches
   card 3, and each one carries the reason it was confirmed for. It is asked per span because the
   same characters are an argument's value in one line and a coincidence in the next — `2` the
   loan term and `2` in *2 người* — and a detector cannot tell them apart while a reader of the
   line can. It **only ever narrows**: an id no span carries is discarded, a span answered twice
   keeps the first answer, and a span nothing came back about is not confirmed, which is what a
   failed call and an answer of the wrong shape both come to. Nothing detected is nobody asked.
5. **Both steps read the sample as it arrived, and their spans meet only at approval.** Scaling
   does not read what card 1 redacted. A partial mention is recognisable only beside the value it
   is a partial mention of — the corpus holds `WRONG_PHONE` in one turn and the full `PHONE` two
   turns later, as different characters in different places — and a scale detector handed
   `<PHONE_1>` has had the one thing it needed to compare against taken away. Reading the raw text
   is what a detector does: `pii_llm_detect` already does it, and the prohibition labelling-ui
   states is about a juror and about the generator, not about a scan.

   So the two produce two independent span sets over one frame of reference, and `POST /redact` is
   handed both at once. Where they claim the same `(path, start, end)`, **scale wins** — a value
   that is an argument is filed as the argument. Where they overlap without matching, containment
   has already run and the longer span took the place; that is the rule as it stands, and it is
   what stops a scale span shorter than a personal-data span from leaving a tail of a confirmed
   value standing in the clear. **Priority settles a tie. It does not overrule containment.**
6. **After the claims the arithmetic is card 1's and it is the same code — except the numbering.**
   One span per occurrence over the whole record, a span inside a longer span dropped, a tick per
   place, replacement from the highest offset down, and `outcome` measured by counting placeholders
   in the string each span's `path` names. None of those is a decision that can differ between the
   two steps — they are facts about where a string stands in a document — and a second spelling of
   any of them would be the two rotting apart (`T-6`).

   **The numbering does differ, and it is the heart of this step: a placeholder is per slot, not
   per value.** A slot is one `(call, argument)` pair, and the values it owns are the value the
   call spells out together with every mention a detector found of it. All of them get the one
   `<CLASS_N>`. Card 1 numbers per value because two spellings of a name are two names and nothing
   binds them; card 3 numbers per slot because *một tỷ* and `1000000000` are one amount and
   everything binds them — whatever re-fills that slot has to move both, to the same number, or it
   writes a conversation that contradicts its own call. `<CLASS_N>` still counts per class in claim
   order, so one tool called twice with two amounts gets `_1` and `_2`, two slots and two names;
   and a value two slots both own keeps the first, which is the rule the reviewer overrules on the
   row.

   **What may differ above them is everything else**, and § *Design* draws the line.

### What is claimed

7. **The rule scan claims every argument value of every call the sample makes**, read from
   `messages[*].tool_calls[*]` and from the label as it ships. Both spellings of a call are read,
   the corpus's `{name, arguments}` and the provider's
   `{function: {name, arguments: "<json text>"}}`, through `read_named_function` — the reader
   `utils.py` already owns, so what a call *is* stays defined once. The label is read **as the
   reviewer settled it on card 2**, not as it arrived, which is the other half of the rule putting
   this step after the label. Each call-and-argument is one slot; the value the call spells out is
   that slot's first value, and the model's mentions join it.
8. **The model is asked one question per slot: where does this conversation mean this argument?**
   It is handed the review text, the slots the rule scan read — tool, argument and the value the
   call passed — **and the catalog**, and answers with the stretches of the conversation that mean
   one of them, each naming the slot it belongs to and carrying the reason written before it.
   **An answer either joins a slot or qualifies one, and it can do nothing else.** It *joins*
   where the stretch is the argument's own value said another way — *một tỷ* for `1000000000` —
   and then it is one more value of that slot, wearing the slot's one placeholder. It *qualifies*
   where the stretch is a different string that the argument's value explains: half a phone
   number, a number said wrongly, one district out of a longer location. A qualified mention opens
   **its own** slot, under `<TOOL>__<QUALIFIER>_<ARG>`, because it is not that value and whatever
   re-fills it has to put something else there.

   The corpus holds both sides of this, which is how the line was drawn:
   `SEARCH_PLACE_27D__LOCATION` and `SEARCH_PLACE_27D__DISTRICT_LOCATION` stand beside each other
   as two slots on one argument, while *một tỷ* and `1000000000` stand inside one. So the model
   never writes a class out of nothing — it answers a slot id, and optionally a qualifier — and
   the reviewer overrules either on the row.
   **The catalog is what makes the qualifier a reading rather than a guess.** `time_period` is
   described as *đơn vị tính là năm*, `principal_amount` as *format thuần số, đơn vị VND* — so a
   model shown the argument's own description can say *this turn gave months where the argument
   takes years* and name it, where one shown the value alone can only say the two strings differ.
   The risk is the mirror of that: an argument described at length invites a model to invent
   categories nobody asked for, so the prompt names the three qualifiers the corpus uses and says
   a fourth needs a reason. The reviewer overrules either way — the class picker on every row is
   the same control card 1 has.
9. **The class is `<TOOL>__<ARG>`, and a qualifier goes in front of the argument.** Each part is
   upper-cased with runs of whitespace written as `_`, which is the rule `namedKind` already
   applies to a kind a reviewer types; the tool name is the catalog's own spelling upper-cased,
   which is why `SEARCH_PLACE_27d` files as `SEARCH_PLACE_27D`. A mention that is not the whole
   value carries a word saying which — `<TOOL>__PART_<ARG>`, `<TOOL>__WRONG_<ARG>`,
   `<TOOL>__DISTRICT_<ARG>` — **so that the class reads and is understood without opening the
   row**, which is the reason the reviewer has been writing them that way. The qualifier is the
   model's to propose and the reviewer's to overrule; no rule reading the catalog could have
   invented one, and none tries.
10. **A value that is both personal data and an argument is claimed by both steps, and scale wins
    the place.** A customer's name passed as `SvcGetcontactinfo(name=…)` is personal data *and* an
    argument. Both detectors read the raw name, both claim it, and both answer a span at the same
    `(path, start, end)`. At `POST /redact` the scale span is the one applied, so what ships is
    `<SVCGETCONTACTINFO__NAME_1>` — exactly what the corpus already holds. There is no re-filing
    and no second pass: the personal-data span was never applied, so nothing has to be undone.

    **The superseded personal-data span is dropped from the `personal_data` key**, because it did
    not happen. The corpus settles this too. Row `b81aac81` ships the name as
    `<SVCGETCONTACTINFO__NAME_1>` and its facet reads `SVCCALCULATEINTEREST__INTEREST_RATE`,
    `SVCCALCULATEINTEREST__PRINCIPAL_AMOUNT`, `SVCCALCULATEINTEREST__TIME_PERIOD`,
    `SVCGETCONTACTINFO__NAME` — the argument classes and no `NAME` beside them. The cost, stated
    once: *which rows held a customer's name* stops being a question the `personal_data` facet
    answers and becomes one only `tool_decision_record` can, off the claims the detector made.
    That is a reporting loss and not a de-identification one — the name is out of what ships either
    way, under whichever name.
11. **A value is claimed only where it stands character for character** — for the rule scan, and
    for the model, whose answer is dropped where it did not copy what it saw. `arguments` is JSON
    *text*, so a value holding a quote, a backslash or a newline is spelled one way inside the call
    and another way in the turn that said it, and the search claims it at the second and not the
    first. This is the same disagreement the pipeline spec measures for `review_text`
    (`Nguyễn "Nam" Văn`, twice in the record and once in the text), read from the argument side. It
    is stated rather than fixed, and under slot numbering it costs less than it did: the two
    spellings are two values of **one** slot, so claiming both is one line and the place that was
    missing comes back under the same `<CLASS_N>`. What stays true is that nothing searches for a
    spelling nobody claimed.
12. **A short value is claimed at every word boundary it stands on.** `time_period: 2` claims each
    standalone `2` in the conversation and not the `2` inside `12`. Nothing narrows it, because
    nothing here can tell the two apart; **the tick per place is the answer**, and it is the same
    answer card 1 gives for `Nam` the given name beside `miền Nam`.
13. **The reviewer's three acts are card 1's three acts**, for the same reason and with the same
    words: re-file a value under another kind, name a kind neither detector proposed, and retype
    what a value stands in for. The corpus already shows why the second is needed —
    `SEARCH_PLACE_27D__LOCATION` and `SEARCH_PLACE_27D__DISTRICT_LOCATION` are one argument whose
    two mentions a reviewer chose to keep apart.

### The generation

14. **One press writes one conversation.** How many a reviewer wants is how many times they press.
    The route answers a conversation and never a list, so nothing anywhere holds *a batch of
    generated samples* as a shape.
15. **The prompt is a template in a box, and the service fills its slots.** The box opens holding
    the deployment's own file; the reviewer may edit every word of it. Whatever stands in the box
    when the button is pressed is filled with `{language}`, `{tools}`, `{conversation}` and
    `{slots}` by the same `slot_filling` every other prompt goes through. A slot the reviewer
    deleted is a fact the model is not told — that is theirs to do, and it is not an error.
    **This is also how two generations are made to differ.** Nothing here tells the second press
    about the first, and nothing tries: the box is edited between presses, which is a reviewer
    steering a corpus rather than a rule guessing at what variety means. A page that appended
    *and do not repeat yourself* would be inventing the one judgement this step exists to keep
    with the person.
16. **The catalog is not generated.** The new conversation offers the source's `tools`, verbatim.
    The point of the act is another conversation *for these tools*, so asking a model to invent a
    catalog would be asking it to invent the thing being held constant.
17. **The label is not generated either.** The model writes turns; what the last turn should call
    is what card 2 exists to settle, and a generated label arriving pre-settled is the panel's
    answer wearing the reviewer's name. The draft opens with the source's label on card 2's form,
    which is where a reviewer edits one already.
18. **A generated conversation is editable. An imported one is not.** The prohibition card 2 states
    — *a page that let a reviewer retype the turns is a page that can quietly make the sample agree
    with the label* — is about a conversation that **arrived**: it is evidence, and evidence is not
    edited. A generated conversation is not evidence. It is a draft the reviewer is authoring, and
    the label is settled from it afterwards rather than beside it. This rewrites a passage of
    `docs/labelling-ui/spec.md`; § *What this rewrites* says which.
19. **The generation is asked with the slotted, redacted sample and nothing else.** This is
    labelling-ui Requirement 20 read one step further along: a juror reads `<EMAIL_1>` and writes
    `<EMAIL_1>`, and a generator reads `<…PRINCIPAL_AMOUNT_1>` and writes it back. A model that had
    been shown the raw values would write raw values into a conversation nobody scanned.
20. **A generated conversation is a sample like any other.** It runs cards 1, 2 and 3 on its own
    and is stored under its own name. It has to: the store refuses a record whose `personal_data`
    is null, and a model asked to write a conversation about a customer will write a phone number
    into it whether or not the slots it was given held one.
21. **What the model wrote that will not read as turns is carried, never guessed at.** Same rule as
    a label the human typed that is not JSON: the text comes back beside an empty conversation, the
    reviewer sees what was said, and nothing is invented to fill the gap.

### The record

22. **`scale` is one more key on the record** — `ScaledValues`, what the step answered and how far
    replacing got, declared beside `ScannedPersonalData` and shaped like it without being it.
    Nothing else about the record moves, and a record written before this step reads back
    unchanged.
23. **`scale` is optional where `personal_data` is mandatory, and checked identically where it is
    there.** `personal_data: null` is refused because de-identification is a legal obligation the
    `dataset` table has to be able to prove; nobody has an obligation to scale anything, so
    `scale: null` is a record that skipped an optional step and stores fine. But a `scale` that
    *exists* and names a span whose placeholder is not standing where it says it stands is a record
    lying about itself, and that is refused in the same sentence and by the same function.
24. **`scale` is a facet, and it is a key in `notes` rather than a column.** It is computed from the
    step's spans exactly as `personal_data` is, lands in `notes` because it is not in
    `ToolDecisionSample.FACETS`, and is therefore counted by `count_by_note`, charted by the dataset
    sheet and readable on an opened row **with no schema change and no migration at all**. Making
    it a column later is one line in `FACETS` plus a rebuild of a derived table; making it a column
    now is that migration with nothing yet asking for it (`T-1`).
25. **The personal-data precondition is not touched, and that is the merge paying for itself.**
    `build_sample` refuses a record where a confirmed personal-data span's placeholder is not
    standing in the string its path names. A span scale won is not in `personal_data.spans` at all
    — the step that lost the place does not record that it happened — so there is no placeholder
    for the check to go looking for, and no record is refused for a reason that is not about it.
    `find_surviving_spans`, `read_scanned_personal_data` and `find_claims_gained` are untouched by
    this spec, and a record with no `scale` key reads exactly as it reads today. § *Design* says
    what the chained alternative would have cost here.
26. **A generated row's `scale` is not empty, and that is how the corpus stays readable across a
    generation.** A conversation generated from slots carries slots as its argument values, so the
    rule scan opens a slot holding `<SVCCALCULATEINTEREST__PRINCIPAL_AMOUNT_1>` and finds it in the
    turns that say it; the class it names is the one the placeholder already wears, and replacing
    it is the identity.
    The facet therefore names the slots the row carries, the same as its parent's, and a corpus
    reader asking *which rows carry `SVCCALCULATEINTEREST__PRINCIPAL_AMOUNT`* gets both. A
    generated row carrying a class its parent did not is one where the model invented a fresh
    value instead of reusing the slot, and the reviewer is looking straight at it.
27. **The six rows listed in § *Context* are re-reviewed by hand.** Re-opening one from the samples
    list and saving it writes the same key, so the row is replaced rather than duplicated, and its
    argument kinds move from `personal_data` to `scale`. No backfill is written: a rule that moved
    every `<TOOL>__<ARG>`-shaped kind would still leave `CAR_PRICE`, `WEIGHT` and `LOAN_TERM` where
    they are, so the automatic half of the job is the half that is not worth having.

### The screen

28. **Card 3, headed by its question, under card 2.** *Which values should this sample vary?* — the
    labelling-ui rule that a decision is a card headed by its question, and the order is the order
    the work happens in.
29. **One drawing of the keep table, used twice.** The seven columns, the tick per place, the kind
    picker on every row, the placeholder box and its two refusals are one behaviour; two copies
    would be the first screen where unticking a row meant two different things. The drawing takes
    the ids it writes into, so each card still owns its own ids and `ui/` Requirement 4 holds.
30. **The extraction lands first, with the screen frozen.** `tests/ui/page.js` passes unedited
    across the commit that moves the table drawing out of `personal-data.js`. That is the whole
    evidence that card 1 did not change while being made reusable, and there is no other way to
    get it — the repository's own rule, applied again.
31. **The generation box is a text area, a picker and one button**, and it is at the foot of card 3
    because that is where the reviewer is standing the moment the slots are approved.
32. **The generated conversations stand in a list under the box, and one Submit writes all of
    them.** The reviewer opens one, works it through the three cards, ticks its facets, and comes
    back; the list says which are finished and which are not. Submit posts **one `POST /records`
    per conversation**, the source first. Each says its own outcome on its own line. A refusal
    stops nothing already written, and re-pressing Submit rewrites the same keys rather than making
    second rows — which is what makes fixing one draft and saving again safe.
33. **A draft lives on the page and nowhere else.** Closing the tab loses every conversation
    generated and not yet stored, and the page says so beside the list rather than leaving it to be
    discovered. Making a draft survive a reload is a second store for a thing that already has one,
    and § *Open* is where it waits.

### The routes

34. **`POST /spans` and `POST /redact` move out from under `/data-quality/personal-data/`.** Neither
    is about personal data: one answers where a set of `(class, value)` claims stand in a record,
    the other replaces every handed-back span in one. Two steps now use both, and a URL saying
    *personal-data* while the scale card posts to it is a name that would have to be explained
    every time it is read. The page is the only client, and nothing stored carries either path.
35. **`POST /data-scale/values`** — the new route on the masking half. A sample, a language and the
    model that reads it; a `ScaleDetected` back, so card 3 can paint the moment it returns. A model
    name this deployment does not serve is 422 before anything is asked, like every other
    model-taking route.
36. **`POST /data-scale/conversation`** — one sample, one prompt, one model name, one language; one
    conversation back.
37. **`GET /data-scale/prompt`** — the deployment's template, unfilled, so the box can open holding
    it. It answers the file and never a filled prompt, so nothing a sample carries passes through
    it.

## Design

### The modules

| file | tag | holds |
|---|---|---|
| `profile/tool_decision/schema.py` | `shape` | gains `PlacedValue`, the carrier the arithmetic answers with |
| `profile/tool_decision/span_arithmetic.py` | `logic` | eight of the nine functions § *Context* lists, plus `keep_winning_spans`; moved out of `data_quality.py` and owned by neither step |
| `modalities/text2text/data_scale/schema.py` | `shape` | `ScaleSpan`, `ScaleDetected`, `ScaleRedacted`, `ScaleScanningConfig`, `ScaleScanningInput`, `ScaleLlmDetected` |
| `modalities/text2text/data_scale/argument_scaling.py` | `logic` | `ValueScaling` — the socket `detect`, and the model detector's body |
| `profile/tool_decision/data_scale.py` | `logic` | `read_argument_slots`, `name_argument_class`, `name_slot_placeholders`, the three prompts, `ToolDecisionValueScaling`, `ConversationGenerator` |
| `services/tool_decision/data_scale.py` | `logic` | one function per endpoint |
| `modalities/.../dataset_management/schema.py` | `shape` | `ScaledValues` beside `ScannedPersonalData` |
| `modalities/.../dataset_management/sample_building.py` | `logic` | the optional half of the precondition — `scale: null` stores, a `scale` that lies does not |
| `ui/spans.js` | `adapter` | the keep table, drawn into the ids it is handed |
| `ui/scale.js` | `adapter` | card 3's values: `scale-table`, `scale-verdict`, `run-scale`, … |
| `ui/generating.js` | `adapter` | the box and the drafts: `gen-prompt`, `gen-run`, `gen-list`, … |

**`data_scale/` is its own package under `modalities/`, and this is the reviewer's decision rather
than a reading of the rules.** The argument for sharing is that scaling's shapes are
personal-data's shapes with one field renamed. The argument that wins is the one that says these
two will not stay alike: **a value being personal data and a value being worth varying are
different questions about different sets** — an interest rate is one and not the other, a
customer's name is both, and the two steps will grow apart at the detector, at the prompt, at
whether a confirmation is asked and at what a class is allowed to be called. A shape shared because
it is identical today is a shape two features have to agree about tomorrow. The cost, stated once:
six field declarations and three model classes exist twice, and the check that keeps them honest is
that neither copy holds a rule — only nouns.

**What is *not* duplicated is the arithmetic, and that is the line.** Where a value stands in a
document, which nested span is dropped, how `<CLASS_N>` is numbered and how a span is replaced are
facts about strings, not judgements about values: they cannot diverge, so a second copy would only
ever be the wrong one (`T-6`). They move to `profile/tool_decision/span_arithmetic.py`, imported by
`data_quality.py` and `data_scale.py` alike, owned by neither. The name says what is in the file:
offsets and counting, no judgement about what a value *is*. `value_spans` was the earlier name and
said too little — every span in this repository is a span of a value.

**One function does not move, because it is the one that differs.** `name_placeholders` keys by
value and belongs to card 1. `find_and_number_spans` therefore takes the placeholder map as an
argument instead of building it:

```python
def find_and_number_spans(
    record: Mapping[str, Any],
    detected: Sequence[tuple[str, str]],
    placeholders: Mapping[str, str],
) -> tuple[PlacedValue, ...]: ...
```

One parameter wider, and it is the right parameter: *which name a value wears* is exactly the
decision the two steps make differently, so handing it in is the seam rather than a leak through
one. Card 1 passes `name_placeholders(detected)`; card 3 passes `name_slot_placeholders(slots)`.
Everything downstream — `find_spans_in_text`, the containment drop, `replace_spans_in_text`,
`decide_replacement_outcome` — reads a `Mapping[str, str]` from value to placeholder and cannot
tell which built it. That the mapping is injective for one step and not for the other is a fact
about the mapping and about nothing else.

**No base shape, no alias, and no new folder.** An earlier draft declared a `ValueSpan` under
`modalities/` that both span shapes extended, each aliasing `value_class` to its own wire name.
That bought one thing — a field the shared arithmetic could read — and cost a module in the generic
layer, an inheritance both steps have to agree about, and an alias a reader has to know is an
alias. It is cheaper to have the arithmetic answer a carrier instead:

```python
class PlacedValue(NamedTuple):      # profile/tool_decision/schema.py, already tagged `shape`
    path: tuple[str | int, ...]
    start: int
    end: int
    value_class: str
    placeholder: str
```

`find_spans_in_text` answers `PlacedValue`, and each step builds its own span out of one —
`PersonalDataSpan(personal_data_class=…)`, `ScaleSpan(scale_class=…)`. The two span shapes are then
fully independent, neither names the other, and **`personal_data_class` stays the field it has
always been**: nothing moves in the 102 places the key stands across the 40 documents of
`tool_decision_record`, and nothing moves on the wire. `PlacedValue` never leaves
`profile/tool_decision/`, which is why it needs no module in `modalities/` and no folder of its
own — `T-2` decides the boundary and cuts the file late, and a second text2text task wanting this
arithmetic is what would move both files up together.

### The claims

```python
def name_argument_class(tool: str, argument: str, qualifier: str = "") -> str:
    """`<TOOL>__<ARG>`, or `<TOOL>__<QUALIFIER>_<ARG>` where a mention is not the whole value.

    Each part upper-cased with runs of whitespace written as `_` -- the rule the page applies to a
    kind a reviewer types, so a class a detector proposes and a class a reviewer types are one
    spelling and not two.
    """

class ArgumentSlot(NamedTuple):
    """One `(call, argument)` pair and every way the sample spells its value."""

    value_class: str
    values: tuple[str, ...]


def read_argument_slots(sample: Mapping[str, Any]) -> tuple[ArgumentSlot, ...]:
    """One slot per argument of every call the sample makes, in the order the calls stand.

    Every call in `messages` and every call in `label` as it ships, both spellings, through
    `read_named_function`. The slot opens holding one value, the one the call spells out; an empty
    value opens no slot, because it can carry no offset. A value two slots both pass stays with the
    first, and the reviewer re-files it on the row where that is wrong.
    """


def name_slot_placeholders(
    text: str, slots: Sequence[ArgumentSlot]
) -> Mapping[str, str]:
    """Every value of a slot mapped to the slot's one `<CLASS_N>`.

    `<CLASS_N>` counts per class, slots ordered by where their earliest value first stands in
    `text` -- the same ordering rule `order_claims_by_class` applies to card 1's claims, read one
    level up because here the thing being ordered is a slot and not a value.

    This is the one place the two steps' arithmetic differs, and the difference is the whole point:
    `name_placeholders` is injective and this is not. *một tỷ* and `1000000000` come back wearing
    one name, so nothing can re-fill them apart.
    """
```

The model detector sends `config/prompts/profiles/tool_decision/argument_scale_detect.txt` — the
task's own file, beside `pii_llm_detect.txt` and on the same terms, `ConfigError` where it is
missing. Four slots: `{language}`, `{review_text}`, `{tools}` (through `convert_tools_to_text`, so
the model reads the catalog the reviewer reads and not a second rendering of it), and
`{slots}`, one `id | tool | argument | value` per line the way `build_pii_llm_confirm_prompt`
writes its spans. It answers `ScaleLlmDetected` — a `{reason, text, slot}` per mention, the reason
written before the value, which is the rule every model answer on this flow follows. **`slot` is
an id off the lines it was shown, never a class the model wrote**: a mention is a value of a slot
that already exists, and a model free to name one would be free to name a second placeholder for
the amount the call already passed. A `slot` no line carries is dropped. `text` must be copied out
of the review text character for character or the claim is dropped too, because that is the string
an offset is searched in.

The model's mentions join the slots the rule scan opened — each one appended to the slot its `slot`
id names — so the union happens on the slot and not after it, and a value the rule scan already
holds is not added twice. The filled slots then go to `name_slot_placeholders` and to the same
`find_and_number_spans` the other step uses. No class is declared for this step, so every scale class orders after the declared
ones in first-claim order — which is already what happens to a kind a reviewer types today.

The confirmation sends `argument_scale_confirm.txt` — **the task's own file and not the modality's,
which is where it differs from the personal-data one.** `pii_llm_confirm.txt` lives under
`modalities/` because *whether a value is personal data* is a question about personal data and
nothing else; *whether this stretch is a mention of that argument* is a question about a tool call,
so it sits with the code that asks it. Three slots — `{language}`, `{review_text}` and `{spans}`,
one `id | CLASS | value` per line — and it answers one `{id, reason, confirmed}` per span it was
shown, read back through the same narrowing rule.

### The merge, and what it saves the precondition

The two span sets meet in one function, and it is the only new arithmetic the merge needs:

```python
def keep_winning_spans(
    yielding: Sequence[PlacedValue], winning: Sequence[PlacedValue]
) -> tuple[tuple[PlacedValue, ...], tuple[PlacedValue, ...]]:
    """The two sets with every place settled, in the order they were handed in.

    Containment runs over the union, so the longer span takes a place it encloses -- that rule is
    unchanged and it runs *before* the tie-break, which is what stops a short span from leaving a
    tail of a longer confirmed value standing. Only then does a tie settle: at one
    `(path, start, end)` the span from `winning` stays and the one from `yielding` is dropped out
    of the set it came from, because it is not what ships there and the record must not say it was.
    """
```

**The function takes no view on which set wins**, which is why it sits in `span_arithmetic.py` with
the rest: *a longer span encloses a shorter one* is a fact about strings, and *the scale step wins
a tie* is a judgement this task makes. `services/tool_decision/data_scale.py` is where the two meet
— it calls `keep_winning_spans(personal_data_spans, scale_spans)` and that argument order **is**
the judgement, written once, at the only place that holds both sets.

`POST /redact` applies the union; the two sets come back separately so each key reports its own
`outcome` against the one redacted document.

**And this is the merge paying for itself: the store's precondition needs nothing added.**
`build_sample` refuses a record where a confirmed personal-data span's placeholder is not standing
in the string its path names. An earlier draft of this spec had the two steps *chain* — card 1
redacts, card 3 claims `<NAME_1>` and re-files it as `<SVCGETCONTACTINFO__NAME_1>` — and under that
design the check would refuse **every row where a customer's name is also an argument**, which is
the commonest row this corpus holds. Repairing it took a new function in `sample_building.py` whose
whole job was to read one step's spans in order to explain the other's. Merging removes the
problem instead of the symptom: a span scale won is not in `personal_data.spans` at all, so there
is no placeholder to go looking for. `find_surviving_spans`, `read_scanned_personal_data` and
`find_claims_gained` are untouched by this spec.

### The generation

`config/prompts/profiles/tool_decision/conversation_generation.txt`, on the same terms as the other
four: the deployment's file, read from the working directory, `ConfigError` where it is missing or
empty. It is the one prompt in this repository a reviewer edits, and the box holds the template
rather than a filled one, so the sample can never be pasted into it by hand. Four slots — `{language}`, `{tools}` (through `convert_tools_to_text`), `{conversation}`
(through `list_conversation_turns`) and `{slots}` (one `<CLASS_N> — what it stands for` per line,
read off the step's own spans).

`ConversationGenerator` is built the way `ToolPredictor` and `PiiLlmDetector` are: `resolve_config`
at construction, `ConfigError` before any record where the name resolves to no endpoint, `complete`
to ask, one declared shape read back, and a failed call is one structured event on stdout and an
empty answer — never a raise (`H-6`).

### The order

Four landings, and each of the first three is usable on its own.

1. **The extraction, with nothing new on the screen and nothing new in the API.** The nine
   functions move to `profile/tool_decision/span_arithmetic.py` and answer `PlacedValue`;
   `find_and_number_spans` takes its placeholder map as an argument and `data_quality.py` passes
   `name_placeholders(detected)` into it; `ui/spans.js` takes the keep-table drawing and
   `held` grows a bucket per step so two cards can hold their own `claimed`, `keeps` and `stands`.
   **Every existing test passes unedited** — `tests/ui/page.js`, `tests/ui/reading.js`,
   `tests/profile/test_personal_data.py`, `tests/edge/test_endpoints.py`. That is the whole
   evidence that the personal-data step was made shareable without being changed, and there is no
   other way to get it. A commit that moves and edits in one proves neither.
2. **The rule half of the scan.** `data_scale/` lands with its shapes and its socket,
   `read_argument_slots` and `name_slot_placeholders` answer it, `POST /data-scale/values` runs the
   search alone, `keep_winning_spans` settles the two sets at `POST /redact`, card 3 appears, and
   `scale` joins the record and the facet. **The merge lands here rather than later**, because two
   span sets meeting is the thing the redaction route does and it cannot be added to it afterwards
   without changing an answer a reviewer has already read. What this landing does *not* yet reach
   is most of the slots: § *Context* measures the search finding 7 of 13, so card 3 is honest and
   thin until the next landing.
3. **The model half of the scan.** Two prompt files, the detector, the confirmation, the model
   picker on card 3's button. It goes third because a scan that answers without a model is a scan
   whose search half can be proved on its own — and because a table full of rule-scan rows is what
   makes a wrong model row visible. Within this landing the detector lands before the
   confirmation, for the same reason again: a confirmation is only readable against claims
   somebody has already looked at.
4. **The generation.** The second prompt file, the two routes, the box, the drafts, and Submit
   writing more than one record. This is where the page grows a list where it held one sample, and
   it is the only part of this spec that touches `app.js`'s `openSample` and `forgetEverything`.

## Decisions

1. **Scaling is its own module with its own functions, and shares all the arithmetic but one.** The
   reviewer's call, and the reason is the one that matters: personal data and scalable values are
   different sets of values answering different questions, so the two steps will change
   separately. An earlier draft of this spec had scaling import the personal-data shapes and call
   `detect_personal_data`'s composition; that would have made every later change to one of them a
   change to both, and the first such change is already visible — scaling wants a qualifier in a
   class name and personal data does not. Alternative: share everything and split when it hurts.
   Rejected because the splitting is what would then be expensive, and because a shared shape is a
   standing invitation to put a scale rule inside a personal-data function. The cost is stated in
   § *Design*: six field declarations and three model classes written twice, with no rule in
   either copy. The one arithmetic function that is **not** shared is `name_placeholders`, and
   that is not a concession, and the decision below headed *a placeholder is numbered per slot*
   says why.
2. **`scale` is a note and stays one.** Settled by the reviewer, not deferred. A column is one
   SQLite will not add to an existing table, so it costs dropping `tool_decision_dataset` and
   rebuilding it from `tool_decision_record`, for which no command exists — and it buys two things
   nobody wants: a column on the rows table of the dataset sheet, and a place on an axis of the
   joint matrix. As a note it is counted by `count_by_note`, charted by the dataset sheet and
   readable on an opened row, for nothing. `direction` and `have_conversation_flow` have lived
   there since the store spec's own § *The page*, so this is the arrangement that already works
   rather than a concession.
3. **The model is the step's main detector and the search is the supplement, not the other way
   round.** An earlier draft of this spec said the scan asked no model at all, on the grounds that
   the calls already say what the values are; a later one kept the model but wrote it as the
   remainder. Both were wrong and the measurement says by how much. A verbatim search finds 7 of
   the 13 bare argument values in the corpus, and row `b81aac81` calls
   `principal_amount=1000000000` over a turn saying *một tỷ* — **this corpus is transcribed
   speech**, so the spoken form of a number and the written form a call passes share no characters
   at all, and that is the ordinary case rather than the edge. The search is still kept, because
   where a value *is* spelled out there is nothing for a model to be wrong about and a failed call
   must not cost those places. Alternative: the model alone. Rejected for exactly that, and for
   nothing else.
4. **The step runs after the label, not before.** Alternative: fold it into card 1, so one scan
   claims both. Then the label's own arguments — where a slot placeholder already stands 6 times
   across the corpus — are read before the reviewer has said what the label is, and the two kinds
   of claim land in one facet,
   which is the state § *Context* measures and this spec exists to end.
5. **The generated conversations are held on the page and written by one Submit.** Alternative: a
   generated conversation is pushed into the queue the moment it is accepted, and labelled later
   like any imported sample. That is far less state — nothing on the page, and a draft that
   survives a reload — but it defers the review to another sitting, and the request is explicit
   that the new conversations are reviewed alongside the one they came from and saved together.
   The cost is Requirement 32, stated on the screen. Reversible: the queue route already exists and
   takes one line.
6. **`POST /records` is unchanged and is called once per conversation.** Alternative: a route that
   takes several. The store's answer to *what is a record* is one conversation, the reviewed
   sample, under its own key; a route taking a list would need its own partial-failure shape, and
   every caller would have to read it. N posts give the page one outcome per conversation for
   nothing.
7. **The two shared routes are renamed now rather than aliased.** Alternative: leave
   `/data-quality/personal-data/spans` where it is and post the scale card's claims to it.
   Two steps posting to a URL that names one of them is a name that needs a footnote, and the only
   client is a page in this repository. Alternative rejected for the opposite reason: adding
   `/data-scale/spans` and `/data-scale/redact` beside the old pair is two URLs for one act, and
   `C-3` is about not leaving a rule for somebody to remember.
8. **The two steps merge; they do not chain.** The reviewer's design, and the corpus is what
   decides it. Three rows carry `WRONG_PHONE` in one turn and the full `PHONE` two turns later, as
   different characters in different places — a mention is recognisable as *a wrong version of
   this value* only beside the value, so a scale detector reading the already-redacted record
   would be handed `<PHONE_1>` and lose the comparison it needs. That is the case this step exists
   to catch. Alternative: chain, which an earlier draft of this spec specified in full. It also
   broke the store's precondition for the commonest row in the corpus and needed a function in
   `sample_building.py` to repair it; merging deletes the problem and the repair together. The
   cost of merging is one new function, `keep_winning_spans`, and the rule that containment runs
   before priority — stated as an invariant because getting it backwards leaves half of a
   confirmed value standing.
9. **A placeholder is numbered per slot, not per value — and this is the one piece of arithmetic
   the two steps do not share.** The reviewer's existing corpus is the argument: row `b81aac81`
   gives `một tỷ` and `1000000000` the single name
   `<SVCCALCULATEINTEREST__PRINCIPAL_AMOUNT_1>`, which `name_placeholders` cannot produce because
   it keys by value. It is not a shortcut the reviewer took. Whatever re-fills that slot must move
   the words in the turn and the number in the call to the same amount, and two names are two
   things it can move apart — a conversation saying *một tỷ* over a call passing `3000000000` is
   the defect the whole step is built to prevent. Alternative: one name per value, with a filler
   told which names go together. That is the same rule written down twice, once in a corpus and
   once in a program nobody here owns (`T-6`), and the second copy is the one that would be wrong.
10. **A personal-data span that scale wins is dropped rather than kept beside it.** The corpus
    already does this — `b81aac81` lists `SVCGETCONTACTINFO__NAME` on `personal_data` and no `NAME`
    — and it is what lets the store's precondition stay untouched. The cost is real and is stated
    once: *which rows held a customer's name* stops being a question the facet answers, and becomes
    one only `tool_decision_record` can answer from the claims the detector made. Alternative: keep
    both spans and teach `find_surviving_spans` that one placeholder may stand for another. That
    buys the facet back and puts a scale rule inside the store's de-identification check, which is
    the one place in this repository where a rule from somewhere else is most expensive to have.
    Reversible: the record keeps the claims, so a later facet can be computed from them without
    re-reviewing a row.
11. **The already-stored rows are re-reviewed by hand, not backfilled.** The reviewer's decision.
   A name-shaped rule would move 12 kinds and leave 8 — `CAR_PRICE`, `DOWN_PAYMENT`,
   `INTEREST_RATE`, `LOAN_TERM`, `WEIGHT`, `DELIVERY_OPTION` and the two `WRONG_` kinds are
   judgements about what a value *is*, not about how it is spelled. Six rows, and the record table
   keeps what arrived, so nothing is lost by taking them one at a time.

## Invariants

- No raw value reaches what ships, whichever step claimed it. Check: both detectors read the sample
  as it arrived, `keep_winning_spans` settles every place between them, and `POST /redact` applies
  the union to one document. A place either step confirmed is replaced; which class it is replaced
  under is the only thing priority decides.
- A place a detector claimed is never left half replaced. Check: containment runs over the union
  before priority, so the longer span takes a place it encloses and a shorter span inside it is
  dropped rather than applied. Priority settles only an exact `(path, start, end)` tie, where
  there is no tail to leave behind.
- Every value of one slot wears one placeholder, and no two slots share one. Check:
  `name_slot_placeholders` maps each of a slot's values to the slot's single `<CLASS_N>`, and
  numbers `<CLASS_N>` per class across slots, so a filler cannot move *một tỷ* without moving the
  `1000000000` beside it and cannot move two slots together.
- Card 1's numbering is unchanged by all of this. Check: `name_placeholders` still keys by value
  and is still the only thing the personal-data step passes to `find_and_number_spans`; the slot
  rule lives in `data_scale.py` and the personal-data tests pass unedited across the extraction.
- A personal-data value the reviewer confirmed is out of what ships. Check: `find_surviving_spans`
  unchanged — a span scale won is not in `personal_data.spans`, so the check is never asked about a
  placeholder that was deliberately not applied, and a record with no `scale` reads exactly as it
  read before this step existed.
- The `scale` facet and the `scale` key on the record cannot disagree. Check: the facet is
  `read_redacted_classes` over the key's own spans, computed at write time, the way
  `personal_data` already is.
- A record whose `scale` says a value was replaced and whose shipped text still holds it does not
  become a row. Check: `find_surviving_spans` over the `scale` key, the same function and the same
  refusal as `personal_data`.
- `scale: null` stores; `personal_data: null` does not. Check: two paths through `build_sample`,
  pinned apart in the store's tests.
- Nothing under `ui/` decides what class a value is. Check: the scale card reads `scale_class` off
  a span the service answered, exactly as card 1 reads `personal_data_class`, and the guard
  forbidding a declared class name in `ui/` source sweeps every file under `ui/`, so it covers the
  new modules with nothing added.
- The wire and the stored documents keep the field names they have. Check: `PersonalDataSpan`
  declares `personal_data_class` as it always has — no base class, no alias — and the 102 places
  that key stands across `tool_decision_record` are not touched by this spec. `ScaleSpan` declares
  `scale_class` and neither shape imports the other.
- The generated conversation offers the source's catalog unchanged. Check: the route copies `tools`
  from the request and the prompt asks for turns only.
- No raw value reaches the generator. Check: the page posts `held…shipped.sample`, and the route's
  request model carries no path to the sample as it arrived.

## Error Behavior

- A generation call that fails answers a conversation with no turns and the model's own text under
  `said`, plus one structured event on stdout naming the model (`H-6`). The reviewer presses again;
  nothing else on the page moves.
- An answer that will not read as a list of turns is the same fact and the same answer. It is never
  partially read and never repaired.
- A generator model this deployment does not serve is a 422 raised by `check_served_models` before
  the call, like every other model-taking route.
- A missing or empty prompt file — `conversation_generation.txt`, `argument_scale_detect.txt` or
  `argument_scale_confirm.txt` — is a `ConfigError` and so a 422, on the same terms as the two
  prompts that came before them: a deployment with no prompt is not a provider having a bad day.
- **A failed model call in the scan leaves the rule scan's claims standing**, the same way a failed
  `pii_llm_detect` leaves the rule scans' values. One structured event on stdout naming the step
  (`H-6`), no raise, and a card 3 holding the slots the calls spelled out. **This costs more here
  than it does on card 1**, and the measurement says how much: a verbatim search reaches 7 of the
  13 bare values in the corpus and none of the ones a turn said in words, so a failed model is a
  table missing most of what the step is for. Nothing on the card says *refused*, because nothing
  was — but the card says the model did not answer, which card 1 does not have to, and the button
  re-runs it.
- **A failed confirmation confirms nothing, and card 3 comes back empty rather than wrong.** This
  is the one place the two steps' failures differ in what they cost: a personal-data confirmation
  that fails leaves every claimed value standing in the copy, which is a record held back; a scale
  confirmation that fails leaves a reviewer with no slots, which is a button to press again. Both
  are one event on stdout and neither raises.
- A model answer naming a class that is not a class — empty, or holding a character a placeholder
  may not carry — is dropped, one claim at a time. A bad row is one claim, not a reason to lose
  the rest of the answer.
- A body `POST /data-scale/values` cannot read as a sample is a 422 at the boundary, drawn in the
  rectangle that sent it.
- A record refused by the store during a multi-conversation Submit stops that conversation and no
  other. The line beside it says the service's own words; the ones already written stay written;
  pressing Submit again rewrites every key rather than making second rows.
- A sample with no calls at all opens no slot, which is not an error. Card 3 says *nothing to
  vary*, and that is a finished card — 30 of the 40 rows in the corpus already carry no bare
  argument value.
- A mention the model attributes to a slot id no line carries is dropped on its own, and so is one
  whose `text` is not in the review text. Neither costs the rest of the answer.

## Testing Strategy

- `read_argument_slots` over a hand-written sample: both call spellings read; a call in the label
  read as readily as one in a turn; an empty value opening no slot; one call with three arguments
  opening three slots; two slots passing one value settled by the first; a tool name lower-cased in
  the catalog claimed under its upper-cased class. Each assertion proved by mutating the source and
  confirming exactly the expected slots go red.
- **`name_slot_placeholders`, which is the test this step exists for.** A slot holding `một tỷ` and
  `1000000000` answers **one** `<SVCCALCULATEINTEREST__PRINCIPAL_AMOUNT_1>` for both, and the
  redacted record carries that one name in the turn and in the call. Pinned beside
  `name_placeholders` over the same two values answering two names, so the two rules are legible
  as two and a change to either is visible as one.
- `keep_winning_spans`: a name claimed by both steps at one place ships as the scale class and
  leaves `personal_data.spans` without it; a scale span enclosed by a longer personal-data span is
  dropped by containment and the personal-data span is what ships, which is the case where priority
  must *not* win; two spans that merely overlap settle by containment and never by step.
- The model half with `complete` stubbed, and the two answers it is allowed to give pinned apart:
  a mention sharing no characters with the value — *một tỷ* against `1000000000` — **joins** the
  slot it names and comes back wearing that slot's placeholder; a mention the model qualifies
  **opens** a second slot under `<TOOL>__<QUALIFIER>_<ARG>` and gets a placeholder of its own. Then
  the refusals: an answer whose `slot` no line carries is dropped; an answer whose `text` is not in
  the review text is dropped; a value the rule scan already holds is not added to the slot twice;
  a failed call leaves the rule scan's slots standing and writes one event. The prompt is pinned to
  carry the catalog, because a slot silently unfilled is a model told less with nothing saying so.
- The confirmation with `complete` stubbed, over the same four rules the personal-data one is
  pinned to: an id no span carries is discarded, a span answered twice keeps the first answer, a
  span nothing came back about is not confirmed, and an empty span list asks nothing at all.
- `name_argument_class` with and without a qualifier, pinned against the three the corpus already
  holds — `SEARCH_PLACE_27D__DISTRICT_LOCATION` is the one that proves the qualifier goes in front
  of the argument and not behind the tool.
- **The merge, over one record**: a name that is both personal data and an argument ships as
  `<SVCGETCONTACTINFO__NAME_1>`, the `personal_data` key does **not** carry a span for it, the
  `scale` key does, and `build_sample` stores the row with `find_surviving_spans` unedited. The
  same record run with the scale step skipped ships `<NAME_1>` and stores too — one sample, two
  outcomes, which is what proves the steps are independent rather than ordered.
- The full masking half over the sample § *Context* quotes: `SvcCalculateinterest`'s three
  arguments claimed, each one spanning the turn that said it, the call that passed it and the reply
  that repeated it, and the redacted copy reading as the corpus already stores it.
- The word-boundary case pinned: `time_period: 2` claims the standalone `2` and not the `2` inside
  `12`, and the claim is one row per place.
- The escaping limit pinned as a known one: a value holding a quote is claimed in the turn and not
  inside `arguments`, so the test says what the step does rather than leaving it to be found.
- The store's precondition: a record with `scale: null` stores; one whose `scale` names a span that
  did not take is refused with the same sentence `personal_data` is refused with; the `scale` facet
  comes back off an opened row and is counted by `count_by_facet`.
- Each route through `TestClient`, called with nothing but its own arguments — no fixture
  threads a detect answer from one route into another, which is pipeline Requirement 1.
- The generation route with `complete` stubbed: the catalog comes back as it went in; a model
  answer that is not turns comes back under `said` with no turns; a model name the directory does
  not hold is 422 and is proved to refuse *before* `complete` is reached.
- The page, in `tests/ui/page.js`: card 3 draws a row per place; its verdict follows its own table;
  the generation box opens holding what `GET /data-scale/prompt` answered; one press asks for one
  conversation; a draft appears in the list unfinished and is posted by Submit; two drafts are two
  posts; a refused draft leaves the others posted.
- The extraction commit changes no test. That is Requirement 29 and it is checked by the diff.

## What this rewrites

- `docs/labelling-ui/spec.md` Requirement 24 and the comment above `#call-form` in `index.html`:
  *the turns are what a customer said … a page that let a reviewer retype either is a page that can
  quietly make the sample agree with the label.* It stays true of a sample that arrived and gains
  the sentence that makes it false of one the page generated (Requirement 17).
- `docs/labelling-ui/spec.md` Requirement 26's opening, *the corpus is one button away*: the sheet's
  charts now separate `personal_data` from `scale`, and the paragraph naming `personal_data` as the
  facet nobody declares values for names both.
- `docs/tool-decision-pipeline/spec.md` Requirement 3: the record gains `scale`, and the sentence
  *the record is assembled by the page, once* becomes *once per conversation the reviewer is
  saving* — the record is still the flow's last answer and still exists in one place.
- `docs/tool-decision-store/spec.md` § *The page*: two route paths move, and the facet list grows a
  note.
- `docs/tool-decision-pipeline/spec.md` § *Context*, the paragraph naming three prompts: there are
  six, and the sentence that sorts them — *the shared one is shared because whether a detected
  value is personal data is a question about personal data and about nothing else* — now has a
  case on the other side of it. `argument_scale_detect.txt` and `argument_scale_confirm.txt` are
  both the task's, because *whether this stretch is a mention of that argument* is a question
  about a tool call; the confirmation is not the modality's the way the personal-data one is.
  `conversation_generation.txt` is the first prompt in this repository that is **edited by the
  person sending it** — every other one is a file only a deployment changes.
- `docs/tool-decision-pipeline/spec.md` Requirement 5, *detecting and replacing are two calls,
  because a human sits between them*: that is now true twice, of two steps, and the sentence names
  which.

The plans keep the history. None of the passages above is annotated in place — the spec states
current truth.

## Out of Scope

- **Filling the slots.** Turning one slotted row into a hundred rows with a hundred different
  amounts is a program reading the exported corpus, and it needs a table of candidate values per
  class that nothing here has. This step makes a corpus fillable and says nothing about who fills
  it.
- **Checking that a slot was filled sensibly.** `principal_amount` is a number and
  `<SVCCALCULATEINTEREST__PRINCIPAL_AMOUNT_1>` is not, so a filled corpus can carry a type error
  that this step cannot see. Whatever fills the slots owns that.
- **Naming a slot's type or its range.** The class says which argument a value came from, nothing
  more. The catalog already declares the type and the constraint beside that argument, so a second
  declaration would be the two rotting apart.
- **A generated conversation that offers a different catalog**, or one generated from nothing. Both
  are *making a sample*, and this step multiplies one that exists.
- **Duplicate detection over generated rows.** Two generations from one source may well be near
  copies, and `calculate_duplicates` compares canonical inputs, so it will not see it. Duplicates
  are `dataset_management`'s question and are deferred there already.

## Open

- **Whether card 1 should say that a row of its table is about to lose its place to card 3.** The
  two cards draw one table and each holds its own claims, so a customer's name that is also an
  argument appears on both — ticked on card 1 as `NAME`, ticked on card 3 as
  `SVCGETCONTACTINFO__NAME` — and only the second one ships. Nothing on card 1 says so. Leaving it
  is honest about what card 1 decided and silent about what happens to it; marking it means card 1
  reading card 3's state, which is the first thing on this page that would. It is decided by
  watching a reviewer use it once, not by argument, so it waits until the screen exists.
- **Whether a generated draft should survive a reload.** Requirement 33 says a draft lives on the
  page and nowhere else, and says so on the screen rather than leaving it to be discovered. Making
  one durable is a second store for a thing the queue already stores, and Decision 5 is why it is
  not that today. If reviewers lose work to a closed tab it becomes a queue row written on accept
  and read back on open, which is one route that already exists.
