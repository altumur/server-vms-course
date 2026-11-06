// Deterministic migration artifact for ADR-0121(10), not an independent judge.
// The editable word source is the single P/07 TSV. WORDS is its derived projection.
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import vm from "node:vm";
import { fileURLToPath } from "node:url";
import { parse, tokenizer } from "acorn";

const artifact = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(artifact, "../../..");
const BASE = "e07b32a5030c696d89c72444e760a86f6246c487";
const OLD = "Platform/06-console/data/localization.tsv";
const TABLE = "Platform/07-console-module/data/localization.tsv";
const MODULE = "Platform/07-console-module/module/console.";
const SOURCE = "Source/w2cplatform/console.";
const WITNESS = {
  js: "9e0356451fcc3c143aacdc643da3881d57936dc91b3315eb6125c35f5a404c71",
  css: "049db5be822fd7e8a01f2345a9d787dcad136a941ed41c255763c05a1cdc7989",
  html: "639676470e26202738b14bc0bd8b8500ab8612e8ec85aad099578df7edf46968",
};
const TABLE_SHA = "a5b3c4b9c1af6cfe40a72c80b58d2348a9e9517d7c36c0b6ad8a91bc807850e9";
const SELECTOR = 'opts.lang === "ru" ? WORDS.ru : WORDS.en';
const options = { ecmaVersion: 2022, sourceType: "script", locations: true };
const hash = value => crypto.createHash("sha256").update(value).digest("hex");
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const assert = (condition, message) => { if (!condition) throw new Error(message); };
const read = name => fs.readFileSync(path.join(root, name));
const exists = name => fs.existsSync(path.join(root, name));
const cyrillic = /\p{Script=Cyrillic}/u;
const ascii = text => text.replace(/[^\x00-\x7f]/g, c => "\\u" + c.charCodeAt(0).toString(16).padStart(4, "0"));
const params = text => [...text.matchAll(/\{([A-Za-z_]\w*)\}/g)].map(m => m[1]).sort();

function walk(node, visit) {
  if (!node || typeof node !== "object") return;
  if (typeof node.type === "string") visit(node);
  for (const value of Object.values(node)) {
    if (Array.isArray(value)) value.forEach(child => walk(child, visit));
    else if (value && typeof value === "object") walk(value, visit);
  }
}

function declarations(ast, name) {
  const found = [];
  walk(ast, n => { if (n.type === "VariableDeclarator" && n.id.type === "Identifier" && n.id.name === name) found.push(n); });
  return found;
}

function one(ast, name) {
  const found = declarations(ast, name);
  assert(found.length === 1 && found[0].init, "expected one initialized declaration: " + name);
  return found[0].init;
}

// Decode a literal rather than executing it. Repeated properties take their last value.
function dictionary(node) {
  const leaves = new Map(), duplicates = [];
  function object(n, prefix) {
    assert(n.type === "ObjectExpression", "WORDS must contain only objects and string literals");
    const keys = new Set();
    for (const prop of n.properties) {
      assert(prop.type === "Property" && !prop.computed && !prop.method && !prop.shorthand && prop.kind === "init", "nonliteral WORDS property");
      const key = prop.key.type === "Identifier" ? prop.key.name : prop.key.value;
      assert(typeof key === "string", "non-string WORDS key");
      if (keys.has(key)) duplicates.push(prefix.concat(key).join("."));
      keys.add(key);
      const at = prefix.concat(key);
      if (prop.value.type === "ObjectExpression") object(prop.value, at);
      else {
        assert(prop.value.type === "Literal" && typeof prop.value.value === "string", "non-string WORDS value");
        leaves.set(at.join("."), { value: prop.value.value, node: prop.value });
      }
    }
  }
  object(node, []);
  return { leaves, duplicates };
}

function roster(dict, lang) {
  return [...dict.leaves.keys()].filter(k => k.startsWith(lang + ".")).map(k => k.slice(lang.length + 1));
}

