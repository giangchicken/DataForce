// adapter · card 2 above the facets: what the panel agreed, what arrived, and the label
// being written. Owns label-editor, label-text, label-fault, label-note,
// label-verdict, label-refusal, out-6, v-correct, v-modify, consensus-line, consensus-note.

import { asking, cannotAsk, mark } from "./checks.js";
import { paintCalls, saidLanguage } from "./conversation.js";
import { held, ticked } from "./held.js";
import { $, esc, json, say, sayVerdict, show } from "./screen.js";

export const rewriting = () => $("v-modify").checked;
import { call } from "./wire.js";

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
  mark(6, "answered", sayAgreement(answer.data));
  show("out-6", answer.data);
  sayVerdict("label-verdict", sayAgreement(answer.data), "");
  paintConsensus();
  return true;
}

function sayAgreement(reviewed) {
  const agreed = ((reviewed || {}).llm || {}).label_agreement;
  if (typeof agreed !== "number") return "reviewed";
  return `${Math.round(agreed * 100)}% agreement with the label`;
}

export function fillEditor() {
  if (!held.sample) return;
  $("label-text").value = json(held.sample.label ?? null);
  paintShipped();
}

function typedLabel() {
  const arrived = held.sample.label ?? null;
  if (!rewriting()) return arrived;
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
  paintCalls(rewriting());
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

function paintConsensus() {
  const offered = agreedLabel() !== "";
  $("consensus-line").hidden = !offered;
  if (offered) say("consensus-note", "the one label the panel agreed on, into the box below");
}

const agreedLabel = () => {
  const agreed = ((held.review || {}).llm || {}).consensus;
  return typeof agreed === "string" ? agreed.trim() : "";
};

export function takeConsensus() {
  const agreed = agreedLabel();
  if (!agreed) return false;
  let laid = agreed;
  try { laid = json(JSON.parse(agreed)); } catch { laid = agreed; }
  $("label-text").value = laid;
  $("v-modify").checked = true;
  $("v-correct").checked = false;
  $("label-editor").hidden = false;
  held.settled = true;
  return true;
}

export function forgetLabel() {
  faultAt += 1;
  paintFaults();
  paintConsensus();
  show("out-6", undefined);
  sayVerdict("label-verdict", "", "");
}

export function sayLabelRefusal(detail) {
  $("label-refusal").hidden = detail === "";
  $("label-refusal").textContent = detail;
}

export function forgetVerdict() {
  $("v-correct").checked = false;
  $("v-modify").checked = false;
  $("label-editor").hidden = true;
}

export function tookVerdict() {
  $("label-editor").hidden = !rewriting();
  held.settled = $("v-correct").checked || rewriting();
}
