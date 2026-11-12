"""Independent bounded P07 migration judge; no author converter/test imports.

NODE_PATH=<owned acorn8.15.0+jsdom26.1.0>/node_modules python -B -m unittest test_console_module_canon
Copy console_module_probe.package.json to an owned temporary environment's
package.json, then npm install --prefix <that environment> --ignore-scripts.
The Node probe parses actual JS and runs owned DOM/Date/fetch fixtures. The frozen Source witness bounds the 519
migrated captions, CSS and HTML; the code outside the four localization blocks and the three later captions are
pinned to the accepted common slice ADR-0083 (145) (change 0083-common-source145). It changes
only an in-memory return epilogue to expose the selected closure for observations.
It does not rewrite a module, run a server, or prove C6/A1/runtime acceptance.
"""
import json
import os
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PROBE = Path(__file__).with_name("console_module_probe.cjs")


class ConsoleModuleCanon(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        text = (ROOT / "Platform/07-console-module/data/localization.tsv").read_bytes().decode("utf-8")
        lines = text.split("\n")
        if lines.pop(0) != "key\ten\tru" or not text.endswith("\n") or "\r" in text:
            raise AssertionError("actual canonical TSV header/LF")
        cls.rows = {}
        for line in lines:
            if not line:
                continue
            key, en, ru = line.split("\t")
            if key in cls.rows:
                raise AssertionError(f"duplicate canonical TSV key {key}")
            cls.rows[key] = {"en": en, "ru": ru}

    def probe(self, mode):
        done = subprocess.run(["node", str(PROBE), mode, str(ROOT)], capture_output=True, text=True,
                              env=os.environ.copy(), timeout=45)
        if "Cannot find module 'acorn'" in done.stderr or "Cannot find module 'jsdom'" in done.stderr:
            self.fail("judge environment missing: NODE_PATH=%r must hold acorn 8.15.0 and jsdom 26.1.0 "
                      "(see the module docstring)" % os.environ.get("NODE_PATH"))
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        result = json.loads(done.stdout)
        self.assertEqual(result["errors"], [])
        return result

    def test_actual_522_values_paths_parameters_and_four_block_identity(self):
        # 519 captions of the frozen witness + 3 top-level captions of the accepted common slice ADR-0083 (145)
        # (change 0083-common-source145, d5e9ab4b4); the probe pins both rosters and the code outside the four blocks.
        self.assertEqual(len(self.rows), 522)
        result = self.probe("audit")
        self.assertEqual(result["counts"], {"tsv": 522, "languages": 2, "witnesses": 3, "approvedBlocks": 4})

    def test_each_owned_mutant_reaches_its_own_rule(self):
        result = self.probe("mutants")
        expected = {"missing WORDS key", "missing TSV key", "duplicate TSV key", "changed substitution",
                    "unaccepted TSV key", "nested accepted key",
                    "trimmed loginAt", "wrong effective glass", "split dotted event key", "browser fallback",
                    "wrong milliseconds", "extra timezone", "extra public API", "Cyrillic comment",
                    "duplicate WORDS property", "CSS token change", "HTML inline code change", "HTML markup change",
                    "frozen witness js", "frozen witness css", "frozen witness html"}
        self.assertEqual({m["name"] for m in result["mutants"]}, expected)
        for mutant in result["mutants"]:
            with self.subTest(mutant=mutant["name"]):
                self.assertTrue(any(mutant["rule"] in error for error in mutant["errors"]), mutant)

    def test_dom_mutants_really_change_observed_language_or_date_arguments(self):
        result = self.probe("dom-mutants")
        self.assertEqual(result["rejected"], ["browser fallback", "milliseconds", "timezone", "mutable opts"])

    def test_owned_dom_browser_mismatch_mixed_mounts_and_formatters(self):
        result = self.probe("dom")
        current, witness = result["current"], result["witness"]
        self.assertEqual(current["surface"], witness["surface"])
        self.assertEqual(current["surface"]["version"], 1)
        self.assertEqual(current["requests"], witness["requests"] * 6)
        self.assertTrue(current["requests"])
        self.assertTrue(all(r["method"] == "GET" for r in current["requests"]))
        self.assertFalse(any("localization" in r["url"] or ".tsv" in r["url"] or "lang=" in r["url"]
                             for r in current["requests"]))
        self.assertEqual(len(current["mounts"]), 12)  # reverse and forward interleaving of six live closures
        seen, formatter_calls = set(), 0
        options = {"day": "2-digit", "month": "2-digit", "hour": "2-digit", "minute": "2-digit", "hour12": False}

        def flattened(value, prefix=()):
            out = {}
            for key, item in value.items():
                at = (*prefix, key)
                if isinstance(item, str):
                    out[".".join(at)] = item
                else:
                    out.update(flattened(item, at))
            return out

        for mount in current["mounts"]:
            lang = "ru" if mount["lang"] == "ru" else "en"
            seen.add(str(mount["lang"]))
            with self.subTest(lang=mount["lang"]):
                self.assertEqual(flattened(mount["words"]), {k: row[lang] for k, row in self.rows.items()})
                self.assertEqual(mount["login"], self.rows["login"][lang])
                self.assertEqual(mount["api"], witness["mounts"][0]["api"])
                self.assertEqual(len(mount["cases"]), 20)
                for case in mount["cases"]:
                    formatter_calls += 1
                    if not case["truthy"]:
                        self.assertEqual(case["value"], "—")
                        self.assertEqual(case["dates"], [])
                        continue
                    self.assertEqual(case["value"], "OWNED_DATE")
                    self.assertEqual(len(case["dates"]), 1)
                    date = case["dates"][0]
                    self.assertEqual(date["constructor"], [case["milliseconds"]])
                    expected = ["ru-RU" if lang == "ru" else "en-US"]
                    if case["name"] == "fmtDay":
                        expected.append(options)
                    self.assertEqual(date["args"], expected)  # exact arity/options, including absence of timeZone
        self.assertEqual(seen, {"<omitted>", "en", "ru", "RU", "ru-RU", "None"})
        self.assertEqual(formatter_calls, 240)


if __name__ == "__main__":
    unittest.main()
