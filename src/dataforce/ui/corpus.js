// adapter · what is already stored: the dataset sheet, the statistics grid, the strip, and
// which database a record lands in. Owns dataset-rows, dataset-bad, dataset-one,
// dataset-more, dataset-note, dataset-store, stats, strip, store.

import { drawCatalog, drawLabel, drawTurns, readTools } from "./conversation.js";
import { facetValues, paintDomainTicks } from "./facets.js";
import { held } from "./held.js";
import { waiting } from "./queue.js";
import { $, esc, say, wordFor } from "./screen.js";
import { ask } from "./wire.js";

const DATASET_PAGE = 100;
const BARS_SHOWN = 10;
const COUNTED_IN_THE_MATRIX = ["domain", "call_trigger"];

let stored = [];
let storedTotal = 0;
let storedShown = 0;
let storedOpen = null;

export async function askDataset(more) {
  storedShown = more ? storedShown + DATASET_PAGE : 0;
  if (!more) stored = [];
  say("dataset-note", "reading…");
  const answer = await ask(`/records?limit=${DATASET_PAGE}&offset=${storedShown}`);
  if (!answer.ok) return say("dataset-note", answer.detail, "bad");
  stored = [...stored, ...(answer.data.samples || [])];
  storedTotal = answer.data.total || 0;
  closeStored();
}

export function paintDataset() {
  const only = $("dataset-bad").checked;
  const rows = only ? stored.filter(row => !row.schema_valid) : stored;
  say("dataset-note", `${rows.length} of ${storedTotal} ${wordFor(storedTotal, "row", "rows")}`);
  $("dataset-more").disabled = stored.length >= storedTotal;
  const body = $("dataset-rows").querySelector("tbody");
  if (!rows.length) {
    body.innerHTML = `<tr><td colspan="8" class="empty">${
      only ? "Every stored row validates against its catalog." : "Nothing is stored yet."
    }</td></tr>`;
    return;
  }
  body.innerHTML = rows.map(row => `<tr class="${row.schema_valid ? "" : "dropped"}">
    <td><button class="open${row.key === storedOpen ? " opened" : ""}" data-stored="${esc(row.key)}">${esc(row.said) || "<i>no turns</i>"}</button></td>
    <td>${esc(row.domain)}</td>
    <td>${esc(row.ambiguous)}</td>
    <td>${esc(row.number_turns)}</td>
    <td>${esc(row.number_label_tools)}</td>
    <td>${esc(row.number_provided_tools)}</td>
    <td>${esc((row.personal_data || []).join(", ")) || "—"}</td>
    <td class="${row.schema_valid ? "ok" : "bad"}">${row.schema_valid ? "yes" : "no"}</td>
  </tr>`).join("");
}

// Whole, and drawn by the code the sample pane draws with -- the same call table, the same turns,
// the same catalog. A second drawing here would be a second idea of what a stored row looks like,
// and the one a reviewer never sees beside the original is the one that goes wrong quietly.
export async function openStored(key) {
  if (key === storedOpen) return closeStored();
  say("dataset-note", "reading…");
  const answer = await ask(`/records/${encodeURIComponent(key)}`);
  if (!answer.ok) return say("dataset-note", answer.detail, "bad");
  const one = answer.data;
  const valid = one.facets.schema_valid;
  storedOpen = key;
  paintDataset();
  say("dataset-note", `#${key}`);
  $("dataset-one").innerHTML = `<div class="storedone">`
    + `<div class="fieldname tight">Label as it ships</div>`
    + drawLabel(one.label ?? null)
    + (valid ? "" : `<p class="refusal">Nothing could validate this label against the catalog`
      + ` — a call names a tool that was never offered, or leaves out an argument it requires.</p>`)
    + `<div class="fieldname">The conversation</div>`
    + `<div class="turns">${drawTurns(one.input.messages || [])}</div>`
    + `<div class="fieldname">Tools offered</div>`
    + `<div class="catalog">${drawCatalog(readTools(one.input.tools))}</div>`
    + `</div>`;
}

