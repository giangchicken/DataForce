// The loader, proved before anything rests on it.
//
// `app.js` imports nothing today, so loading it says only that a module compiles. What the split
// will rest on is the rest of `dom.js`'s loader, and this is where it is held: a specifier
// resolved against the file that wrote it, one instance of a module two others import, a bare
// specifier refused the way a browser refuses one, and a module that throws while it is evaluated
// taking the run down rather than leaving an empty page for every check to pass against.
//
// The pages here are written out rather than kept beside the real one: what they prove is the
// loader, and a fixture under `ui/` would be a module the page does not have. **One of them puts a
// module in a subdirectory**, which the real tree never will -- not to plan for a nested `ui/`,
// but because resolving against the importer and resolving against the entry give the same answer
// in a flat directory, so a flat fixture cannot tell the rule it claims from the wrong one.
//
// Usage: loading.js <a directory to write the fixture pages into>
const fs = require("fs");
const path = require("path");
const { build } = require("./dom");

const INTO = process.argv[2];

let failed = 0;
function fails(said) {
  failed += 1;
  process.exitCode = 1;
  console.log(`FAIL  ${said}`);
}
const claims = (said, ok) => (ok ? console.log(`  ok  ${said}`) : fails(said));

process.on("unhandledRejection", error =>
  fails(`a promise was left rejected: ${error && error.stack ? error.stack : error}`));

// One page, written into its own directory, answered with the path `build` takes.
function write(named, files) {
  const at = path.join(INTO, named);
  for (const [name, text] of Object.entries(files)) {
    const file = path.join(at, name);
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(file, text, "utf8");
  }
  return path.join(at, "app.js");
}

const PAGE = '<div id="out"></div>\n<script type="module" src="app.js"></script>\n';
const said = error => (error && error.message) || String(error);

// What `build` threw, or `null` where it did not throw at all.
async function broke(app) {
  try {
    await build({}, app);
  } catch (error) {
    return said(error);
  }
  return null;
}

(async () => {
  // `shared.js` pushes nothing itself, so the text on the page counts what each half saw: `1,2`
  // where one array was shared, `1,1` where the module was evaluated twice and each half got an
  // array of its own. And `deep/two.js` reaches it as `../shared.js`, which is only the same file
  // if the specifier was resolved against `deep/` -- against the entry it is a path out of the
  // fixture, and the run dies on a file that is not there.
  const linked = write("links", {
    "index.html": PAGE,
    "app.js": [
      'import { mine as first } from "./one.js";',
      'import { mine as second } from "./deep/two.js";',
      'document.getElementById("out").textContent = `${first},${second}`;'
    ].join("\n"),
    "one.js": 'import { seen } from "./shared.js";\nseen.push("one");\nexport const mine = seen.length;',
    "deep/two.js": 'import { seen } from "../shared.js";\nseen.push("two");\nexport const mine = seen.length;',
    "shared.js": "export const seen = [];"
  });
  const page = await build({}, linked);
  claims("a module reaches the same DOM a script reached", page.el("out").textContent !== "");
  claims("**a specifier is resolved against the file that wrote it**, not against the page",
    page.el("out").textContent.includes(","));
  claims("**a module two others import is evaluated once**, so what it holds is one state",
    page.el("out").textContent === "1,2");

  // The file is right there beside the importer, so path resolution finds it and the page loads.
  // A browser does not, and this is the one failure a stub cannot be allowed to be kinder about.
  const bare = write("bare", {
    "index.html": PAGE,
    "app.js": 'import { seen } from "shared.js";\ndocument.getElementById("out").textContent = seen.length;',
    "shared.js": "export const seen = [];"
  });
  const refused = await broke(bare);
  claims("**a bare specifier is refused though the file is next door**, as a browser refuses it",
    refused !== null && refused.includes('imports "shared.js"'));

  const throwing = write("throws", {
    "index.html": PAGE,
    "app.js": 'import "./bad.js";\ndocument.getElementById("out").textContent = "started";',
    "bad.js": 'throw new Error("this module is broken");'
  });
  claims("**a module that throws takes the run down**, rather than leaving an empty page to pass",
    (await broke(throwing)) === "this module is broken");

  console.log(failed ? `\n${failed} failed` : "\nthe loader holds");
})();
