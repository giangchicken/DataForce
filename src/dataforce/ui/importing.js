// adapter · how a corpus gets in: one sample pasted, or a file of lines. Owns pasting,
// paste-open, paste-text, paste-now, paste-queue, paste-cancel, paste-note, sheet-import,
// file, drop, drop-said, import-run, import-note, import-said.

import { $, esc, say, wordFor } from "./screen.js";
import { ask } from "./wire.js";

export function showPasting(open) {
  $("pasting").hidden = !open;
  if (open) $("paste-text").focus();
}

function readPasted(text) {
  const said = text.trim();
  if (!said) return { samples: [], broke: "nothing pasted" };
  try {
    const read = JSON.parse(said);
    if (Array.isArray(read)) {
      const bad = read.findIndex(one => !one || typeof one !== "object" || Array.isArray(one));
      if (bad !== -1) return { samples: [], broke: `item ${bad + 1} is not a sample object` };
      return { samples: read, broke: "" };
    }
    if (typeof read === "object" && read !== null) return { samples: [read], broke: "" };
    return { samples: [], broke: "that is JSON, but not a sample object" };
  } catch {
    const lines = said.split("\n").filter(line => line.trim());
    const samples = [];
    for (const [at, line] of lines.entries()) {
      try {
        const read = JSON.parse(line);
        if (!read || typeof read !== "object" || Array.isArray(read)) {
          return { samples: [], broke: `line ${at + 1} is not a sample object` };
        }
        samples.push(read);
      } catch (error) {
        return { samples: [], broke: `line ${at + 1} is not JSON: ${error.message}` };
      }
    }
    return { samples, broke: "" };
  }
}

export async function labelPasted() {
  const { samples, broke } = readPasted($("paste-text").value);
  if (broke) return say("paste-note", broke, "bad");
  say("paste-note", "reading…");
  const answer = await ask("/samples/named", {
    method: "POST",
    headers: { "Content-Type": "application/x-ndjson" },
    body: samples.map(one => JSON.stringify(one)).join("\n")
  });
  if (!answer.ok) return say("paste-note", answer.detail, "bad");
  const named = answer.data.samples || [];
  if (!named.length) return say("paste-note", "nothing in that was a sample", "bad");
  say("paste-note", named.length > 1
    ? `${named.length} read — opening the first; add them to the queue to walk the rest`
    : "read as one sample");
  showPasting(false);
  return named[0];
}

export async function queuePasted() {
  const { samples, broke } = readPasted($("paste-text").value);
  if (broke) return say("paste-note", broke, "bad");
  say("paste-note", "adding…");
  return sendLines(samples.map(one => JSON.stringify(one)).join("\n"), "paste-note");
}

let chosen = null;

export function tookFile(file) {
  chosen = file;
  $("drop-said").textContent = file ? `${file.name} — ${file.size} bytes` : "Drop a file here, or choose one";
  $("import-run").disabled = !file;
  say("import-note", "");
}

export async function runImport() {
  if (!chosen) return;
  $("import-run").disabled = true;
  say("import-note", "reading…");
  try {
    return await sendLines(await chosen.text(), "import-note");
  } finally {
    $("import-run").disabled = !chosen;
  }
}

async function sendLines(text, noteId) {
  const answer = await ask("/queue/import", {
    method: "POST",
    headers: { "Content-Type": "application/x-ndjson" },
    body: text
  });
  if (!answer.ok) {
    say(noteId, answer.detail, "bad");
    return false;
  }
  say(noteId, "");
  const came = answer.data;
  $("import-said").innerHTML = '<div class="figs">'
    + `<div><b>${esc(came.read)}</b> ${wordFor(came.read, "line", "lines")} read</div>`
    + `<div><b>${esc(came.imported)}</b> now waiting</div>`
    + `<div><b>${esc(came.already_held)}</b> already held</div></div>`
    + (came.unreadable.length
      ? `<p class="refusal">${esc(came.unreadable.length)} `
        + `${wordFor(came.unreadable.length, "line was", "lines were")} not a JSON object and `
        + `${wordFor(came.unreadable.length, "was", "were")} left out — `
        + `${wordFor(came.unreadable.length, "line", "lines")} ${esc(came.unreadable.join(", "))}. `
        + "Everything else imported.</p>"
      : "");
  return true;
}

export const pastingOpen = () => $("pasting").hidden;

export const markDrop = on => $("drop").classList.toggle("over", on);
