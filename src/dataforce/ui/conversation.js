// adapter · a turn, a tool call and a label, drawn. Owns turns, catalog, tool-count,
// raw-sample, calls, calls-which, language.

import { held, NO_CALL } from "./held.js";
import { $, esc, json, show, wordFor } from "./screen.js";

export function paintTurns() {
  show("raw-sample", held.sample);
  const turns = held.sample.messages || [];
  if (!turns.length) {
    $("turns").innerHTML = '<div class="empty">This sample carries no turns.</div>';
    return;
  }
  $("turns").innerHTML = drawTurns(turns);
}

export const drawTurns = turns => turns.map(turn => {
  const who = String(turn.role ?? "?");
  const said = typeof turn.content === "string" ? turn.content
    : turn.content == null ? "" : json(turn.content);
  const calls = turn.tool_calls ? `<div class="calls">${drawCalls(turn.tool_calls)}</div>` : "";
  return `<div class="turn ${esc(who)}"><div class="who">${esc(who)}</div>`
    + `<div class="said">${esc(said)}${calls}</div></div>`;
}).join("");

export function paintCatalog() {
  const tools = held.sample.tools || [];
  $("tool-count").textContent = `${tools.length} ${wordFor(tools.length, "tool", "tools")}`;
  if (!tools.length) {
    $("catalog").innerHTML = '<div class="empty">No tools were offered.</div>';
    return;
  }
  $("catalog").innerHTML = tools.map(tool => {
    const spec = tool.function || tool;
    const args = Object.keys((spec.parameters || {}).properties || {});
    return `<div class="tool"><b>${esc(spec.name ?? "(unnamed)")}</b>`
      + (args.length ? `<span class="args"> (${esc(args.join(", "))})</span>` : "")
      + (spec.description ? `<div class="note">${esc(spec.description)}</div>` : "")
      + "</div>";
  }).join("");
}

export const drawCalls = calls => calls.map(one => {
  const spec = typeof one === "string" ? { name: one } : (one && one.function) || one || {};
  const args = spec.arguments === undefined ? "" : json(spec.arguments);
  return `<div class="call"><b>${esc(spec.name ?? "(unnamed)")}</b>`
    + (args ? `<div class="args">${esc(args)}</div>` : "") + "</div>";
}).join("");

export function paintCalls(rewriting) {
  if (!held.sample) return;
  const ships = held.settled && held.shipped;
  const label = ships
    ? held.shipped.sample.label
    : (held.edited ? held.edited.label : held.sample.label);
  $("calls-which").textContent = ships
    ? "The label as it ships — this is what is stored"
    : rewriting
      ? "The label as you are rewriting it"
      : "The label as it arrived";
  $("calls").innerHTML = drawLabel(label);
}

function drawLabel(label) {
  if (label === null || label === undefined) return NO_CALL;
  if (!Array.isArray(label)) return '<div class="nocall">Not JSON yet — the box below says what is wrong.</div>';
  return label.length ? drawCalls(label) : NO_CALL;
}

export function sayNoSample(said) {
  $("turns").innerHTML = `<div class="empty">${esc(said)}</div>`;
  $("catalog").innerHTML = "";
  $("tool-count").textContent = "";
}

export const saidLanguage = () => $("language").value;