function parseTable(bytes, witness) {
  const text = bytes.toString("utf8");
  assert(!text.includes("\r") && !text.startsWith("\ufeff") && text.endsWith("\n"), "TSV must be UTF-8, LF, no BOM, with a final LF");
  const lines = text.slice(0, -1).split("\n");
  assert(lines.shift() === "key\ten\tru", "TSV header must be key/en/ru");
  const rows = [], seen = new Set();
  lines.forEach((line, i) => {
    const cols = line.split("\t");
    assert(cols.length === 3 && cols.every(s => s.trim() !== ""), "three nonempty columns required at TSV line " + (i + 2));
    const [key, en, ru] = cols; // Do not trim values: loginAt ends in U+0020.
    assert(!seen.has(key), "duplicate TSV key: " + key);
    assert(!cyrillic.test(key) && !cyrillic.test(en), "Cyrillic is allowed only in the ru column");
    seen.add(key);
    rows.push({ key, en, ru, line: i + 2 });
  });
  const expected = roster(witness, "en"), expectedRU = roster(witness, "ru");
  assert(same([...expected].sort(), [...expectedRU].sort()), "witness language rosters differ");
  const missing = expected.filter(k => !seen.has(k)), extra = [...seen].filter(k => !expected.includes(k));
  assert(!missing.length && !extra.length, "TSV roster mismatch; missing=" + JSON.stringify(missing) + "; extra=" + JSON.stringify(extra));
  assert(rows.length === 519, "expected exactly 519 TSV keys");
  for (const row of rows) {
    assert(same(params(row.en), params(row.ru)), "parameter mismatch: " + row.key);
    for (const lang of ["en", "ru"]) {
      assert(row[lang] === witness.leaves.get(lang + "." + row.key).value, "value mismatch: " + lang + "." + row.key);
    }
  }
  assert(hash(bytes) === TABLE_SHA, "TSV is not the exact historical table move");
  return rows;
}

function materialize(rows) {
  const words = { en: {}, ru: {} };
  for (const row of rows) for (const lang of ["en", "ru"]) {
    const prefix = row.key.startsWith("kinds.") ? "kinds" : row.key.startsWith("n.") ? "n" : null;
    // Only the first prefix is structural. Dots inside an event kind are literal.
    if (prefix) (words[lang][prefix] ||= {})[row.key.slice(prefix.length + 1)] = row[lang];
    else words[lang][row.key] = row[lang];
  }
  const indent = text => text.split("\n").map((line, i) => i ? "    " + line : line).join("\n");
  const en = indent(JSON.stringify(words.en, null, 2));
  const ru = indent(ascii(JSON.stringify(words.ru, null, 2)));
  return "{\n    en: " + en + ",\n    ru: " + ru + "\n  }";
}

const comments = JSON.parse(fs.readFileSync(path.join(artifact, "comments.json"), "utf8"));
assert(comments.base === BASE, "comment map base mismatch");
function englishComments(source, sourcePath) {
  const lines = source.split("\n");
  for (const item of comments.replacements.filter(x => x.source === sourcePath)) {
    assert(hash(lines[item.line - 1]) === item.sourceLineSha256, "comment source mismatch: " + sourcePath + ":" + item.line);
    assert(!item.replacement.includes("\n") && !cyrillic.test(item.replacement), "invalid English comment replacement");
    lines[item.line - 1] = item.replacement;
  }
  return lines.join("\n");
}

function replaceRanges(source, edits) {
  for (const edit of edits.sort((a, b) => b.start - a.start)) source = source.slice(0, edit.start) + edit.text + source.slice(edit.end);
  return source;
}

function cleanAST(node, holes = []) {
  if (!node || typeof node !== "object") return node;
  const hole = holes.find(h => node === h.node);
  if (hole) return { type: hole.name };
  if (Array.isArray(node)) return node.map(n => cleanAST(n, holes));
  return Object.fromEntries(Object.entries(node).filter(([k]) => !["start", "end", "loc", "range"].includes(k)).map(([k, v]) => [k, cleanAST(v, holes)]));
}

function tokens(source, holes = []) {
  const out = [], used = new Set();
  for (const token of tokenizer(source, options)) {
    const hole = holes.find(h => token.start >= h.node.start && token.end <= h.node.end);
    if (hole) {
      if (!used.has(hole.name)) { out.push([hole.name]); used.add(hole.name); }
    } else out.push([token.type.label, source.slice(token.start, token.end)]);
  }
  assert(used.size === holes.length, "token comparison did not consume every approved hole");
  return out;
}

