// The page handed what the routes really answered, rather than a fixture somebody wrote.
//
// `page.js` proves the page reads what this repository's tests think a route's answer looks like.
// This proves it reads what the service actually says, which is a different claim: the field names
// are written in `profile/tool_decision/schema.py` and read in `ui/app.js`, and nothing else holds
// the two together. `test_page.py` imports a file and stores samples through the real routes, asks
// them, and passes the answers in.
//
// Usage: reading.js <directory holding models.json, queued.json and stats.json> [app.js]
const fs = require("fs");
const path = require("path");
const { build, settled } = require("./dom.js");

const FROM = process.argv[2];
const APP = process.argv[3] || path.join(__dirname, "..", "..", "src", "dataforce", "ui", "app.js");

let failed = 0;
function fails(said) {
  failed += 1;
  process.exitCode = 1;
  console.log(`FAIL  ${said}`);
}
const claims = (said, ok) => (ok ? console.log(`  ok  ${said}`) : fails(said));

process.on("unhandledRejection", error =>
  fails(`the page threw rather than saying anything: ${error && error.stack ? error.stack : error}`));

const read = named => JSON.parse(fs.readFileSync(path.join(FROM, named), "utf8"));

(async () => {
  const queued = read("queued.json");
  const real = read("stats.json");
  const served = read("models.json");
  const page = build({
    // The route's own answer, not this file's idea of one. A `models` key read off an array is
    // `undefined` on every deployment, and the only thing that catches it is asking the service.
    models: served,
    statistics: real,
    // The queue answer as the route gave it, sample and all.
    queue: [queued.sample],
    // Enough for one submit to get through, so the key can be followed all the way back.
    redacted: {
      messages: queued.sample.messages,
      tools: queued.sample.tools,
      label: queued.sample.label ?? null
    }
  }, APP);
  for (let n = 0; n < 8; n += 1) await settled();

  const strip = page.byId.get("strip").innerHTML;
  const stats = page.byId.get("stats").innerHTML;
  const turns = page.byId.get("turns").innerHTML;

  // ---------------------------------------------------------------------- what /models answered
  claims("the models the deployment serves are drawn as something to tick",
    served.every(name => page.byId.get("verifier-ticks").innerHTML.includes(name)));
  claims("**and a verifier is picked**, so the scan is not refused for a tick nobody could make",
    page.inputsNamed("verifier").some(box => box.checked));

  // ---------------------------------------------------------------- what /queue/next answered
  claims("the sample the queue answered is drawn as a conversation",
    turns.includes("role") === false && turns.length > 0);
  claims("its turns are on the screen",
    queued.sample.messages.every(turn => turns.includes(turn.content)));
  claims("the import gave the sample a name and the page shows it",
    page.byId.get("sample-name").textContent.includes(queued.sample.id));
  claims("the catalog the sample carries is drawn",
    page.byId.get("catalog").innerHTML.includes(queued.sample.tools[0].function.name));

  // ---------------------------------------------------------------- what /records/stats answered
  claims("the strip counts the rows the route says are stored", strip.includes("<b>2</b> rows stored"));
  claims("and does not fall back to saying there is no database",
    !page.byId.get("strip").className.includes("none"));
  // Two samples, three of the fifteen pairs carried: one fires one way, the other fires two. The
  // fifteen is five domains against three triggers -- four this page declares, plus the one only
  // the corpus knows about.
  claims("twelve of the fifteen cells are still empty",
    strip.includes("<b>12</b> of 15 cells still empty"));

  claims("the matrix is drawn", stats.includes('<table class="matrix"'));
  // Counted inside the matrix and not across the panel: every count table under it draws cells too,
  // so a tally over the whole panel would pass on somebody else's arithmetic.
  const matrix = stats.slice(stats.indexOf('<table class="matrix"'), stats.indexOf("</table>"));
  claims("a pair the corpus carries reads as one",
    (matrix.match(/<td class="cell">1<\/td>/g) || []).length === 3);
  claims("and the twelve it does not read as empty",
    (matrix.match(/cell zero/g) || []).length === 12);
  claims("every axis value is one this page can tick", !matrix.includes("axis gone"));
  // **The end of *add a domain*.** One was stored under a name nothing on this page declares, and
  // the page reads it back off the corpus -- so it is a thing to tick again after a reload, which
  // is the only thing that makes adding one more than a note to oneself.
  claims("a domain only the corpus knows about is offered as something to tick",
    page.byId.get("domain-ticks").innerHTML.includes("insurance_claims"));

  claims("how many rows the corpus holds is read", stats.includes("<b>2</b> rows"));
  claims("how many rows answered at all is read", stats.includes("<b>2</b> answered with a call"));
  claims("how many distinct answers is read", stats.includes("<b>1</b> distinct answer"));
  claims("a figure of one does not read as many", !stats.includes("<b>1</b> distinct answers"));
  claims("how many tools were offered is read",
    stats.includes("<b>1</b> tool the catalogs put in front of the model"));
  claims("the tools the labels call are named by name", stats.includes("OpenTicket"));
  claims("the same input twice is counted", /<b>\d+<\/b> groups? agreeing/.test(stats));
  claims("every facet the table carries has its own count", stats.includes("number_label_tools"));

  // ---------------------------------------------------- the key, followed all the way back
  // Read off the route's own answer and posted back on submit, which is what marks the queue row
  // done in the same transaction as the two table writes. Nothing else checks this seam: a `key`
  // renamed in Python would leave every record posted without one, and every sample already
  // labelled would be offered again with nothing to say it had been.
  page.inputsNamed("f-domain")[0].checked = true;
  await page.byId.get("submit").onclick();
  for (let n = 0; n < 12; n += 1) await settled();
  const records = page.asked.filter(one => one.path.split("?")[0] === "/records");
  claims("one record is posted", records.length === 1);
  claims("the queue key the route answered travels back with the record",
    records.length === 1
    && records[0].path.includes(`queue_key=${encodeURIComponent(queued.key)}`));

  // ------------------------------------------ a line with no name, named by the real service
  // The seam this exists for, on the path that had no test with a name missing from it. A raw
  // corpus line is `{messages, tools, label}`: nothing writes an `id` into one, and every route
  // from here on reads a sample by name. A page that opened one unnamed gets a 422 from the first
  // check it runs and a 422 from the store, which is exactly what it did.
  const naming = read("named.json");
  const anonymous = fs.readFileSync(path.join(FROM, "anonymous.json"), "utf8");
  const pasting = build({
    models: served,
    statistics: real,
    queue: [],
    named: naming,
    redacted: { messages: [], tools: [], label: null }
  }, APP);
  for (let n = 0; n < 8; n += 1) await settled();

  pasting.el("paste-text").value = anonymous;
  await pasting.el("paste-now").onclick();
  for (let n = 0; n < 8; n += 1) await settled();
  const given = naming.samples[0].id;
  claims("a sample with no name is opened under the name the service gave it",
    pasting.byId.get("sample-name").textContent.includes(given));
  claims("and that name is one the service made, not one the page did",
    given.length === 36 && !anonymous.includes(given));

  pasting.inputsNamed("f-domain")[0].checked = true;
  await pasting.byId.get("submit").onclick();
  for (let n = 0; n < 12; n += 1) await settled();
  const stored = pasting.asked.filter(one => one.path.split("?")[0] === "/records");
  claims("**and it stores under that name**, which is the key the row is written under",
    stored.length === 1 && JSON.parse(stored[0].body).id === given);

  console.log(failed ? `\n${failed} failed` : "\nall green");
})();
