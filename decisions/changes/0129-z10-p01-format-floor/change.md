# Change 0129-z10-p01-format-floor — metadata revision2, source unchanged

change: 0129-z10-p01-format-floor rev 2 · lesson P/01 · delta_base 725653954 · author spec103 · state review

Original source base `d034aa09e6dcad450cd4e0942457f430dda43ece`; unchanged source component `2f413bd265f73343a5fe2395e3c4e647e0e7eeab`. [ADR-0122](../../0122-правки-норм-дельтами-added-modified-removed.md) heading-aware units and boundary disposition0086 control this metadata-only child. SOURCE-A f935/de4b and all nine final source SHA remain unchanged. Metadata activation472584f1 authorizes exactly six kit files plus the two own auxiliary rows; no source or case edit.

## Complete eighteen-artifact source kit

| Artifact | Operation from original source base | Base blob | Result blob |
|---|---|---|---|
| `Platform/01-store/spec/01.3-store.norms.md` | modify | b47a2f025ef46fd272e26100ea2a31099e27338e | 68cf68ab06d00980ad68a7cc6f8187245c8c36c1 |
| `Platform/01-store/ru/spec/01.3-store.norms.md` | modify | 9d0bb6e6872a382933f242e6365c840d1f60cdad | 39791bd39f38b512db8ee472b0395453d6671ace |
| `Platform/01-store/acceptance/3/README.md` | modify | 4605aecb805445f952c80ba156793e42332caa9f | 74dd8399f3b9aeec59f3ef58e70839cbd4f1e8f9 |
| `Platform/01-store/ru/acceptance/3/README.md` | modify | 850299e7653a8877484eab6cb247ffa17d6056cd | 965429267004457cee82140ab6d66b371b11136a |
| `Platform/01-store/data/epoch_floor.schema.json` | modify | c6e351ba474a436ad111af832c23340201a9ad35 | cf1e40b29590da93bc15cd16cededf202848b4d2 |
| `Platform/common/vectors/family-read/01.tsv` | modify | ceacd8755fd36985d2c0730a8508859e937fe39b | fb868b012d74c8e2b31990fb62b8ee6183b03f13 |
| `Platform/01-store/acceptance/3/scenarios.tsv` | modify | 019a5e23838480e2ab8a4c1a2a77b2da49ca278c | 3a19c03a614fc8e6517bc69697ddd3ec7981f955 |
| `Platform/01-store/acceptance/3/inputs/bad-floor-zero.jsonl` | add | - | 2e041329c14d570316c06dbd3004a9108e98266b |
| `Platform/01-store/acceptance/3/inputs/bad-floor-above-current.jsonl` | add | - | dee71e42df3bdd63b41dfb03836dd40476564ca8 |
| `decisions/changes/registry.tsv` | append/own rev2 row update | 81f139a2f453e95ba6c109ab68fa7fc6617601db | 79ddad2c97c6c8af23548830e42af15a6f19eb77 |
| `decisions/journal/platform/01-store/corrections-3.tsv` | append | 7882c113735ba38e2bee7bc156c7c47bb628acc1 | ebb5fd9c41d711149693692f0b51be13dd5fbf4e |
| `decisions/adr-norms.tsv` | append/own rev2 row update | fd962e436d802de6b56bd94492f00fbb3166ee8b | 2c0d3338d87dd85535eff2c4ae59b538240382d1 |
| `decisions/changes/0129-z10-p01-format-floor/delta.md` | add | - | f038e68027519e49fda27d12ba7f4526d76dedc0 |
| `decisions/changes/0129-z10-p01-format-floor/change.md` | add | - | external final metadata FREEZE (self hash) |
| `decisions/changes/0129-z10-p01-format-floor/source-map.json` | add | - | 7487161cc0dcbd3b1d5ae061102be8c77f693b51 |
| `decisions/changes/0129-z10-p01-format-floor/corpus-map.json` | add | - | 2ac8abede099d0dad8dafb3fe088ae3c8cad436c |
| `decisions/changes/0129-z10-p01-format-floor/preservation.json` | add | - | 8f8b1dc4eee3e04b761498767ac50d18a1a83848 |
| `decisions/changes/0129-z10-p01-format-floor/history.md` | add | - | b90c891e7ceb20c3dadebe21267fb5d40d8e1987 |

The external final metadata FREEZE pins all18 source-kit identities and all8 child identities, including this self hash. Raw source9 before/after maps are preserved; no recursive hash is fabricated.

## Actual req operations

Only MODIFIED R006 and R029. Old expected hashes retain the established LF/trailing-space/one-final-LF convention. Full replacement units end at the next req anchor or a same/older Markdown heading. R011 and R030 are strictly unchanged; no REMOVED/new/renumbered req operation exists.

## Derived source blocks outside req operations

| Path | Subject | Base/result blob | Old UTF8 span / new UTF8 span | Relationship |
|---|---|---|---|---|
| `Platform/01-store/spec/01.3-store.norms.md` | operator Implementation decides item5 | b47a2f025ef46fd272e26100ea2a31099e27338e / 68cf68ab06d00980ad68a7cc6f8187245c8c36c1 | 56469..56824 / 56722..57089 | derived from actual R006/R029; exact texts/hashes in source-map.json |
| `Platform/01-store/spec/01.3-store.norms.md` | floor field table | b47a2f025ef46fd272e26100ea2a31099e27338e / 68cf68ab06d00980ad68a7cc6f8187245c8c36c1 | 30564..30735 / 30725..30896 | derived from actual R006/R029; exact texts/hashes in source-map.json |
| `Platform/01-store/ru/spec/01.3-store.norms.md` | operator Implementation decides item5 | 9d0bb6e6872a382933f242e6365c840d1f60cdad / 39791bd39f38b512db8ee472b0395453d6671ace | 74634..75108 / 75279..75771 | derived from actual R006/R029; exact texts/hashes in source-map.json |
| `Platform/01-store/ru/spec/01.3-store.norms.md` | floor field table | 9d0bb6e6872a382933f242e6365c840d1f60cdad / 39791bd39f38b512db8ee472b0395453d6671ace | 39950..40145 / 40377..40572 | derived from actual R006/R029; exact texts/hashes in source-map.json |

## Related-change matrix

| Subject | Status | Boundary |
|---|---|---|
| Req delta membership | changed | only actual R006/R029; unchanged R011/R030 removed from operation list |
| Derived floor table/operator summaries | separately manifested | path, original/result blob, raw spans and exact text; no invented req IDs |
| Source9 / family8 / copy2 / scenario4 | agreed unchanged | exact source2f SHA; payloads/expectations/prefixes unchanged |
| Registry and ADR ledger | changed | only own A revision1→2 and req-ID cell; state review |
| Journal3 and all other source/tree entries | agreed unchanged | no append or source rewrite in this child |
| Source B | not applicable | separate branch parent854; not folded or repinned |
| Tools/apply/accepted/applied/models/runtime/GATE | not applicable | no implementation or execution assigned |

## Revision history

| Rev | Source / metadata | Evidence | Status |
|---|---|---|---|
| 1 | source2f | immutable FREEZE21a5; erroneous4 marker partitions preserved at prior blobs | historical, not strict req-boundary compliance |
| 2 | source2f unchanged, exact8 metadata child | final author commit and FREEZE external | review only; static metadata/link/hash controls |
