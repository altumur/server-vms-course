# Console module — lesson P/07

This English text is the source; the Russian translation `ru/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

A micromodule: a JS library. What it norms and from where — the module design note `Platform/module-design.md` (for people, not in the export), the table «Уроки».

The layout of the catalogue (ADR-0124: the English source on the canonical path, the Russian text for people in `ru/`). The lesson has one chapter; it has no HTTP contract, life cycle, families,
vectors or acceptance catalogue of its own: the doors the module calls are the contract of lesson P/06, the publication of the module is chapter
6.5 and its acceptance (sc. 01):

```text
README.md                                this file
spec/07-console-module.norms.md          norms (one chapter; N2 — the library contract)
spec/07-console-module.README.md         implementation instructions
ru/                                      for people, not in the export — the lecture ru/07-console-module.md, translations of the English text by the same path
```
