// logic · the one thing this page composes. Owns record.

import { held } from "./held.js";
import { same, show } from "./screen.js";

export function composeRecord(facets) {
  if (!held.sample || !held.shipped) return;
  const redacted = held.shipped.sample;
  held.record = {
    ...held.sample,
    messages: held.sample.messages ?? [],
    tools: held.sample.tools ?? [],
    label: held.sample.label ?? null,
    new_messages: redacted.messages,
    new_tools: same(redacted.tools, held.sample.tools ?? []) ? null : redacted.tools,
    new_label: redacted.label,
    personal_data: held.detected ? { ...held.handed, outcome: held.shipped.outcome } : null,
    duplicate: null,
    abnormal: null,
    llm: held.review ? held.review.llm : null,
    sft: held.review ? held.review.sft : null,
    class: facets
  };
  show("record", held.record);
}
