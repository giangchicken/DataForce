// adapter · the two checks, and the row each one reports on. Owns said-2, said-6,
// checks-note, checks-verdict.

import { say, sayVerdict } from "./screen.js";
import { call } from "./wire.js";

export const CHECKS = [
  { step: 2, what: "Personal data", said: "said-2" },
  { step: 6, what: "Label", said: "said-6" }
];

const checked = {};

export function mark(step, state, text) {
  checked[step] = { state, text };
  paintChecks();
}

export function paintChecks() {
  for (const { step, said } of CHECKS) {
    const at = checked[step] || { state: "", text: "not run" };
    const kind = { answered: "ok", bad: "bad", unasked: "bad", wait: "busy", edited: "ok" }[at.state] || "";
    sayVerdict(said, at.text || "not run", kind);
  }
}

export function cannotAsk(step, why) {
  mark(step, "unasked", why);
  return false;
}

export async function asking(step, body, path) {
  mark(step, "wait", "asking…");
  const answer = await call(path, body);
  if (!answer.ok) mark(step, "bad", answer.detail);
  return answer;
}

export function forgetChecks() {
  for (const step of CHECKS.map(one => one.step)) delete checked[step];
  paintChecks();
  sayChecking("Two calls: the personal-data scan, then the reviewers.");
  sayChecksVerdict("not run", "");
}

export const sayChecking = (said, kind = "") => say("checks-note", said, kind);

export const sayChecksVerdict = (said, kind) => sayVerdict("checks-verdict", said, kind);