function verifyJS(before, after, rows) {
  const a = parse(before, options), b = parse(after, options);
  const aw = one(a, "WORDS"), bw = one(b, "WORDS"), al = one(a, "W"), bl = one(b, "W");
  const expectedSelector = parse("const W = " + SELECTOR + ";", options);
  assert(same(cleanAST(bl), cleanAST(one(expectedSelector, "W"))), "unapproved language selector");
  const holesA = [{ name: "DerivedWORDS", node: aw }, { name: "ApprovedLanguageSelector", node: al }];
  const holesB = [{ name: "DerivedWORDS", node: bw }, { name: "ApprovedLanguageSelector", node: bl }];
  const ta = tokens(before, holesA), tb = tokens(after, holesB);
  assert(same(ta, tb), "outside-WORDS/selector token drift");
  const aa = cleanAST(a, holesA), ab = cleanAST(b, holesB);
  assert(same(aa, ab), "outside-WORDS/selector AST drift");
  const old = dictionary(aw), derived = dictionary(bw);
  assert(same([...old.leaves.keys()].sort(), [...derived.leaves.keys()].sort()), "derived dictionary extra/missing keys");
  assert(derived.duplicates.length === 0, "duplicate generated property");
  const map = rows.map(row => {
    const result = { key: row.key, tableLine: row.line, parameters: params(row.en), languages: {} };
    for (const lang of ["en", "ru"]) {
      const key = lang + "." + row.key, x = old.leaves.get(key), y = derived.leaves.get(key);
      assert(y.value === row[lang] && x.value === y.value, "decoded dictionary mismatch: " + key);
      assert(same(params(y.value), params(row[lang])), "decoded parameter mismatch: " + key);
      result.languages[lang] = { valueSha256: hash(y.value), witnessLine: x.node.loc.start.line, moduleLine: y.node.loc.start.line };
    }
    return result;
  });
  const untouchedFormatters = Object.fromEntries(["fmt", "fmtDay"].map(name => {
    const x = one(a, name), y = one(b, name), sa = before.slice(x.start, x.end), sb = after.slice(y.start, y.end);
    assert(sa === sb, "unapproved formatter change: " + name);
    return [name, { unchanged: true, expressionSha256: hash(sa) }];
  }));
  const values = { en: { caption: "en" }, ru: { caption: "ru" } };
  const matrix = [{ lang: null, browser: "ru-RU", expected: "en" }, { lang: "en", browser: "ru-RU", expected: "en" },
    { lang: "ru", browser: "en-US", expected: "ru" }, { lang: "ru-RU", browser: "ru-RU", expected: "en" },
    { lang: "RU", browser: "ru-RU", expected: "en" }].map(c => {
    const result = vm.runInNewContext(after.slice(bl.start, bl.end), { opts: c.lang === null ? {} : { lang: c.lang }, navigator: { language: c.browser }, WORDS: values });
    assert(result.caption === c.expected, "language matrix mismatch");
    return { ...c, actual: result.caption };
  });
  for (const lang of ["en", "ru"]) {
    assert(derived.leaves.get(lang + ".loginAt").value.endsWith(" "), "loginAt lost U+0020");
    assert(derived.leaves.get(lang + ".glass").value === old.leaves.get(lang + ".glass").value, "glass lost last-wins value");
  }
  return { map, check: { normalizedTokenSha256: hash(JSON.stringify(ta)), tokensOutsideApprovedHoles: ta.length,
    normalizedASTSha256: hash(JSON.stringify(aa)), astAndRawTokensExactOutsideTwoHoles: true,
    witnessDuplicateProperties: old.duplicates, generatedDuplicateProperties: derived.duplicates,
    decodedLeavesPerLanguage: rows.length, parameterizedKeys: rows.filter(r => params(r.en).length).length,
    parameterOccurrencesPerLanguage: rows.reduce((n, r) => n + params(r.en).length, 0),
    glassLastWinsExact: true, loginAtFinalU0020Exact: true, formatters: untouchedFormatters, languageMatrix: matrix } };
}

