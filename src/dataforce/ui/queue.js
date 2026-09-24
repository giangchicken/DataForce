// adapter · which sample is next, how much of the corpus is left, and the rows a reviewer
// picked to walk. Owns list-walk, list-none, list-rows, list-note, sample-name.

import { STATE_SAID, held } from "./held.js";
import { $, esc, say } from "./screen.js";
import { ask, call } from "./wire.js";

export const picked = new Set();

let left = null;
let walking = [];

export const waiting = () => left;

export function forgetQueue() {
  left = null;
  walking = [];
}

export function walkThese() {
  walking = listed.filter(row => picked.has(row.key)).map(row => row.key);
  return walking.length > 0;
}

export async function nextQueued() {
  const gone = [];
  while (walking.length) {
    const answer = await ask(`/queue/${encodeURIComponent(walking.shift())}`, {});
    if (answer.ok) {
      left = answer.data;
      return { answer, gone };
    }
    gone.push(`a picked sample is gone: ${answer.detail}`);
  }
  const answer = await ask("/queue/next", {});
  left = answer.ok ? answer.data : null;
  return { answer, gone };
}

export async function oneQueued(key) {
  walking = [];
  const answer = await ask(`/queue/${encodeURIComponent(key)}`, {});
  if (answer.ok) left = answer.data;
  return answer;
}

export async function skipQueued(key) {
  const answer = await call(`/queue/${encodeURIComponent(key)}/skip`, undefined);
  if (answer.ok) left = answer.data;
  return answer;
}

export function sayQueueName(said) {
  $("sample-name").textContent = said;
}

let listed = [];

export async function askList() {
  const answer = await ask("/queue", {});
  if (!answer.ok) {
    listed = [];
    $("list-rows").innerHTML = `<div class="empty">${esc(answer.detail)}</div>`;
    return say("list-note", "");
  }
  listed = answer.data.samples || [];
  say("list-note", `${listed.length} of ${answer.data.waiting + answer.data.done + answer.data.skipped}`);
  paintList();
}

export function paintList() {
  if (!listed.length) {
    $("list-rows").innerHTML = '<div class="empty">The queue is empty. Add a file or paste a sample.</div>';
    return pickedChanged();
  }
  $("list-rows").innerHTML = listed.map(row =>
    `<div class="row ${esc(row.state)}${row.key === held.key ? " here" : ""}">`
    + `<label class="tick"><input type="checkbox" data-pick="${esc(row.key)}"`
    + `${picked.has(row.key) ? " checked" : ""}></label>`
    + `<button class="open" data-open="${esc(row.key)}">`
    + `<span class="at">${esc(row.walk_position)}</span>`
    + `<span class="said">${esc(row.preview) || "<i>no turns</i>"}</span>`
    + `<span class="was">${esc(STATE_SAID[row.state] || row.state)}</span>`
    + "</button></div>").join("");
  pickedChanged();
}

export function pickedChanged() {
  $("list-walk").disabled = picked.size === 0;
  $("list-none").disabled = picked.size === 0;
  $("list-walk").textContent = picked.size
    ? `Label the ${picked.size} selected`
    : "Label the selected";
}
