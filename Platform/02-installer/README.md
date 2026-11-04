# Manifest and installer — lesson P/02

This English text is the source; the Russian [`README.md`](../README.md) is derived from it by translation and is not edited by hand (ADR-0121).

A micromodule: a command process, a centre, units. What it norms and from where — the [module design note](../../module-design.md), the table «Уроки».

The layout of the catalogue (filled by the move, stage B). The installer has no OpenAPI of its own — it has no HTTP doors;
`GET /manifest`, `ManifestView` and `ConsoleRefusal` moved with the move of lesson 2 temporarily to М10/9, and with the move of lesson 6 to [chapter 6.5](../../06-console/spec/06.5-console.norms.md) of the console
(review of stage A 2, П10):

```text
02-installer.md                     lecture
spec/02[.K]-installer.norms.md       norms (chapters — .K)
spec/02-installer.library.md         library contract (if any)
spec/02-installer.README.md          implementation instructions
lifecycle.md                    flags, environment, exit codes, units
data/<family>.schema.json       schemas of the families the lesson owns (JSON Schema 2020-12, ADR-0092; ADR-0088)
vectors/<algorithm>/            vectors of the algorithms the lesson introduces
acceptance/[K/]                 acceptance
```