const stripCSSComments = text => text.replace(/\/\*[\s\S]*?\*\//g, "");
function htmlMechanism(text) {
  return text.replace(/<!--[\s\S]*?-->/g, "").replace(/(<script\b[^>]*>)([\s\S]*?)(<\/script>)/g,
    (_, open, body, close) => open + JSON.stringify(tokens(body)) + close);
}

function rejectProof(tableBytes, witness) {
  const text = tableBytes.toString("utf8"), lines = text.trimEnd().split("\n");
  const cases = [
    ["extra-key", text + "notAnExistingKey\tx\tx\n", /roster mismatch.*extra=/],
    ["missing-key", [lines[0], ...lines.slice(2)].join("\n") + "\n", /roster mismatch.*missing=/],
    ["duplicate-key", text + lines[1] + "\n", /duplicate TSV key/],
    ["changed-parameter", text.replace("{p}", "{wrong}"), /parameter mismatch/],
    ["loginAt-space", text.replace(/^(loginAt\t[^\t]*) \t/m, "$1\t"), /value mismatch: en.loginAt/],
  ];
  return cases.map(([name, input, error]) => {
    try { parseTable(Buffer.from(input), witness); } catch (e) {
      assert(error.test(e.message), "unexpected rejection: " + name + ": " + e.message);
      return { name, rejected: true, reason: e.message };
    }
    throw new Error("invalid TSV accepted: " + name);
  });
}

function main() {
  assert(process.argv.length === 3 && ["--write", "--check"].includes(process.argv[2]), "usage: node convert.mjs --write|--check");
  const write = process.argv[2] === "--write";
  const sources = Object.fromEntries(Object.keys(WITNESS).map(ext => {
    const bytes = read(SOURCE + ext);
    assert(hash(bytes) === WITNESS[ext], "immutable witness SHA mismatch: " + ext);
    return [ext, bytes.toString("utf8")];
  }));
  const witness = dictionary(one(parse(sources.js, options), "WORDS"));
  const input = read(exists(TABLE) ? TABLE : OLD);
  const rows = parseTable(input, witness);
  let js = englishComments(sources.js, SOURCE + "js");
  const ast = parse(js, options), words = one(ast, "WORDS"), selector = one(ast, "W");
  js = replaceRanges(js, [{ start: words.start, end: words.end, text: materialize(rows) }, { start: selector.start, end: selector.end, text: SELECTOR }]);
  js = js.replace("  const WORDS = ", "  // Generated WORDS from P/07 data/localization.tsv, SHA-256 " + TABLE_SHA + ". Edit the TSV only.\n  const WORDS = ");
  const outputs = { js, css: englishComments(sources.css, SOURCE + "css"), html: englishComments(sources.html, SOURCE + "html") };
  for (const [ext, output] of Object.entries(outputs)) assert(!cyrillic.test(output), "raw Cyrillic outside ru TSV: " + ext);
  assert(stripCSSComments(sources.css) === stripCSSComments(outputs.css), "CSS behavior changed");
  assert(htmlMechanism(sources.html) === htmlMechanism(outputs.html), "HTML markup or script behavior changed");
  const verified = verifyJS(sources.js, outputs.js, rows);
  const negatives = rejectProof(input, witness);
  // The comparison must also reject a change outside the two approved AST holes.
  const changedBehavior = outputs.js.replace("C.timeoutMs = 20000;", "C.timeoutMs = 19999;");
  assert(changedBehavior !== outputs.js, "behavior rejection probe anchor absent");
  try {
    verifyJS(sources.js, changedBehavior, rows);
    throw new Error("outside-WORDS behavior change accepted");
  } catch (e) {
    assert(e.message === "outside-WORDS/selector token drift", "unexpected behavior rejection: " + e.message);
    negatives.push({ name: "outside-WORDS-behavior", rejected: true, reason: e.message });
  }
  // These checks also run in --check mode before any evidence is trusted.
  assert(exists(TABLE) || write, "canonical P/07 table absent");
  if (write) {
    for (const [ext, content] of Object.entries(outputs)) {
      fs.mkdirSync(path.dirname(path.join(root, MODULE + ext)), { recursive: true });
      fs.writeFileSync(path.join(root, MODULE + ext), content);
    }
    fs.mkdirSync(path.dirname(path.join(root, TABLE)), { recursive: true });
    fs.writeFileSync(path.join(root, TABLE), input);
    if (exists(OLD)) { assert(hash(read(OLD)) === TABLE_SHA, "old table changed"); fs.unlinkSync(path.join(root, OLD)); }
  }
  assert(!exists(OLD), "old table alias/copy remains");
  assert(read(TABLE).equals(input), "canonical TSV byte drift");
  for (const [ext, content] of Object.entries(outputs)) assert(read(MODULE + ext).equals(Buffer.from(content)), "materialized file byte drift: " + ext);
  const evidence = { base: BASE, authorCheckNotIndependentJudge: true, parser: "acorn@8.15.0 / ES2022",
    artifacts: Object.fromEntries(Object.entries(outputs).map(([ext, content]) => [MODULE + ext, { bytes: Buffer.byteLength(content), sha256: hash(content), rawCyrillic: false }])),
    immutableWitnesses: WITNESS, canonicalTable: { path: TABLE, movedFrom: OLD, sha256: hash(input), bytes: input.length, keys: rows.length, oldPathAbsent: true },
    wordsAndBehavior: verified.check, englishCaptionsExactWitness: true, russianEscapesDerivedFromRuOnly: true,
    cssNoncommentBytesExact: true, htmlMarkupAndInlineTokensExact: true,
    rejectedInputs: negatives, inlineCSP: [...outputs.html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => "sha256-" + crypto.createHash("sha256").update(m[1]).digest("base64")) };
  for (const [name, value] of [["map.json", { base: BASE, table: TABLE, entries: verified.map }], ["evidence.json", evidence]]) {
    const content = ascii(JSON.stringify(value, null, 2)) + "\n", file = path.join(artifact, name);
    if (write) fs.writeFileSync(file, content);
    else assert(fs.readFileSync(file, "utf8") === content, "stale evidence: " + name);
  }
  console.log(JSON.stringify({ result: "PASS", mode: write ? "write" : "check", keys: rows.length,
    astAndTokensOutsideWORDSAndSelector: "exact", formatters: "unchanged", newNetworkCalls: 0,
    outputs: evidence.artifacts, tableSha256: hash(input) }, null, 2));
}

try { main(); } catch (e) { console.error("FAIL: " + e.message); process.exitCode = 1; }
