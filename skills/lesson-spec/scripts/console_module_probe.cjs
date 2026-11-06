// Independent P07 judge. Never imports the author's converter or its maps/tests.
// Test dependencies: acorn 8.15.0, jsdom 26.1.0; pass their home with NODE_PATH.
"use strict";
const fs = require("fs"), path = require("path"), crypto = require("crypto");
const acorn = require("acorn"), {JSDOM} = require("jsdom");
for (const [name, version] of [["acorn", "8.15.0"], ["jsdom", "26.1.0"]]) {
  if (require(name + "/package.json").version !== version) throw Error("judge dependency pin: " + name + "@" + version);
}
const ROOT = path.resolve(process.argv[3]);
const home = "Platform/07-console-module/";
const digest = data => crypto.createHash("sha256").update(data).digest("hex");
const hashes = {
  js: "9e0356451fcc3c143aacdc643da3881d57936dc91b3315eb6125c35f5a404c71",
  css: "049db5be822fd7e8a01f2345a9d787dcad136a941ed41c255763c05a1cdc7989",
  html: "639676470e26202738b14bc0bd8b8500ab8612e8ec85aad099578df7edf46968",
};
const read = name => fs.readFileSync(path.join(ROOT, name), "utf8");
const parse = text => acorn.parse(text, {ecmaVersion: 2022, sourceType: "script"});
function clean(x) {
  if (Array.isArray(x)) return x.map(clean);
  if (x && typeof x === "object") return Object.fromEntries(Object.entries(x)
    .filter(([key]) => !["start", "end", "raw"].includes(key)).map(([key, v]) => [key, clean(v)]));
  return x;
}
const same = (a, b) => JSON.stringify(clean(a)) === JSON.stringify(clean(b));
function walk(node, fn) {
  if (!node || typeof node !== "object") return;
  if (node.type) fn(node);
  for (const value of Object.values(node)) {
    if (Array.isArray(value)) value.forEach(x => walk(x, fn));
    else if (value && typeof value === "object") walk(value, fn);
  }
}
function declarations(tree, name) {
  const out = [];
  walk(tree, n => {
    if (n.type === "VariableDeclaration" && n.declarations.some(d => d.id.name === name)) out.push(n);
  });
  if (out.length !== 1 || out[0].kind !== "const" || out[0].declarations.length !== 1)
    throw Error("one const declaration required: " + name);
  return out[0];
}
function parts(text) {
  const tree = parse(text), found = [];
  walk(tree, n => {if (n.type === "FunctionDeclaration" && n.id.name === "mount") found.push(n);});
  if (found.length !== 1) throw Error("one mount required");
  const decl = Object.fromEntries(["WORDS", "W", "fmt", "fmtDay"].map(n => [n, declarations(tree, n)]));
  const init = Object.fromEntries(Object.entries(decl).map(([k, n]) => [k, n.declarations[0].init]));
  return {tree, mount: found[0], decl, init};
}
function object(node, duplicates, prefix = []) {
  if (node.type === "Literal" && typeof node.value === "string") return node.value;
  if (node.type !== "ObjectExpression") throw Error("WORDS contains a nonliteral at " + prefix.join("/"));
  const result = Object.create(null);
  for (const p of node.properties) {
    if (p.type !== "Property" || p.computed || p.method || p.kind !== "init") throw Error("WORDS property form");
    const key = p.key.type === "Identifier" ? p.key.name : p.key.value;
    if (typeof key !== "string") throw Error("WORDS string key required");
    if (!duplicates && Object.hasOwn(result, key)) throw Error("duplicate WORDS property: " + [...prefix, key]);
    result[key] = object(p.value, duplicates, [...prefix, key]); // witness duplicates use their effective last value
  }
  return result;
}
function leaves(value, prefix = [], result = new Map()) {
  for (const [k, v] of Object.entries(value)) {
    const at = [...prefix, k];
    if (typeof v === "string") {
      const key = at.join(".");
      if (result.has(key)) throw Error("ambiguous flat WORDS key: " + key);
      result.set(key, {at, value: v});
    } else leaves(v, at, result);
  }
  return result;
}
function table(text) {
  const rows = text.split("\n"), result = new Map();
  if (rows.shift() !== "key\ten\tru" || text.includes("\r") || !text.endsWith("\n")) throw Error("TSV header/LF");
  for (const line of rows) {
    if (!line) continue;
    const cells = line.split("\t");
    if (cells.length !== 3 || !cells[0] || result.has(cells[0])) throw Error("TSV duplicate/width/key");
    result.set(cells[0], {en: cells[1], ru: cells[2]}); // no trim: loginAt's terminal U+0020 matters
  }
  return result;
}
const params = text => [...text.matchAll(/\{([^{}]+)\}/g)].map(m => m[1]).sort();
function tokens(text, ranges = []) {
  return [...acorn.tokenizer(text, {ecmaVersion: 2022})]
    .filter(t => !ranges.some(([a, b]) => t.start >= a && t.end <= b))
    .map(t => text.slice(t.start, t.end));
}
function protectedTree(subject) {
  const replaced = new Map(["WORDS", "W", "fmtDay"].map(n => [subject.init[n], {type: "JudgeHole", name: n}]));
  function copy(x) {
    if (replaced.has(x)) return replaced.get(x);
    if (Array.isArray(x)) return x.filter(n => n !== subject.decl.fmt).map(copy);
    if (x && typeof x === "object") return Object.fromEntries(Object.entries(x)
      .filter(([k]) => !["start", "end", "raw"].includes(k)).map(([k, v]) => [k, copy(v)]));
    return x;
  }
  return copy(subject.tree);
}
function ranges(subject) {
  return [...["WORDS", "W", "fmtDay"].map(n => [subject.init[n].start, subject.init[n].end]),
    [subject.decl.fmt.start, subject.decl.fmt.end]];
}
function cssWithoutComments(text) {
  let out = "", quote = "";
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (c === "\\") {out += c + (text[++i] || ""); continue;}
    if (quote) {out += c; if (c === quote) quote = ""; continue;}
    if (c === '"' || c === "'") {quote = c; out += c; continue;}
    if (text.slice(i, i + 2) === "/*") {
      const end = text.indexOf("*/", i + 2);
      if (end < 0) throw Error("unclosed CSS comment");
      i = end + 1;
    } else out += c;
  }
  return out;
}
function htmlProtected(text) {
  const doc = new JSDOM(text, {includeNodeLocations: true}), scripts = [], edits = [];
  for (const script of doc.window.document.querySelectorAll("script")) {
    const loc = doc.nodeLocation(script);
    if (!loc.endTag) throw Error("unclosed script");
    scripts.push({ast: clean(parse(script.textContent)), tokens: tokens(script.textContent)});
    edits.push([loc.startTag.endOffset, loc.endTag.startOffset]);
  }
  let raw = text;
  for (const [a, b] of edits.reverse()) raw = raw.slice(0, a) + "OWNED_SCRIPT" + raw.slice(b);
  doc.window.close();
  return {markup: raw.replace(/<!--[\s\S]*?-->/g, ""), scripts};
}
function audit(input) {
  const errors = [], need = (yes, label) => {if (!yes) errors.push(label);};
  const old = parts(input.old.js), current = parts(input.fresh.js);
  const witness = object(old.init.WORDS, true), actual = object(current.init.WORDS, false), rows = table(input.tsv);
  need(rows.size === 519, "519 TSV keys");
  need(Object.keys(actual).sort().join() === "en,ru", "only EN/RU WORDS");
  for (const lang of ["en", "ru"]) {
    const before = leaves(witness[lang]), after = leaves(actual[lang]);
    need(before.size === 519 && after.size === 519, "519 WORDS leaves " + lang);
    need([...before.keys()].sort().join("\0") === [...rows.keys()].sort().join("\0"), "witness TSV roster " + lang);
    need([...after.keys()].sort().join("\0") === [...rows.keys()].sort().join("\0"), "actual TSV roster " + lang);
    for (const [key, row] of rows) {
      const a = after.get(key), b = before.get(key);
      need(a && b && same(a.at, b.at), "property path " + lang + ":" + key);
      need(a && a.value === row[lang], "decoded WORDS TSV " + lang + ":" + key);
      need(b && b.value === row[lang], "witness TSV value " + lang + ":" + key);
      need(a && b && same(params(a.value), params(b.value)), "parameters " + lang + ":" + key);
      need(same(params(row.en), params(row.ru)), "EN/RU parameters " + key);
    }
    need(actual[lang].glass === witness[lang].glass, "effective glass " + lang);
    need(actual[lang].loginAt.endsWith(" ") && actual[lang].loginAt === witness[lang].loginAt,
      "terminal U+0020 loginAt " + lang);
  }
  const expression = code => parse("const x = " + code + ";").body[0].declarations[0].init;
  need(same(current.init.W, expression('opts.lang === "ru" ? WORDS.ru : WORDS.en')), "exact language selector");
  need(same(current.init.fmt, expression('t => (t ? new Date(t * 1000).toLocaleString(W === WORDS.ru ? "ru-RU" : "en-US") : "—")')), "exact fmt shape");
  need(same(current.init.fmtDay, expression('t => t ? new Date(t * 1000).toLocaleString(W === WORDS.ru ? "ru-RU" : "en-US", {day:"2-digit",month:"2-digit",hour:"2-digit",minute:"2-digit",hour12:false}) : "—"')), "exact fmtDay shape");
  const body = current.mount.body.body, at = body.indexOf(current.decl.W);
  need(at >= 0 && body[at + 1] === current.decl.fmt, "fmt immediately after per-mount W");
  need(same(protectedTree(old), protectedTree(current)), "AST outside four approved blocks");
  need(same(tokens(input.old.js, ranges(old)), tokens(input.fresh.js, ranges(current))), "tokens outside four approved blocks");
  need(cssWithoutComments(input.old.css) === cssWithoutComments(input.fresh.css), "CSS outside comments");
  need(same(htmlProtected(input.old.html), htmlProtected(input.fresh.html)), "HTML markup/inline JS outside comments");
  for (const ext of ["js", "css", "html"]) {
    need(digest(input.old[ext]) === hashes[ext], "frozen witness SHA " + ext);
    need(!/\p{Script=Cyrillic}/u.test(input.fresh[ext]), "raw Cyrillic " + ext);
  }
  return {errors, counts: {tsv: rows.size, languages: 2, witnesses: 3, approvedBlocks: 4}};
}
function inputs() {
  const old = {}, fresh = {};
  for (const ext of ["js", "css", "html"]) {
    old[ext] = read("Source/w2cplatform/console." + ext);
    fresh[ext] = read(home + "module/console." + ext);
  }
  return {old, fresh, tsv: read(home + "data/localization.tsv")};
}
function mutants(input) {
  const out = [], original = audit(input);
  if (original.errors.length) throw Error("unclean mutant baseline: " + original.errors);
  function test(name, edit, needle) {
    const changed = structuredClone(input); edit(changed);
    let errors;
    try {errors = audit(changed).errors;} catch (e) {errors = [e.message];}
    if (!errors.some(e => e.includes(needle))) throw Error("mutant survived its rule: " + name + " / " + errors);
    out.push({name, rule: needle, errors});
  }
  function words(x, edit) {
    const current = parts(x.fresh.js), value = object(current.init.WORDS, false); edit(value);
    x.fresh.js = x.fresh.js.slice(0, current.init.WORDS.start) + JSON.stringify(value) + x.fresh.js.slice(current.init.WORDS.end);
  }
  test("missing WORDS key", x => words(x, w => {delete w.en.unsaved;}), "actual TSV roster");
  test("duplicate WORDS property", x => {
    const p = parts(x.fresh.js), value = object(p.init.WORDS, false), raw = JSON.stringify(value);
    x.fresh.js = x.fresh.js.slice(0, p.init.WORDS.start) + raw.slice(0, -1) + ',"en":' + JSON.stringify(value.en) + '}' + x.fresh.js.slice(p.init.WORDS.end);
  }, "duplicate WORDS property");
  test("missing TSV key", x => {x.tsv = x.tsv.split("\n").filter(l => !l.startsWith("unsaved\t")).join("\n");}, "519 TSV keys");
  test("duplicate TSV key", x => {x.tsv += x.tsv.split("\n")[1] + "\n";}, "TSV duplicate");
  test("changed substitution", x => words(x, w => {w.en.newGroupIn = w.en.newGroupIn.replace("{p}", "{wrong}");}), "parameters en:newGroupIn");
  test("trimmed loginAt", x => words(x, w => {w.ru.loginAt = w.ru.loginAt.trimEnd();}), "terminal U+0020 loginAt");
  test("wrong effective glass", x => words(x, w => {w.en.glass = "wrong";}), "effective glass");
  test("split dotted event key", x => words(x, w => {
    const key = Object.keys(w.en.kinds).find(k => k.includes(".")), value = w.en.kinds[key];
    delete w.en.kinds[key]; const names = key.split("."); let at = w.en.kinds;
    for (const name of names.slice(0, -1)) at = at[name] || (at[name] = {});
    at[names.at(-1)] = value;
  }), "property path en:kinds.");
  test("browser fallback", x => {x.fresh.js = x.fresh.js.replace('opts.lang === "ru" ? WORDS.ru : WORDS.en',
    'WORDS[opts.lang] || WORDS[(navigator.language || "").startsWith("ru") ? "ru" : "en"]');}, "exact language selector");
  test("wrong milliseconds", x => {x.fresh.js = x.fresh.js.replace("t * 1000", "t * 100");}, "exact fmt shape");
  test("extra timezone", x => {x.fresh.js = x.fresh.js.replace('hour12: false', 'hour12: false, timeZone: "UTC"');}, "exact fmtDay shape");
  test("extra public API", x => {x.fresh.js = x.fresh.js.replace("const C = { version: VERSION };",
    "const C = { version: VERSION, foreign: true };");}, "outside four approved blocks");
  test("Cyrillic comment", x => {x.fresh.js += "\n// \u0416\n";}, "raw Cyrillic js");
  test("CSS token change", x => {x.fresh.css += "\nbody{color:red}\n";}, "CSS outside comments");
  test("HTML inline code change", x => {x.fresh.html = x.fresh.html.replace("version === 1", "version === 2");}, "HTML markup/inline JS");
  test("HTML markup change", x => {x.fresh.html = x.fresh.html.replace('<div id="app">', '<div id="foreign">');}, "HTML markup/inline JS");
  for (const ext of ["js", "css", "html"]) test("frozen witness " + ext, x => {
    x.old[ext] += ext === "js" ? "\n// changed\n" : ext === "css" ? "\n/* changed */\n" : "\n<!-- changed -->\n";
  }, "frozen witness SHA " + ext);
  return {errors: [], mutants: out};
}
function expose(text) {
  const subject = parts(text), returns = subject.mount.body.body.filter(n => n.type === "ReturnStatement" && n.argument.name === "C");
  if (returns.length !== 1) throw Error("one final mount return C required");
  const at = returns[0].start;
  return text.slice(0, at) + "C.__judge = {W, fmt, fmtDay};\n" + text.slice(at);
}
async function runtime(text, languages) {
  const dom = new JSDOM("<!doctype html><html lang=ru><body></body></html>", {runScripts: "outside-only", url: "http://judge.invalid/"});
  const w = dom.window, requests = [], dates = [], mounts = [];
  Object.defineProperty(w.navigator, "language", {value: "ru-RU"});
  const NativeDate = w.Date;
  w.Date = class extends NativeDate {
    constructor(...args) {super(...args); this.__args = args;}
    toLocaleString(...args) {dates.push({constructor: this.__args, args}); return "OWNED_DATE";}
  };
  w.matchMedia = () => ({matches: false, addEventListener() {}, removeEventListener() {}});
  w.fetch = async (url, init = {}) => {
    requests.push({url: String(url), method: init.method || "GET"});
    const bodies = {"/session": {open: false}, "/manifest": {name: "probe", rows: "things"},
      "/mounts": {mounts: {}}, "/things": {rows: []}, "/servers": {servers: {}}, "/where": {}, "/metrics": {}};
    const known = Object.hasOwn(bodies, url), body = known ? bodies[url] : {};
    return {ok: known, status: known ? 200 : 404, headers: {get: () => "application/json"},
      json: async () => body, text: async () => JSON.stringify(body)};
  };
  try {
    w.eval(expose(text));
    const surface = {keys: Object.keys(w.PlatformConsole).sort(), version: w.PlatformConsole.version,
      features: Array.from(w.PlatformConsole.features)};
    for (const lang of languages) {
      const root = w.document.createElement("div"); w.document.body.append(root);
      const opts = lang === undefined ? {} : {lang};
      const c = w.PlatformConsole.mount(root, opts);
      opts.lang = lang === "ru" ? "en" : "ru"; // the caller's mutable object must not change this mount's choice
      await Promise.race([c.ready, new Promise((_, reject) => setTimeout(() => reject(Error("mount ready timeout")), 1500))]);
      mounts.push({c, root, lang});
    }
    const result = [];
    for (const {c, root, lang} of [...mounts].reverse().concat(mounts)) {
      const cases = [];
      for (const t of [undefined, null, false, 0, "", NaN, 1, 1.25, -2, "3"]) {
        for (const name of ["fmt", "fmtDay"]) {
          dates.length = 0;
          const value = c.__judge[name](t);
          cases.push({name, truthy: !!t, milliseconds: t ? t * 1000 : null, value, dates: structuredClone(dates)});
        }
      }
      result.push({lang: lang === undefined ? "<omitted>" : lang, words: c.__judge.W,
        login: root.querySelector(".pc-login-t").textContent, cases,
        api: Object.keys(c).filter(n => n !== "__judge").sort()});
    }
    return {surface, mounts: result, requests};
  } finally {w.close();}
}
async function main() {
  const input = inputs(), mode = process.argv[2];
  if (mode === "audit") return audit(input);
  if (mode === "mutants") return mutants(input);
  if (mode === "dom") return {errors: [], current: await runtime(input.fresh.js, [undefined, "en", "ru", "RU", "ru-RU", null]),
    witness: await runtime(input.old.js, ["en"])};
  if (mode === "dom-mutants") {
    const result = [];
    for (const [name, before, after] of [
      ["browser fallback", 'opts.lang === "ru" ? WORDS.ru : WORDS.en', 'WORDS[(navigator.language || "").startsWith("ru") ? "ru" : "en"]'],
      ["milliseconds", "t * 1000", "t * 100"],
      ["timezone", "hour12: false", 'hour12: false, timeZone: "UTC"'],
      ["mutable opts", 'W === WORDS.ru ? "ru-RU" : "en-US"', 'opts.lang === "ru" ? "ru-RU" : "en-US"'],
    ]) {
      if (input.fresh.js.split(before).length < 2) throw Error("missing DOM mutant anchor " + name);
      const changed = await runtime(input.fresh.js.replace(before, after), [undefined, "ru"]);
      const bad = changed.mounts.some(m => m.login !== table(input.tsv).get("login")[m.lang === "ru" ? "ru" : "en"] ||
        m.cases.some(c => c.truthy && (c.dates[0].constructor[0] !== c.milliseconds ||
          c.dates[0].args[0] !== (m.lang === "ru" ? "ru-RU" : "en-US") || c.dates[0].args[1]?.timeZone)));
      if (!bad) throw Error("DOM mutant survived: " + name);
      result.push(name);
    }
    return {errors: [], rejected: result};
  }
  throw Error("unknown fixed judge mode");
}
main().then(result => {process.stdout.write(JSON.stringify(result) + "\n"); process.exitCode = result.errors.length ? 1 : 0;})
  .catch(error => {process.stdout.write(JSON.stringify({errors: [error.stack]}) + "\n"); process.exitCode = 1;});
