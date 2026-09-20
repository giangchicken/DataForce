// adapter · which facets a person ticks, and where a value that is not declared comes from.
// Owns facet-ticks, domain-ticks, domain-new, domain-add, domain-note, guide-facets.

import { DECLARED_FACETS, PICK_SAID, held } from "./held.js";
import { $, esc, readTick, say, ticksNamed } from "./screen.js";

const addedValues = {};

export function facetValues(name) {
  const facet = DECLARED_FACETS.find(one => one.name === name);
  if (!facet || !facet.values) return [];
  const byFacet = (held.counted || {}).counted_distribution_by_facet || {};
  const stored = facet.pick === "one" ? Object.keys(byFacet[name] || {}) : [];
  return [...new Set([...facet.values, ...stored, ...(addedValues[name] || [])])];
}

export function paintGuideFacets() {
  $("guide-facets").innerHTML = DECLARED_FACETS.map(facet =>
    `<div class="facet"><b>${esc(facet.name)}</b>`
    + `<span class="pick">${esc(PICK_SAID[facet.pick])}</span>`
    + (facet.values ? `<span class="values">${esc(facetValues(facet.name).join("  ·  "))}</span>` : "")
    + `<div class="note">${esc(facet.said)}</div></div>`).join("");
}

const tickInput = facet =>
  facet.pick === "yes"
    ? `<label class="inline"><input type="checkbox" name="f-${facet.name}"> yes</label>`
    : facetValues(facet.name).map(value =>
        `<label class="inline"><input type="${facet.pick === "one" ? "radio" : "checkbox"}"`
        + ` name="f-${facet.name}" value="${esc(value)}"> ${esc(value)}</label>`).join("");

export function paintFacetTicks() {
  paintDomainTicks();
  $("facet-ticks").innerHTML = DECLARED_FACETS.filter(facet => facet.name !== "domain").map(facet =>
    `<div class="lab">${esc(facet.name)}</div>`
    + `<div class="tickbox">${tickInput(facet)}</div>`
    + `<div class="note">${esc(facet.said)}</div>`).join("");
}

let domainsDrawn = null;

export function paintDomainTicks() {
  const facet = DECLARED_FACETS.find(one => one.name === "domain");
  const values = facetValues("domain");
  const drawing = values.join("\u0000");
  if (drawing === domainsDrawn) return;
  domainsDrawn = drawing;
  const was = readTick("f-domain");
  $("domain-ticks").innerHTML = tickInput(facet);
  $("domain-said").textContent = facet.said;
  tickDomain(was);
}

function tickDomain(value) {
  for (const box of ticksNamed("f-domain")) {
    box.checked = !!value && box.value === value;
  }
}

export function addDomain() {
  const said = $("domain-new").value.trim();
  if (!said) return say("domain-note", "type a domain first", "bad");
  if (facetValues("domain").includes(said)) {
    return say("domain-note", `${said} is already offered`, "bad");
  }
  addedValues.domain = [...(addedValues.domain || []), said];
  paintDomainTicks();
  tickDomain(said);
  $("domain-new").value = "";
  say("domain-note", `${said} added and ticked — it stays offered once a sample carries it`);
}

export function readDeclaredFacets() {
  const answered = { language: $("language").value };
  for (const facet of DECLARED_FACETS) {
    const boxes = ticksNamed(`f-${facet.name}`);
    if (facet.pick === "yes") answered[facet.name] = boxes[0].checked;
    else if (facet.pick === "any") answered[facet.name] = boxes.filter(box => box.checked).map(box => box.value);
    else {
      const one = boxes.find(box => box.checked);
      if (one) answered[facet.name] = one.value;
    }
  }
  return answered;
}
