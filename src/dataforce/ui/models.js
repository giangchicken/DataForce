// adapter · which models answer, and that config/model/ is a directory a deployment edits
// while the service is up. Owns verifier-ticks, jury-ticks, sft-ticks.

import { ticked } from "./held.js";
import { $, readTick, same, sayInTicks, tickBox, ticksNamed } from "./screen.js";
import { ask } from "./wire.js";

export const TICK_LISTS = ["verifier-ticks", "jury-ticks", "sft-ticks"];

let drawn = null;

export async function paintTicks() {
  const answer = await ask("/models", {});
  if (!answer.ok) return sayInTicks(TICK_LISTS, answer.detail);
  const served = Array.isArray(answer.data) ? answer.data : [];
  if (!served.length) {
    drawn = null;
    return sayInTicks(TICK_LISTS,
      "no model is configured: config/model/ holds none this deployment can serve");
  }
  if (same(served, drawn)) return;
  drawn = served;
  $("verifier-ticks").innerHTML = served.map(name => tickBox("verifier", name)).join("");
  $("jury-ticks").innerHTML = served.map(name => tickBox("jury", name)).join("");
  $("sft-ticks").innerHTML = '<label class="inline"><input type="radio" name="sft" value="" checked> none</label>'
    + served.map(name => tickBox("sft", name)).join("");
  retick(served);
}

function retick(served) {
  const wasVerifier = ticked.verifier;
  const wasJury = ticked.jury.filter(name => served.includes(name));
  const wasSft = ticked.sft;
  ticked.verifier = served.includes(wasVerifier) ? wasVerifier : served[0];
  ticked.jury = wasJury.length ? wasJury : [served[0]];
  ticked.sft = served.includes(wasSft) ? wasSft : null;
  for (const box of ticksNamed("verifier")) {
    box.checked = box.value === ticked.verifier;
  }
  for (const box of ticksNamed("jury")) {
    box.checked = ticked.jury.includes(box.value);
  }
  for (const box of ticksNamed("sft")) {
    box.checked = box.value === (ticked.sft || "");
  }
}

export function readTicked() {
  ticked.verifier = readTick("verifier");
  ticked.jury = ticksNamed("jury").filter(box => box.checked).map(box => box.value);
  ticked.sft = readTick("sft") || null;
}
