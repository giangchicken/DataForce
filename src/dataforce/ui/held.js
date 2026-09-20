// shape · what the page holds between one sample and the next, and what a check and a facet
// are. Owns no id.

export const held = {
  key: null,        // the queue row this sample came from, posted back to say it is done
  sample: null,     // the sample as the queue handed it over
  detected: null,   // the scan's answer, with the spans as they came back
  rows: [],         // the span rows as the human is editing them, added ones included
  keeps: {},        // which rows the human is handing back
  handed: null,     // the detect shape with the spans as they left it
  review: null,     // what the reviewers said
  edited: null,     // the three, as they ship before redaction
  settled: false,   // has the reviewer said what the label is?
  faults: null,     // what the catalog says is wrong with the label on the screen
  shipped: null,    // the record as it ships, the text it reads as, and how far redacting got
  copyNote: null,   // why there is no such copy, where something refused to make one
  record: null      // what will be posted
};

export const ticked = { verifier: null, jury: [], sft: null };

// The two checks, and the row each one writes on. The step numbers are the service's own and are
// kept because the refusals name them; what the reviewer reads is the `what`.
//
// **The replacement is not one of them.** It is not a decision and never was: a span the reviewer
// keeps is a value that has to come out, so it comes out as they tick. It reports on the row of
// the scan that found it, because that is the check it belongs to.
export const CHECKS = [
  { step: 2, what: "Personal data", said: "said-2" },
  { step: 6, what: "Label", said: "said-6" }
];

export const checked = {};

export const NO_CALL = '<div class="nocall">No call — the turn needs no tool. That is an answer, not a skipped row.</div>';

export const TICK_LISTS = ["verifier-ticks", "jury-ticks", "sft-ticks"];

// How long a pause counts as *done typing*. An offset is typed a digit at a time and each digit
// is a different set of spans, so one call per keystroke would be a call per character. A label
// being rewritten is the same thing through a different box.
export const COPY_AFTER = 180;

// **This page's own list, and the only one there is.** A tickable value is a thing a person
// chooses, and the store has no use for one until a sample carries it -- so a read of the store
// answers what the rows hold, never what they were allowed to hold, and nothing below the edge
// keeps a copy of this. The cost, stated: a facet the profile declares and this list never draws
// is a column that is always null, and nothing but somebody reading both catches it.
//
// `language` is not in it. The sample pane declares it for the scan and the jury, and it rides to
// the row from there -- asking again would be one sample described in two places.
export const DECLARED_FACETS = [
  { name: "domain", pick: "one",
    values: ["debt_collection", "telesale", "bill_reminder", "customer_care"],
    said: "what the bot does, not the customer's industry. A column, so a sample without it is "
      + "refused. Add one below if none of these is it" },
  { name: "call_trigger", pick: "any",
    values: ["condition_met", "user_utterance", "every_turn"],
    said: "one per call, so tick every way this sample fires. Nothing ticked is a sample that calls nothing" },
  { name: "direction", pick: "one", values: ["inbound", "outbound"],
    said: "who placed the call. Goes to notes, because not every corpus this table holds is a call bot" },
  { name: "ambiguous", pick: "one", values: ["LOW", "MED", "HIGH"],
    said: "how arguable this sample is. A column, so a sample without it is refused — two "
      + "annotators differing on a HIGH one is signal, not a mistake by either" },
  { name: "have_conversation_flow", pick: "yes",
    said: "a step in a scripted flow, where reaching it is what obliges the call. Goes to notes" }
];

// How many of a facet's values one sample carries. Said in words because the shape of the input
// is not an explanation: a person reading the guide before they start has no tick box in front of
// them to infer it from.
export const PICK_SAID = {
  one: "tick one",
  any: "tick every one that applies",
  yes: "tick it, or leave it"
};

export const STATE_SAID = { waiting: "", done: "labelled", skipped: "skipped" };

export const DATASET_PAGE = 100;
