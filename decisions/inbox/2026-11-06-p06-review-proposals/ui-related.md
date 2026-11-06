# UI/localization related proposal only

Proposed source: Platform/06-console/data/localization.tsv, whole header `key<TAB>en<TAB>ru`, ASCII unique identifier keys. English is the default platform UI; Russian only when explicitly selected. The table is the only source-language Cyrillic exception. Subject captions continue from their manifest; protocol/API/log/error/state data and enum values never switch with UI language.

Concrete initial rows using already published W key names (a sample, not a completed dictionary):

```text
key       en       ru
unit      unit     единица
units     units    единицы
noRows    No rows  Нет строк
save      Save     Сохранить
cancel    Cancel   Отмена
```

The full key roster must be frozen from the platform captions actually required by P06/P07, including plural/count forms and placeholders. For each key both locales must preserve the same substitution parameters. Do not claim the five sample rows cover the entire published module. Do not make this a runtime fallback/alias dictionary for protocol words. en_mirror already recognizes exactly this path/header and exempts only ru cells; no scanner expansion or new exception is requested.

Related root text, separately assigned: CONSOLE-MODULE.md and ru/CONSOLE-MODULE.md. Proposed passages: §3 opts.lang says absent means en (en/ru supported); §6 default unit/noRows captions name their table entries; §10a's holder-page example uses the English default and offers explicit Russian choice instead of browser-language fallback; §12 says the table owns platform captions. This is the already accepted ADR0121(6) language rule, not a new HTTP feature. P06.5's display defaults and opts text reference the table. Existing public version/features/call API do not change.

Frozen Source/w2cplatform/console.js/css/html are NOT changed. Current console.js chooses browser language when opts.lang is absent; the new norm/table does not implement a different behavior in those bytes. Record that as an owner-of-published-bytes/P07 acceptance debt when that scope is assigned, not as a completed localization run. No P07 rewrite, tests against changed bytes, new shell route, compatibility alias or runtime localization claim.

P06's13 raw static/binary asset witnesses (including app.js85 and bundle.js300045) remain exact byte payloads. P09 two ops cells and reserved P10 forwarding/gate-and-pass source+mirror paths remain untouched. No other rootdoc is requested by this proposal.
