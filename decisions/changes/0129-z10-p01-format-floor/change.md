# Change 0129-z10-p01-format-floor — independent current FORMAT and floor source

change: 0129-z10-p01-format-floor rev 1 · lesson P/01 (delta_base 725653954) · author spec103 · state review

Base `d034aa09e6dcad450cd4e0942457f430dda43ece`. [ADR-0129](../../0129-минимум-догадок-генератор-не-больше-кода.md), addendum (23), and the [Z10 adjudication](../../inbox/2026-11-07-З10-P01-P02-разбор.md). This separate complete bundle contains only FORMAT and present floor. It does not transplant another frozen branch or include Time/canonical/layout/wrappers/B29.

Both source authorities are pinned in source-map.json: initial SOURCE-A `f935cd4ba9af3dc4be90527013a6760a89f5a692b3c4c3eeb9fc7c7602f87817` plus exact3 mirror-only adjustment `de4ba859f34da6e34063ecf69ea0de2c084196528cc978cc96abf4426ba3fb9a`. The original nine forecasts are preserved; only the two final norm SHA overrides apply. EN final `5f96fe44603861555d5c3e0b752559bcfecf536d37abe6d0099f40ffa9137686`; RU final `b63319c74d1518056030e8b26c583719864c9edc49cb3f588f97a6cc918f6395`.

## Complete manifest

| Artifact | Operation | Base blob | Result blob |
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
| `decisions/changes/registry.tsv` | append | 81f139a2f453e95ba6c109ab68fa7fc6617601db | 7ff8126f8557c59d79727c011940b4133a8bc4cf |
| `decisions/journal/platform/01-store/corrections-3.tsv` | append | 7882c113735ba38e2bee7bc156c7c47bb628acc1 | ebb5fd9c41d711149693692f0b51be13dd5fbf4e |
| `decisions/adr-norms.tsv` | append | fd962e436d802de6b56bd94492f00fbb3166ee8b | 1431361e8bbfb9a3a2b3d7aec8f7e4f9b8951528 |
| `decisions/changes/0129-z10-p01-format-floor/delta.md` | add | - | ff16d0919f506957aaa24f65e21d37c1c26c7399 |
| `decisions/changes/0129-z10-p01-format-floor/change.md` | add | - | self: external FREEZE |
| `decisions/changes/0129-z10-p01-format-floor/source-map.json` | add | - | 85f1582f20eba8fff5999ace1f10a9ed986c255c |
| `decisions/changes/0129-z10-p01-format-floor/corpus-map.json` | add | - | 49fbc80d9accb4741e727e0f8be90690f09be742 |
| `decisions/changes/0129-z10-p01-format-floor/preservation.json` | add | - | 527ed4d416003131f774275b354ced98f598e54a |
| `decisions/changes/0129-z10-p01-format-floor/history.md` | add | - | 0d8c3317656bd25985ae38f8770cdb7414786bb8 |

The change.md self hash and every metadata file hash are pinned by the external FREEZE of the final author commit. They are not omitted artifacts or fabricated circular hashes. Source maps pin every one of the nine source results; no changed path outside this eighteen-file manifest is permitted.

## Related-change matrix

| Related subject | Disposition | Evidence/boundary |
|---|---|---|
| Current internal format choice, start refusal, caller and operator action | changed | N1.3 format, N4 start_format, Implementation decides5 EN/RU; impl remains diagnostic only, first mark/log/no-write refusal/current portable copy preserved |
| Concrete floor form/printed family limits | changed | only floor.minimum=1 and floor.maximum=2^53-2^32; whole-number codec/ref remain; schema $defs and generation_at unchanged |
| Floor readers/issue/lease/recovery | agreed unchanged | existing unreadable/fenced/whole-input refusal; missing row virtual0 separate; current F1/generation formula and public operation unchanged, no multipleOf |
| Family corpus, copy fixture list, scenario steps | changed | append8, two current-format copy inputs, four extra steps in existing case12; exact raw prefixes and old negative causes preserved |
| HTTP/OpenAPI, write-checks, flags/constants/stages/outcomes/rights | agreed unchanged | current operation already owns this floor range; no new command, refusal, class, role or route |
| Time and private admission/portable exceptions | not applicable | generation_at and current common Time/number forms byte-exact; future Time source separate |
| Canonical/layout/four wrappers/B29 | not applicable | separate unactivated source slices; not charged as completed here |
| Source/VMS/tools/skills/module/other lessons/common15 | agreed unchanged | final non-allowlist tree proof is external; no CODE/Go/render/general generation or source transplant |
| Runner/model/implementation readiness | not applicable | source assertions are not importer/IO/SUT execution; models/independent checks/full main GATE remain with their owners |

## Checks and limits

New author controls only: exact authorized source forecasts and inverse slices; same JSON tree except the two concrete floor limits; eight integer-boundary neighbors before/after and the eight new family values after explicit integer decoding; immutable old TSV prefixes and unique existing case/step identities; two copy inputs differ only by the invalid floor string. JSONSchema bounds checks do not claim custom codec/family-library execution.

The initial actual norm mirror produced two new messages (line wrapping and explicit copy version spelling), retained in external MIRROR-CONTROLS.json. After exact3 authorized repair the actual changed norm pair has zero messages. The unchanged README pair was already zero and was not re-run. No full strict/render/generation/Go/HTTP/IO/SUT/model/GATE or old archived programme was run. Current branch is a source component for intake, not SOURCE_READY or accepted/applied status.

## Revision history

| Revision | Checked source | Independent reports/model | Change |
|---|---|---|---|
| 1 | final author SHA in external FREEZE | none assigned or borrowed | complete independent FORMAT+floor bundle; initial exact forecasts plus separately approved mirror-only exact3 |
