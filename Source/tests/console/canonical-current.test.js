// Отдельное свидетельство над нынешним JS. Случаи не переписывают код модуля.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const {createHash} = require("node:crypto");
const {spawnSync} = require("node:child_process");

const file = path.resolve(__dirname, "../../../Platform/07-console-module/module/console.js");
const sha256 = createHash("sha256").update(fs.readFileSync(file)).digest("hex");
const fixtures = [
  "module-calls", "module-changes", "module-retry", "module-may",
  "module-shared-schema", "module-card-markup", "module-refusal-field", "module-form-if-match",
  "module-refresh-event"
];
let failed = false;
for (const fixture of fixtures) {
  const child = spawnSync(process.execPath, [path.join(__dirname, fixture + ".test.js")], {
    cwd: __dirname,
    env: {...process.env, PC_MODULE_SOURCE: "canonical"},
    encoding: "utf8", timeout: 60000, maxBuffer: 1024 * 1024
  });
  try {
    assert.ifError(child.error);
    assert.equal(child.status, 0, "fixture exit");
    assert.equal(child.stderr, "", "unexpected runtime diagnostics");
    const lines = child.stdout.split("\n");
    const inputs = lines.filter(line => line.startsWith("PC_MODULE_INPUT "));
    assert.equal(inputs.length, 1, "exactly one canonical input receipt");
    assert.deepEqual(JSON.parse(inputs[0].slice("PC_MODULE_INPUT ".length)), {file, sha256});
    const start = lines.indexOf("{");
    const end = lines.lastIndexOf("}");
    assert.ok(start >= 0 && end > start, "fixture report exists");
    const report = JSON.parse(lines.slice(start, end + 1).join("\n"));
    if ("errors" in report) assert.deepEqual(report.errors, [], "browser errors");
    assert.ok(Object.values(report).some(value => value === true), "nonempty assertions");
    assert.ok(lines.includes("все проверки пройдены"), "fixture assertions passed");
    assert.ok(!/^FAILED/m.test(child.stdout), "no failed assertions");
    console.log(JSON.stringify({fixture, file, sha256, result: "PASS", assertions: report}));
  } catch (error) {
    failed = true;
    console.error(fixture + ": " + error.message);
    process.stdout.write(child.stdout || "");
    process.stderr.write(child.stderr || "");
  }
}
if (failed) {
  console.log("FAILED: canonical-current");
  process.exitCode = 1;
}
