// adapter · card 2 above the facets: what the panel proposes, what arrived, and which of the
// three a reviewer takes. Owns proposed-call, proposed-note, arrived-call, arrived-note,
// jury-said, v-take, v-keep, v-write, label-editor, label-text, label-check, label-note,
// label-fault, label-verdict, out-6, label-refusal.

import { asking, cannotAsk, mark } from "./checks.js";
import { drawLabel, saidLanguage } from "./conversation.js";
import { held, ticked } from "./held.js";
import { $, esc, json, say, sayVerdict, show, wordFor } from "./screen.js";
import { call } from "./wire.js";

export const rewriting = () => $("v-write").checked;
const taking = () => $("v-take").checked;

export async function review(handed) {
  if (!held.sample) return cannotAsk(6, "no sample");
  const answer = await asking(6, {
    ...handed,
    language: saidLanguage(),
    jury_models: ticked.jury,
    sft_model: ticked.sft
  }, "/ai-review");
  if (!answer.ok) return false;
  held.review = answer.data;
  mark(6, "answered", sayAgreement(answer.data) || "reviewed");
  show("out-6", answer.data);
  sayVerdict("label-verdict", "reviewed", "");
  paintProposal();
  paintArrived();
  return true;
}

// What `label_agreement` measures: the share of jurors whose own answer matches the label that
// **arrived**. So it belongs beside what arrived, and nowhere near the panel's proposal — a
// proposal captioned *33% agreed* would read as a third of them agreeing with the proposal.
function sayAgreement(reviewed) {
  const agreed = ((reviewed || {}).llm || {}).label_agreement;
  if (typeof agreed !== "number") return "";
  return `${Math.round(agreed * 100)}% of the reviewers gave this answer too`;
}

export function fillEditor() {
  if (!held.sample) return;
  $("label-text").value = json(held.sample.label ?? null);
  paintShipped();
}

const proposed = () => (held.review || {}).consensus_calls || [];

function typedLabel() {
  if (taking()) return proposed();
  if (!rewriting()) return held.sample.label ?? null;
  try { return JSON.parse($("label-text").value); } catch { return { unparsed: $("label-text").value }; }
}

export function paintShipped() {
  if (!held.sample) return;
  held.edited = {
    messages: held.sample.messages ?? [],
    tools: held.sample.tools ?? [],
    label: typedLabel()
  };
  const unparsed = held.edited.label && held.edited.label.unparsed !== undefined;
  say("label-note", unparsed
    ? "not JSON, carried as {unparsed: …}"
    : "re-parsed as a label", unparsed ? "bad" : "");
  held.record = null;
  paintArrived();
}

let faultAt = 0;

export async function checkLabel() {
  if (!held.sample) return false;
  const mine = (faultAt += 1);
  const answer = await call("/data-quality/label", { ...held.sample, ...(held.edited || {}) });
  if (mine !== faultAt) return false;
  held.faults = answer.ok ? answer.data : null;
  if (!answer.ok) return sayNoCheck(answer.detail);
  paintFaults();
  return true;
}

function sayNoCheck(why) {
  const said = $("label-fault");
  said.hidden = false;
  said.textContent = `the label could not be checked against the catalog: ${why}`;
  return false;
}

function paintFaults() {
  const said = $("label-fault");
  const broken = held.faults && !held.faults.schema_valid;
  said.hidden = !broken;
  said.innerHTML = broken
    ? "<b>Nothing here can validate this label against the catalog.</b><ul>"
      + held.faults.faults.map(one => `<li>${esc(one)}</li>`).join("")
      + "</ul>"
    : "";
}

export function paintProposal() {
  const calls = proposed();
  const votes = ((held.review || {}).llm || {}).votes || [];
  $("v-take").disabled = calls.length === 0;
  $("proposed-call").innerHTML = held.review
    ? drawLabel(calls)
    : '<div class="empty">Nobody has been asked yet.</div>';
  say("proposed-note", !held.review ? ""
    : calls.length
      ? `what more than half of ${votes.length} ${wordFor(votes.length, "reviewer", "reviewers")} gave`
      : "the panel agreed on nothing, so there is nothing to take");
  $("jury-said").querySelector("tbody").innerHTML = votes.map(vote => `<tr>
    <th scope="row">${esc(vote.model_name)}</th>
    <td>${drawLabel(readVote(vote.label))}</td>
    <td class="note">${esc(vote.reason)}</td>
  </tr>`).join("");
}

const readVote = said => {
  try { const read = JSON.parse(said); return Array.isArray(read) ? read : null; } catch { return null; }
};

export function paintArrived() {
  if (!held.sample) return;
  $("arrived-call").innerHTML = drawLabel(held.sample.label ?? null);
  say("arrived-note", sayAgreement(held.review));
}

export function forgetLabel() {
  faultAt += 1;
  paintFaults();
  paintProposal();
  show("out-6", undefined);
  sayVerdict("label-verdict", "", "");
}

export function sayLabelRefusal(detail) {
  $("label-refusal").hidden = detail === "";
  $("label-refusal").textContent = detail;
}

export function forgetVerdict() {
  for (const id of ["v-take", "v-keep", "v-write"]) $(id).checked = false;
  $("label-editor").hidden = true;
}

export function tookVerdict() {
  if (rewriting() && $("label-editor").hidden) seedEditor();
  $("label-editor").hidden = !rewriting();
  held.settled = taking() || $("v-keep").checked || rewriting();
}

// The panel's answer where there is one: the finding this card is built on is that the arriving
// label is the weak half, so seeding from it is how a call two models spelled out is retyped.
function seedEditor() {
  const calls = proposed();
  $("label-text").value = json(calls.length ? calls : held.sample.label ?? null);
}
