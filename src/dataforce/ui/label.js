// adapter · card 2 above the facets: what the panel proposes, what arrived, which of the three a
// reviewer takes, and the form the third one writes on. Owns proposed-call, proposed-note,
// arrived-call, arrived-note, jury-said, v-take, v-keep, v-write, call-form, call-add, call-none,
// label-fault, label-verdict, out-6, label-refusal.

import { asking, cannotAsk, mark } from "./checks.js";
import { drawLabel, offeredTools, readCall, saidLanguage } from "./conversation.js";
import { held, ticked } from "./held.js";
import { $, esc, say, sayVerdict, show, wordFor } from "./screen.js";
import { call } from "./wire.js";

const rewriting = () => $("v-write").checked;
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

const proposed = () => (held.review || {}).consensus_calls || [];

const writtenCalls = () => (held.written || [])
  .filter(one => one.name)
  .map(one => ({
    name: one.name,
    // A field nobody filled in is an argument nobody stated, so it is not one the call makes.
    // What that costs the label is the catalog's to say, and it says it in `label-fault`.
    arguments: Object.fromEntries(
      Object.entries(one.arguments).filter(([, said]) => said !== ""))
  }));

function typedLabel() {
  if (taking()) return proposed();
  if (!rewriting()) return held.sample.label ?? null;
  return $("call-none").checked ? [] : writtenCalls();
}

export function paintShipped() {
  if (!held.sample) return;
  held.edited = {
    messages: held.sample.messages ?? [],
    tools: held.sample.tools ?? [],
    label: typedLabel()
  };
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

function paintProposal() {
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
  // **A juror's own answer, in the juror's own words.** Read as a call it would be this page
  // deciding what a sentence a model wrote holds, which is the reading `consensus_calls` exists to
  // keep on the service's side — and a juror that answered in prose would be drawn as *no call*,
  // which is a different answer from the one it gave.
  $("jury-said").querySelector("tbody").innerHTML = votes.map(vote => `<tr>
    <th scope="row">${esc(vote.model_name)}</th>
    <td class="value">${esc(vote.label)}</td>
    <td class="note">${esc(vote.reason)}</td>
  </tr>`).join("");
}

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
  $("call-none").checked = false;
  $("call-form").hidden = true;
}

export function tookVerdict() {
  if (rewriting() && held.written === null) seedForm();
  $("call-form").hidden = !rewriting();
  if (rewriting()) paintForm();
  held.settled = taking() || $("v-keep").checked || rewriting();
}

// The panel's answer where there is one: the finding this card is built on is that the arriving
// label is the weak half, so seeding from it is how a call two models spelled out is retyped. A
// seeded call naming a tool this sample never offered is dropped rather than carried, because the
// only thing pickable here is what the catalog offers.
function seedForm() {
  const offered = offeredTools().map(tool => tool.name);
  const from = proposed().length ? proposed() : held.sample.label;
  const calls = (Array.isArray(from) ? from : [])
    .map(readCall)
    .filter(one => offered.includes(one.name));
  held.written = calls.length ? calls : offered.slice(0, 1).map(blankCall);
}

const blankCall = named => ({ name: named, arguments: {} });

function paintForm() {
  const tools = held.sample ? offeredTools() : [];
  const none = $("call-none").checked;
  $("call-add").hidden = none || !tools.length;
  $("call-form").querySelector(".callforms").innerHTML = none
    ? '<div class="nocall">No call ships. The turn needs no tool, and that is an answer.</div>'
    : tools.length
      ? (held.written || []).map((one, at) => drawCallForm(one, at, tools)).join("")
      : '<div class="empty">This sample offers no tool, so the only answer it can be given is'
        + ' that the turn needs none.</div>';
}

function drawCallForm(one, at, tools) {
  const tool = tools.find(each => each.name === one.name) || { said: "", fields: [] };
  return `<div class="callform">
    <div class="runline">
      <select data-tool="${at}">${tools.map(each =>
        `<option value="${esc(each.name)}"${each.name === one.name ? " selected" : ""}>`
        + `${esc(each.name)}</option>`).join("")}</select>
      <button class="quiet" data-drop="${at}">Remove this call</button>
    </div>
    ${tool.said ? `<div class="note">${esc(tool.said)}</div>` : ""}
    ${tool.fields.length
      ? tool.fields.map(field => `<div class="fieldname">${esc(field.name)}`
        + (field.needed ? '<span class="needed">required</span>' : "")
        + `</div><input data-call="${at}" data-arg="${esc(field.name)}" spellcheck="false"`
        + ` value="${esc(one.arguments[field.name] ?? "")}">`
        + (field.said ? `<div class="note">${esc(field.said)}</div>` : "")).join("")
      : '<div class="note">This tool takes no argument.</div>'}
  </div>`;
}

export function pickedTool(event) {
  const picked = event.target.closest("[data-tool]");
  if (!picked || !held.written) return false;
  const at = Number(picked.dataset.tool);
  held.written = held.written.map((one, n) => (n === at ? blankCall(picked.value) : one));
  paintForm();
  return true;
}

// The one thing on this form that does not redraw it: a field being typed in is a field with the
// caret in it, and markup written over it takes the caret with it.
export function typedArgument(event) {
  const typed = event.target.closest("[data-arg]");
  if (!typed) return false;
  const one = (held.written || [])[Number(typed.dataset.call)];
  if (!one) return false;
  one.arguments = { ...one.arguments, [typed.dataset.arg]: typed.value };
  return true;
}

export function droppedCall(event) {
  const dropped = event.target.closest("[data-drop]");
  if (!dropped || !held.written) return false;
  held.written = held.written.filter((one, n) => n !== Number(dropped.dataset.drop));
  paintForm();
  return true;
}

export function addCall() {
  const offered = offeredTools().map(tool => tool.name);
  if (!offered.length) return false;
  held.written = [...(held.written || []), blankCall(offered[0])];
  paintForm();
  return true;
}

export const tookNoCall = () => paintForm();
