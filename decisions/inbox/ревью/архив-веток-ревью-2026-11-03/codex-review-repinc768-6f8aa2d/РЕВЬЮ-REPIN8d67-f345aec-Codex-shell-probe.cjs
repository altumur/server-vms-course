'use strict';
// Independent calls of the published tools; run only by CT103, no SUT.
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const {JSDOM} = require('jsdom');
const [engine, specs, before, after] = process.argv.slice(2);
const {sourceCore} = require(path.join(engine, 'main.cjs'));
const {consoleFixture} = require(path.join(engine, 'console.cjs'));
const read = name => fs.readFileSync(path.join(specs, name), 'utf8');
const harness = {system: read('VMS/10-assist/harness/system.md'),
  tools: JSON.parse(read('VMS/10-assist/harness/tools.json')),
  words: JSON.parse(read('VMS/10-assist/harness/words.json'))};
const original = JSON.parse(read('VMS/10-assist/vectors/plan-check/stand3.console.json'));

async function exercise(page) {
  const dom = new JSDOM('<body>', {runScripts: 'outside-only', url: 'https://vms.test/'});
  try {
    dom.window.eval(sourceCore(fs.readFileSync(page, 'utf8')) + '\n;globalThis.reviewCore=makeAssist(' + JSON.stringify(harness) + ');');
    const core = dom.window.reviewCore;
    const doc = JSON.parse(JSON.stringify(original));
    doc.session = {open: true};
    const ids = ['\u{10000}', '\ue000', 'Z', 'a'];
    const values = [10, 2, -1, false, true, '\u{10000}', '\ue000', 'a'];
    doc.rows.testsub2 = ids.map((id, i) => ({id, name: id, revision: 1, of: 'Alder', tags: i === 0 ? values : []}));
    const fixture = consoleFixture(doc);
    const turn = core.newTurn();
    const tools = core.tools(fixture, turn);
    const found = JSON.parse((await tools.call('find_units', {sub: 'testsub2'})).content);
    const counts = JSON.parse((await tools.call('field_values', {sub: 'testsub2', field: 'tags'})).content);
    const units = found.units.map(row => row.unit);
    const order = counts.values.map(row => row.value);
    assert.equal(found.count, 4);
    assert(counts.values.every(row => row.units === 1));
    return {units, values: order, reads: fixture.calls};
  } finally { dom.window.close(); }
}

(async () => {
  const old = await exercise(before), current = await exercise(after);
  assert.deepEqual(current.units, ['testsub2/Z', 'testsub2/a', 'testsub2/\ue000', 'testsub2/\u{10000}']);
  assert.deepEqual(current.values, ['a', '\ue000', '\u{10000}', -1, 2, 10, false, true]);
  assert.notDeepEqual(old.units, current.units);
  assert.notDeepEqual(old.values, current.values);
  console.log(JSON.stringify({before: old, after: current,
    unicode_id_order: true, unicode_string_order: true, numeric_value_order: true,
    mixed_json_type_order: true, boolean_order: true}));
})().catch(error => { console.error(error); process.exitCode = 1; });
