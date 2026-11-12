// Источник выбран явно: прежние проверки по умолчанию сохраняют замороженный вход.
// canonical-current.test.js запускает те же случаи отдельно на нынешнем каноне.
const fs = require("node:fs");
const path = require("node:path");
const {createHash} = require("node:crypto");

module.exports = function readModule() {
  const mode = process.env.PC_MODULE_SOURCE || "frozen";
  if (!["frozen", "canonical"].includes(mode)) throw new Error("Unknown PC_MODULE_SOURCE: " + mode);
  const file = mode === "canonical"
    ? path.resolve(__dirname, "../../../Platform/07-console-module/module/console.js")
    : path.resolve(__dirname, "../../w2cplatform/console.js");
  const bytes = fs.readFileSync(file);
  if (mode === "canonical") {
    console.log("PC_MODULE_INPUT " + JSON.stringify({file, sha256: createHash("sha256").update(bytes).digest("hex")}));
  }
  return bytes.toString("utf8");
};
