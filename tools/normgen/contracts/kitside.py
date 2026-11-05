"""The items a lesson performs for an adapter of the package contracts (build_kit --part contracts and the judge
test_contracts.py — one function). A table whose rows a side performs only in part (secret-in: the display — 06, 04;
the refusal — 06, 03, 08; the README «Who performs it») has its adapter carry the constant `"@side"`; it is replaced by
the items the lesson's own vectors compare (out/pNN/go/vectortests, the output of gen_vectors): "display" if the rows
expect masked, "refusal" if they expect fault."""
import re
from pathlib import Path

SIDE = '"@side"'


def items(vectortests: Path) -> str:
    found = []
    text = "".join(p.read_text(encoding="utf-8") for p in sorted(vectortests.glob("secretin_*_test.go")))
    if re.search(r'\\"masked\\":', text):
        found.append("display")
    if re.search(r'\\"fault\\":', text):
        found.append("refusal")
    return ",".join(found)


def fill(adapter: str, vectortests: Path) -> str:
    return adapter.replace(SIDE, '"' + items(vectortests) + '"') if SIDE in adapter else adapter
