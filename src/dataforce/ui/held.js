// shape · what the page holds between one sample and the next.

export const held = {
  key: null,        // the queue row this sample came from, posted back to say it is done
  sample: null,     // the sample as the queue handed it over
  scanned: null,    // the scan's own answer: what the detectors claimed, before any renumbering
  detected: null,   // the spans over the values still ticked, in the text they index
  claimed: new Map(),  // value → what kind it is, as the human left it: card 1's rows
  keeps: new Map(),    // which of those values the human is handing back
  handed: null,     // the detect shape with the spans as they left it
  review: null,     // what the reviewers said
  edited: null,     // the three, as they ship before redaction
  settled: false,   // has the reviewer said what the label is?
  faults: null,     // what the catalog says is wrong with the label on the screen
  shipped: null,    // the record as it ships, the text it reads as, and how far redacting got
  copyNote: null,   // why there is no such copy, where something refused to make one
  record: null,     // what will be posted
  counted: null     // what the statistics answered
};

export const ticked = { verifier: null, jury: [], sft: null };

export const NO_CALL = '<div class="nocall">No call — the turn needs no tool. That is an answer, not a skipped row.</div>';

export const COPY_AFTER = 180;

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

export const PICK_SAID = {
  one: "tick one",
  any: "tick every one that applies",
  yes: "tick it, or leave it"
};

export const STATE_SAID = { waiting: "", done: "labelled", skipped: "skipped" };