function closeStored() {
  storedOpen = null;
  $("dataset-one").innerHTML = "";
  paintDataset();
}

// **Never the DSN**, in either place it is said: a connection string carries a password, and what
// both of these answer is *am I writing where I think I am* without one.
export async function askStore() {
  const answer = await ask("/store", {});
  const named = answer.ok && answer.data && typeof answer.data.describes === "string"
    ? answer.data.describes : "";
  if (!named) return sayStore("store none", "", "nothing answered which database this writes to");
  sayStore("store", named, `records land in ${named}`);
}

// The header says which, in as few words as a pill holds; the sheet that opens the corpus says it
// as a sentence, because a page of rows with no line saying where they came from is a page of rows
// about nowhere. One reading, said twice, so the two cannot come to disagree.
function sayStore(kind, named, why, said = "") {
  $("store").className = kind;
  $("store").textContent = named;
  $("store").title = why;
  say("dataset-store", why, said);
}

export async function askStatistics() {
  const answer = await ask("/records/stats", {});
  if (!answer.ok) return sayNoStatistics(answer.detail);
  held.counted = answer.data;
  try {
    paintDomainTicks();
    paintStrip();
    paintStatistics();
  } catch (error) {
    sayNoStatistics(`the statistics came back unreadable: ${error}`);
  }
}

function sayNoStatistics(said) {
  held.counted = null;
  $("strip").className = "strip none";
  $("strip").textContent = said;
  $("stats").innerHTML = '<div class="fieldname">What the corpus holds</div>'
    + `<div class="note">${esc(said)}</div>`;
}

function listEmptyCells(grid) {
  const empty = [];
  for (const domain of facetValues("domain")) {
    for (const trigger of facetValues("call_trigger")) {
      if (!((grid[domain] || {})[trigger])) empty.push([domain, trigger]);
    }
  }
  return empty;
}

const offList = (facet, value) => !facetValues(facet).includes(value);

