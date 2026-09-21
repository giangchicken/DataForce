// adapter · a turn, a tool call and a label, drawn. Owns turns, catalog, tool-count,
// raw-sample, language.

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

// A catalog, read once: the pane draws it, the form that writes a label is built out of it, and a
// stored row opened out of the corpus draws its own. A second reading would be a second idea of
// what a tool's parameters are.
export const readTools = tools => (tools || []).map(tool => {
  const spec = tool.function || tool;
  const taken = (spec.parameters || {}).properties || {};
  const needed = (spec.parameters || {}).required || [];
  return {
    name: spec.name ?? "(unnamed)",
    said: spec.description || "",
    fields: Object.entries(taken).map(([named, field]) => ({
      name: named,
      said: (field || {}).description || "",
      needed: needed.includes(named)
    }))
  };
});

export const offeredTools = () => readTools(held.sample.tools);

export const drawCatalog = read => (read.length
  ? read.map(tool => `<div class="tool"><b>${esc(tool.name)}</b>`
    + (tool.fields.length
      ? `<span class="args"> (${esc(tool.fields.map(field => field.name).join(", "))})</span>` : "")
    + (tool.said ? `<div class="note">${esc(tool.said)}</div>` : "")
    + "</div>").join("")
  : '<div class="empty">No tools were offered.</div>');

export function paintCatalog() {
  const tools = offeredTools();
  $("tool-count").textContent = `${tools.length} ${wordFor(tools.length, "tool", "tools")}`;
  $("catalog").innerHTML = drawCatalog(tools);
}

export const drawCalls = calls => calls.map(one => {
  const spec = typeof one === "string" ? { name: one } : (one && one.function) || one || {};
  const args = spec.arguments === undefined ? "" : json(spec.arguments);
  return `<div class="call"><b>${esc(spec.name ?? "(unnamed)")}</b>`
    + (args ? `<div class="args">${esc(args)}</div>` : "") + "</div>";
}).join("");

export function drawLabel(label) {
  if (label === null || label === undefined) return NO_CALL;
  // Not a list of calls at all, which a corpus line may well be: `label` is `Any` on the way in,
  // so whatever somebody wrote is what arrives. The catalog's own check refuses it in its own
  // words on `label-fault` above, and that is where this points — there is no box below.
  if (!Array.isArray(label)) {
    return '<div class="nocall">This is not a list of calls, so nothing here can draw it as one.'
      + " The catalog's warning above says what is wrong with it.</div>";
  }
  if (!label.length) return NO_CALL;
  return label.map(drawOneCall).join("");
}

const readArguments = given => {
  if (typeof given !== "string") return given;
  try { return JSON.parse(given); } catch { return given; }
};

// One call, in the two spellings the store says are one: `{name, arguments: {...}}` as a corpus
// writes it, and `{function: {name, arguments: "<json text>"}}` as a provider does. Every argument
// comes back as text, because a field on a form holds text and nothing else.
export function readCall(one) {
  const spec = typeof one === "string" ? { name: one } : (one && one.function) || one || {};
  const args = readArguments(spec.arguments);
  const taken = args && typeof args === "object" && !Array.isArray(args) ? Object.entries(args) : [];
  return {
    name: spec.name ?? "",
    arguments: Object.fromEntries(taken.map(([named, value]) =>
      [named, typeof value === "string" ? value : json(value)]))
  };
}

// Through `readCall` and not beside it. Drawn on its own it grew a second reading: a call whose
// `arguments` are a list drew a row holding that list, while the record table one box below read
// `Lookup()`. The store settles it — `read_call_arguments` answers `{}` for anything that is not
// a mapping, and `check_label_calls` refuses such a call — so *no arguments* is what it supplies,
// and `label-fault` is what says why.
function drawOneCall(one) {
  const read = readCall(one);
  const rows = Object.entries(read.arguments);
  return `<table class="calltable"><thead><tr>
    <th colspan="2">${esc(read.name || "(unnamed)")}</th>
  </tr></thead><tbody>${rows.length
    ? rows.map(([named, said]) => `<tr><th scope="row">${esc(named)}</th>`
      + `<td>${esc(said)}</td></tr>`).join("")
    : '<tr><td colspan="2" class="empty">no arguments</td></tr>'}</tbody></table>`;
}

// One call on one line, the way the catalog writes one: the tool named once, then one
// `argument=value` for each it was given. A label that names a tool and never calls it reads as
// empty brackets, which is that said in words.
export function saidCall(one) {
  const read = readCall(one);
  return `${read.name || "(unnamed)"}(${Object.entries(read.arguments)
    .map(([named, said]) => `${named}=${said}`).join(", ")})`;
}

export function sayNoSample(said) {
  $("turns").innerHTML = `<div class="empty">${esc(said)}</div>`;
  $("catalog").innerHTML = "";
  $("tool-count").textContent = "";
}

export const saidLanguage = () => $("language").value;
