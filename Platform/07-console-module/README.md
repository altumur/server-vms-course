# Console module — lesson P/07

This English text is the source; the Russian translation `ru/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

A micromodule: a JS library. What it norms and from where — the [module design note](../module-design.md), the table «Уроки».

The layout of the catalogue (after the move, stage B). The lesson has one chapter; it has no HTTP contract, life cycle, families,
vectors or acceptance catalogue of its own: the doors the module calls are the contract of lesson P/06, the publication of the module is chapter
6.5 and its acceptance (sc. 01):

```text
07-console-module.md                     lecture
spec/07-console-module.norms.md          norms (one chapter; Н2 — the library contract)
spec/07-console-module.README.md         implementation instructions
```