function buildMatrixTable(grid) {
  const rows = [...new Set([...facetValues("domain"), ...Object.keys(grid)])];
  const columns = [...new Set([
    ...facetValues("call_trigger"),
    ...Object.values(grid).flatMap(row => Object.keys(row))
  ])];
  const head = columns.map(column =>
    `<th class="axis${offList("call_trigger", column) ? " gone" : ""}">${esc(column)}</th>`).join("");
  const body = rows.map(row => {
    const cells = columns.map(column => {
      const number = (grid[row] || {})[column] || 0;
      return `<td class="cell${number ? "" : " zero"}">${esc(number)}</td>`;
    }).join("");
    return `<tr><th class="axis${offList("domain", row) ? " gone" : ""}">${esc(row)}</th>${cells}</tr>`;
  }).join("");
  return '<div class="tablewrap"><table class="matrix">'
    + `<thead><tr><th class="axis"></th>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}

function drawBars(counted) {
  const ranked = Object.entries(counted).sort(([, one], [, two]) => two - one);
  const most = ranked.length ? ranked[0][1] : 0;
  return '<div class="barchart">'
    + ranked.slice(0, BARS_SHOWN).map(([value, number]) =>
      `<div class="barname">${esc(value)}</div>`
      + '<div class="bartrack">'
      + (number ? `<div class="barfill" style="width:${(number / most) * 100}%"></div>` : "")
      + `</div><div class="barnumber${number ? "" : " zero"}">${esc(number)}</div>`).join("")
    + '</div>'
    + (ranked.length > BARS_SHOWN
      ? `<p class="note">The ${BARS_SHOWN} largest of ${ranked.length}.</p>`
      : "");
}

function drawHistogram(facet, counted) {
  const declared = facetValues(facet);
  const values = [...declared, ...Object.keys(counted).filter(one => !declared.includes(one))];
  const most = Math.max(0, ...Object.values(counted));
  return '<div class="histogram">'
    + values.map(value => {
      const number = counted[value] || 0;
      return '<div class="column"><div class="columntrack">'
        + `<div class="columnfill" style="height:${most ? (number / most) * 100 : 0}%">`
        + `<span class="columnnumber${number ? "" : " zero"}">${esc(number)}</span></div>`
        + `</div><div class="columnname">${esc(value)}</div></div>`;
    }).join("")
    + '</div>';
}

export function paintStrip() {
  const bits = [];
  if (waiting()) {
    bits.push(`<b>${esc(waiting().waiting)}</b> waiting`);
    if (waiting().done) bits.push(`<b>${esc(waiting().done)}</b> done`);
    if (waiting().skipped) bits.push(`<b>${esc(waiting().skipped)}</b> skipped`);
  }
  if (held.counted) {
    const totals = Object.values(held.counted.sample_totals || {});
    const stored = totals.length ? Math.min(...totals) : 0;
    bits.push(`<b>${esc(stored)}</b> ${wordFor(stored, "row", "rows")} stored`
      + (new Set(totals).size > 1 ? " — the two tables disagree" : ""));
    const grid = held.counted.counted_distribution_by_domain_and_call_trigger || {};
    const empty = listEmptyCells(grid).length;
    const cells = facetValues("domain").length * facetValues("call_trigger").length;
    bits.push(`<b>${esc(empty)}</b> of ${esc(cells)} cells still empty`);
  }
  $("strip").className = "strip";
  $("strip").innerHTML = bits.join("");
}

function paintStatistics() {
  const grid = held.counted.counted_distribution_by_domain_and_call_trigger || {};
  const label = held.counted.label_summary || {};
  const calls = held.counted.tool_call_counts || {};
  const groups = held.counted.duplicate_groups || {};
  const silent = Object.values(calls).filter(number => !number).length;
  const empty = listEmptyCells(grid);
  const byFacet = held.counted.counted_distribution_by_facet || {};
  $("stats").innerHTML = '<div class="fieldname">What the corpus holds</div>'
    + '<div class="fieldname">Domain against call trigger</div>'
    + buildMatrixTable(grid)
    + (empty.length
      ? `<p class="note">Still empty: ${esc(empty.map(([a, b]) => `${a} × ${b}`).join(", "))}.</p>`
      : '<p class="note">Every cell has at least one sample.</p>')
    + '<div class="fieldname">The labels</div>'
    + '<div class="figs">'
    + `<div><b>${esc(label.total ?? 0)}</b> ${wordFor(label.total ?? 0, "row", "rows")}</div>`
    + `<div><b>${esc(label.number_not_null_label ?? 0)}</b> answered with a call</div>`
    + `<div><b>${esc(label.number_diff_label ?? 0)}</b> distinct ${wordFor(label.number_diff_label ?? 0, "answer", "answers")}</div>`
    + `<div><b>${esc(held.counted.number_tools_offered ?? 0)}</b> ${wordFor(held.counted.number_tools_offered ?? 0, "tool", "tools")} the catalogs put in front of the model</div>`
    + '</div>'
    + '<div class="fieldname">Tools called</div>'
    + (Object.keys(calls).length
      ? drawBars(calls)
        + (silent
          ? `<p class="note">${esc(silent)} of ${esc(Object.keys(calls).length)} tools`
            + ` ${wordFor(silent, "is", "are")} never called — a corpus teaches no tool it never`
            + ' calls.</p>'
          : "")
      : '<p class="note">No stored sample calls a tool yet.</p>')
    + '<div class="fieldname">The same input twice</div>'
    + '<div class="figs">'
    + `<div><b>${esc((groups.same_label || []).length)}</b> ${wordFor((groups.same_label || []).length, "group", "groups")} agreeing</div>`
    + `<div><b>${esc((groups.diff_label || []).length)}</b> ${wordFor((groups.diff_label || []).length, "group", "groups")} disagreeing</div>`
    + '</div>'
    + Object.entries(byFacet)
      .filter(([facet]) => !COUNTED_IN_THE_MATRIX.includes(facet))
      .map(([facet, values]) =>
        `<div class="fieldname">${esc(facet)}</div>`
        + (Object.keys(values).length
          ? drawHistogram(facet, values)
          : '<p class="note">nothing stored</p>')).join("");
}
