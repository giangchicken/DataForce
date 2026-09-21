// logic · the one thing this page composes, and that record read back in words before it is
// written. Owns record, record-table.

import { saidCall } from "./conversation.js";
import { DECLARED_FACETS, held } from "./held.js";
import { $, esc, same, show, wordFor } from "./screen.js";

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
  paintRecord();
}

// Separately callable, because one of its rows lands on its own clock: the catalog's answer about
// the label arrives after the copy that composed the record as often as not, and a row nobody
// redrew goes on saying what the last answer said while the warning above it says otherwise.
export function paintRecord() {
  if (!held.record) return;
  $("record-table").querySelector("tbody").innerHTML = readBack().map(([named, said, kind]) =>
    `<tr><th scope="row">${esc(named)}</th>`
    + `<td${kind ? ` class="${kind}"` : ""}>${esc(said)}</td></tr>`).join("");
}

function readBack() {
  const valid = held.faults ? held.faults.schema_valid : null;
  return [
    ["key", held.record.id || "the service names it when it lands", ""],
    ["label", saidLabel(held.record.new_label), ""],
    ...facetRows(),
    // The row worth reading twice: the store's own rule, asked while the reviewer is still
    // looking at the sample rather than found days later by somebody reading the corpus.
    ["schema_valid", valid === null ? "nothing could check it" : valid ? "yes" : "no",
      valid === false ? "bad" : valid ? "ok" : ""],
    ["values replaced", saidReplaced(), ""]
  ];
}

// Every declared facet has a row whether or not it was ticked. A facet nobody answered is the
// one thing on this table worth seeing, and one that simply does not appear reads as nothing to
// say — `readDeclaredFacets` leaves a *tick one* facet out of the object entirely until one is.
function facetRows() {
  const answered = held.record.class;
  // Declared order first, which is the order they are ticked in above, then anything else the
  // record carries under `class` -- `language`, which is a declaration about the sample.
  const named = [...new Set([...DECLARED_FACETS.map(one => one.name), ...Object.keys(answered)])];
  return named.map(one => [one, saidFacet(answered[one]), ""]);
}

// A label is a list of calls or it is nothing this can read. `label` is `Any` on the way in, so a
// corpus line carrying a bare string arrives as one, and `"Lookup"` has a length and no `map`.
const saidLabel = calls => (Array.isArray(calls)
  ? (calls.length ? calls.map(saidCall).join("   ·   ")
    : "no call — the turn needs none, which is an answer")
  : calls === null || calls === undefined
    ? "no call — the turn needs none, which is an answer"
    : "not a list of calls, so nothing here can read it as one");

const saidFacet = said => (Array.isArray(said) ? said.join(", ") || "nothing ticked"
  : typeof said === "boolean" ? (said ? "yes" : "no")
  : String(said ?? "") || "nothing ticked");

function saidReplaced() {
  if (!held.record.personal_data) return "nothing has been read for personal data";
  // **The values on the table**, which is what card 1 counts too. The record hands back the scan's
  // own `claims` -- what it claimed before anybody ticked -- so counting those would put a
  // different denominator one box below the same number, the moment a reviewer adds a value.
  const values = held.claimed.size;
  if (!values) return "nothing was found";
  const spans = held.record.personal_data.spans || [];
  // One placeholder per distinct value, which is what `find_and_number_spans` numbers by -- so
  // counting them is counting the values that came out, not the occurrences they came out of.
  const replaced = new Set(spans.map(span => span.placeholder)).size;
  return `${replaced} of ${values} ${wordFor(values, "value", "values")} replaced,`
    + ` in ${spans.length} ${wordFor(spans.length, "place", "places")}`;
}

export function forgetRecord() {
  held.record = null;
  show("record", undefined);
  $("record-table").querySelector("tbody").innerHTML =
    '<tr><td colspan="2" class="empty">Nothing yet — the record is made as soon as the values you'
    + " kept are replaced.</td></tr>";
}
