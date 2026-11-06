# tools/normgen: code generators from forms (ADR-0120 item 2(a), ADR-0125, ADR-0126)

Generators build a lesson's mechanical parts from machine-readable forms without a model. Each has an external judge
(ADR-0125 addendum (1), item 1). Generators use Python stdlib; output uses Go 1.22 and stdlib.

`code_origin.py` counts final-code origins from implementation and kit SHAs:
[method, inputs and ADR-0127 probe report](provenance/README.md). Count `generated`, handwritten kit code and model
code separately for code/tests, using final bytes and manifest `origin`.

| No. | Generator | Form | Output (`out/p01-1/go/`) | Kit part | Judge |
|---|---|---|---|---|---|
| 1 | `gen_checks.py` | `forms/write-checks.tsv` | `checks/` (+ `python/checks.py`) | `writecheck` with `kit/go` | `check_tables` oracle through `test_gen_checks.py` |
| 2 | `gen_door.py` | `spec/01-store.api.openapi.yaml` | `door/` | `door` | P/01.1 runner on `kit/build_stub.py`, then `door_judge.py` |
| 2 (P/06, P/08-P/10, 3a) | `gen_door_lesson.py --lesson 06-console` / `08-domain` / `09-agent` / `10-domain-console`; `gen_door.py` delegates after P/01 | Lesson OpenAPI, relative external refs from 05/06/08/shared contracts, yamlsub mapping anchors/aliases; a literal server has no sub prefix. Ignore description/x-mounting prose | `apidoor/routes.go`: Op per path/method, Ops metadata (method, path, Prefixed from `{origin}/{sub}`, parameters, response statuses/media/headers, request media), router templates and minLength/maxLength/pattern/enum/const/not checks. Copied `doorrt2/go/routes.go` implements `Route(method, path, Catalog)`: literal > loaded catalog class (sub/rows/table/pass) > free parameter; 405 only when all path operations declare it | `door` (P/06) | `test_gen_door_lesson.py`, one subclass per lesson: independent OpenAPI route model, every operation and short/prefixed variant (167/167), 404/405/percent/schema-boundary negatives and prefix/all405/schema/rank mutants |
| 2 (P/06, 3b) | `gen_door_lesson.py --lesson 06-console` | Request/response body schemas, with external 05/08/shared-contract refs | `apidoor/bodies.go`: combined `$defs` (301 components, external `NN.<name>`, inline `<Op>.<req\|resp>.<status>.<media>`), request/response schema tables by media/status; copied `doorrt2/go/schema.go`: Draft 2020-12 `Validate`, including unevaluatedProperties, plus StrictJSON/DecodeRequest/CheckResponse/EncodeResponse | `door` | `test_gen_door_bodies.py`: jsonschema oracle on judge values (5797) and synthetic schemas, original-versus-combined schemas through referencing, API and checker mutants |
| 2 (P/05) | `gen_door_lesson.py --lesson 05-resource`, x-route-priority mode (P/05-R057) | OpenAPI priority, segment/remainder capture, percent-segment decode, per-method x-path-error, and door-roles.tsv | routes.go priority/capture/decoding/errors/roles; copied `doorrt2/go/routes_priority.go`: raw literal matching, method filtering before priority, bodyless 405/404 and parameter errors without fallback; Admitted for mtls roles. Shared CheckParam/CheckParams support query/header schemas/defaults; x-line-schema supports NDJSON | `door` | `test_gen_door_priority.py`: independent R057 model, resource-route s30-s37, operations, %2F/%FF/empty/double-slash corruptions, random paths, roles and runtime mutants. `test_gen_door_bodies.py` also checks parameters against jsonschema |
| contracts (all lessons) | Handwritten `contracts/go`, once per vocabulary, inventory item 1 | `Platform/common/contracts/*.md` | internal/contracts: instance GivenInstance/ResolveBox; slot-name SlotOrder/NextName/RoleOf; labels ValidLabel/LabelSetWrite/LabelTextRead/EnvLabels; journal EncodeComponent/FileName/ReadHashedName/WriteHashedName/BucketName/AppendLine/ReadBucket. contracts/adapters supply implementation-owned vector adapters in place of scaffolds | `contracts` | `test_contracts.py`: vectors for every consumer through contracts adapters (334 tests), and kit-part build |
| 3 | `gen_flags.py` | `forms/daemon-flags.tsv` | `flags/` | `flags` | `flag_judge.py` daemon startup probes |
| 3 (P/02) | `gen_flags.py --lesson 02-installer` | operator-commands.tsv command/process/argv prefix/positional string-array schema; daemon-flags.tsv string/number/file/bool options with CEL f/cmd | flags ParseArgv/Lookup/Parse/Commands; refusals have no exit code because commands select it from refusals.tsv. Option spelling and decimal number syntax are kit conventions | `flags` | Independent-form/CEL `cmdflag_judge.py`; mutants in test_gen_flags_cmd.py |
| 4 | `gen_refusals.py` | `forms/refusals.tsv` | `refusals/` | `refusals` | `refusal_judge.py`, acceptance and door.Refuse |
| 4 (P/02) | `gen_refusals.py --lesson 02-installer` | 15-column refusals.tsv: call/cli/start/process/peer, exit N/!0, peer HTTP status or '-', word/log; cause/outcome/diagnostic/caller prose is not emitted | Spec Exit/AnyNonZero/Status/Word/Log/Words and ExitCode; kit convention maps !0 to 1 | `refusals` | refusal_judge compares the table and every seam RUN exit; test_gen_refusals_plain.py mutants |
| 3 (P/03-P/05) | `gen_flags.py --lesson 03-worker` / `04-controller` / `05-resource` | Process inputs: environment `$NAME`, positional `<arg>`, string/dir/file/number, CEL f/cmd | Parse(cmd,args,getenv), Inputs/Commands, refusal without exit code; adapters own default_text and contract checks using Given | `flags` | test_gen_flags_inputs.py independent form/CEL model, 4000 probes per lesson and mutants |
| 4 (P/03-P/05) | `gen_refusals.py --lesson 03-worker` / `04-controller` / `05-resource` | Single-chapter labels such as 4; peer fields/headers from imported doors; exact word cell (spec103, 2026-11-05). P/05 adds local http and response_schema from OpenAPI components | Spec plus Fields/Headers/Named (quoted outcome-token index, not any-of)/WordCell (verbatim cell) | `refusals` | refusal_judge: P/03 56/56, P/04 18/18 with independent reads; test_gen_refusals_lessons.py mutants/invalid forms |
| stagetests (P/03-P/05) | `gen_cmdtests.py --lesson 03-worker` / `04-controller` / `05-resource` | stages.tsv tests gates, acceptance seams with CALL port JSON only, forms/README CALL port table | CALL engine using P/02 match/decode; port panic/error fails. Closed lessonadapter.go plus one implementation-owned file per port (P/03 15, P/04 11) | `stagetests` | test_gen_cmdtests_ports.py: scaffolds fail without panic, seam-derived fixtures pass, mutants fail |
| vectors (P/03-P/06, P/08-P/10) | `gen_vectors.py` with the corresponding lesson | consumers.tsv plus temporary wire_draft.py projection until wire.tsv. Sources: package READMEs and runner comparison; reports `/home/pilot/wire-p03p04-draft.md`, `/home/pilot/wire-p06-draft.md`, `/home/pilot/wire-p0810-draft.md`. P/06 whole-table fault, pool without:<field>, mapped secret, whole-secret no-leak at least 4 bytes; local creates-key/near-of/order/shrink-* | Same vectoradapter/vectortests/vectorcmd/cmd-vectors layout as P/02; one implementation-owned file per package. Selected-out rows remain excluded with reasons. values-by-type uses write/read frames. compare_test.go checkBy implements subset/fields/setarrays/events/row/secret/turn/vbt-write | `vectors` | test_gen_vectors_lessons.py: exact consumer roster, default failures without panic, passing rule-derived fixture adapter; 10 mutants fail their own tests, fields outside fields remain accepted |
| 5 | `gen_families.py` | catalog.tsv, 01-store/data family schema/layers/outcomes; only path/reader/priority/unit from outcomes; README key placeholders | families.go and handwritten famrt/go/runtime.go V7 traversal | `families` | family_judge on family-read/01.tsv and independent --v7 cases; check_spec compares vectors with V7 |
| 5 (P/02+) | `gen_families.py --lesson 02-installer` | Lesson-owned schemas/catalog/layers/outcomes, data-schema mode for every lesson after P/01 | families.go stores schema text,key template,outcomes; copied famrt2 runtime executes closed Draft 2020-12/V7 keywords with dialect paths: x-encoding json/jcs,x-codec,x-time,x-integer,x-whole,x-max-bytes,x-max-names,$defs.writer | `families` | family_judge on 02.tsv and --v7 nested mutants; test_gen_families_doc.py synthetic-family V7 comparison/runtime mutants |
| 6 | `gen_tests.py` + common_vectors.py | JCS,rights-evaluator,stages; pre-consumers COMPOSITION for common crl/revoked/log-mask cases.tsv,store-client,family-read01.tsv | TestCommon<Package>_Line<N>, unified vectorcmd, kit-executed family-read, implementation-owned per-function canonical/rights/crl/revoked/logmask/storeclient scaffolds | `vectors`, requiring families for family-read | vector_judge.py and P/NN/vectors-<package> runner targets |
| 6 (P/02) | `gen_vectors.py --lesson 02-installer` + wire_vectors.py | wire.tsv via wire.py: inputs,fixtures,groups,markers,native,compare/assert; stages and consumers roster. Use check-env Python for CEL/jsonschema | Existing Go signatures; one test per form Run (1517), including both platform-lists surfaces; wirecheck validates full native.schema before subset/assert using body-schema runtime without HTTP; vectorcmd/cmd-vectors. Journal modes are layout/excluded | `vectors`, requiring families | test_gen_vectors.py roster/scaffolds/fixtures/mutants; test_wire_vectors.py independent full schema/frame/compare/assert,form mutations and missing bindings; test_wire.py and P/02 vectors runner targets |
| 2 + 3 | `gen_launch.py` | daemon flags and OpenAPI through flags/door | launch, editable temporary net/http frame with N2.1 anchors, and editable cmd/configstore entrypoint | `launch`, requiring door/flags/stagetests/admin | P/01.1 runner on unchanged launch.Empty with scaffold Open, then launch_judge.py for 01-absent |
| 3 + N1.3 | `gen_admin.py` | commands column, N1.3 R006 admin_ops/copy/import/floor/box/repeat,R018,N3 recover,refusals,and common @spoil row directive | Closed admin.go Env/Run/NotInStage(exit 1), one implementation-owned file per subcommand and own.go spoil-row. launch uses admin.Run for nil App.Admin and checks Own before flags | `admin`, requiring flags and required by launch | admin_judge: unimplemented command exit 1, invalid/foreign flags 2, spoil-row 1; test_gen_admin.py anchors/mutants/seed |
| rollout-poll (P/02) | `gen_rollout.py --lesson 02-installer` | rollout-poll.traces.tsv; machine YAML is normative, not executed by the generator | TestRolloutPoll_Trace_<trace>, subtests per observable state and same-step did=refuse, passing event prefixes to lessonadapter.RolloutPoll; internal alive/need/target assertions excluded | `rollout-poll`, requiring stagetests | test_gen_rollout.py scaffold failures, passing trace-response fixture, failing mutants |
| machines (P/03,P/04) | `gen_machine.py` for machine-column forms | n/state/condition/action/next/norm; states/Initial/#var/#const/#action; uppercase vars are settings. Generator1 CEL parser with typed lowering. First matching row, otherwise wait; '-' is YOURS | Closed machine.go State/In/Step transition selection,Actions/Apply; form tests cover input-value/outcome pairs and constant/setting boundaries; inventory. Editable impl actions.go and per-action/procedure files, including first_write_to_cleanup.go P/03.2-R024 and judge_to_release.go/consider_to_writing.go P/04-R041 | slot-capture/slot-fate/slot-release | test_gen_machine independently reads forms and evaluates random/boundary typed arguments/overflow with CEL; oracle-distinguishable condition/next/literal/order mutants fail original tests; invalid grammar refuses |
| stagetests (P/02) | `gen_cmdtests.py --lesson 02-installer` | stages tests/verdicts gates, seams RUN/CALL command/load/load-catalogue/rollout-poll,@file/@read/@parallel; verdicts/cases/classes. puts explicitly needs P/01 store and runner | Non-HTTP engine, Test<Stage>_<Scenario>/Verdicts,base64 cases in verdicts.jsonl,inventory; closed lessonadapter types and implementation-owned command/load/catalogue/poll | `stagetests` | test_gen_cmdtests.py scaffold failures without panic, passing fixture adapter and failing adapter/seam mutants |
| 2 + N3 | `gen_core.py` | Generated Handler signatures and P/01.1 N3/N2.1 req anchors. Context identity: P/01.2 Roles/check,P/01.1 R050/R066,P/01.3-07 order,header and 403 catalog rows. Chapter1.2/1.3 stubs bind N2 clauses,P/01.3-R016 doors and named refusals | out/p01-1/core/coreadapter core/open and one editable file per Handler method,installed once; do not add stubs for names already declared | `core`, requiring door/stagetests | test_gen_core.py build/scaffold failures without panic plus runner. Get's empty-store default keeps launch closed |

Handwritten once per vocabulary: CEL runtime/ and #fn prims/ in Go/Python, flags/go/flagtypes.go, doorrt/, and
kit/go jsonstrict/writecheck.

## Kit B

`python3 kit/build_kit.py <dst> --module <import-path-to-dst/01-store> [--part door] [--part flags] [--part refusals]
[--part tests]` installs parts under `<dst>/01-store/internal/`, KIT.md and kit.manifest.json. The manifest records parts,
line counts by origin/component, per-part form/generator/runtime/judge SHA256 provenance, an output file-set digest,
and optional `judged` links through `--judged part=link`. Every copied output, including generators 1/2, must match a
fresh generation rather than merely its header. Stale forms,producers or runtimes refuse build until regenerated.

KIT.md supplies connection signatures, verbatim examples from kit/examples/<part>.go (compiled by test_gen_launch.py)
and actual exported names from source. The task receives this guide instead of generated implementation bodies.

## Tests and judges run on Linux (CT 103)

Run normgen tests/judges as pilot on CT 103. Go 1.22 on macOS links net/loopback binaries lacking LC_UUID, which fail in dyld.

- CEL Python: `/opt/check-env/lesson-spec/bin/python` with cel_expr_python for check/flag oracles.
- Suites: test_gen_checks,tests,door,flags,refusals,stagetests,launch,core,families,admin; test_gate,test_judges,test_lesson;
  command/input flags,plain/lesson refusals,cmdtests,rollout,data-schema families,machines,CALL ports,lesson vectors,
  lesson door routes/bodies/priority,contracts; kit/test_kit.py,test_kit_p02.py,test_kit_lessons.py,test_export.py;
  then skills/lesson-spec/scripts/check_spec.py and test_gen_vectors.py.
- lesson.py selects --lesson NN-name or NORMGEN_LESSON,default01-store,for every generator,judge and build_kit.
  Derive paths,out/modules,kit directory/default --module and chapter norms from lessons.tsv. P/01-only norm/vector/frame
  declarations in gen_core/admin/launch/tests reject other lessons by name; explicit P/01 preserves pre-generalization bytes.
- Attempt kits use only `build_kit.py <kit> --module ... --part ... --export <export-SHA>`. Inputs come from cammeta-specs
  Platform at --specs; code comes from clean course HEAD. Dirty tools/normgen refuses. Regenerate in a temporary tree,
  leave the course unchanged,record commit/export in the manifest and automatically write SOURCE.txt.
- P/02: `build_kit.py <kit> --lesson 02-installer --part flags --part refusals --part stagetests --part rollout-poll
  --export <sha>`. No writecheck; gen_cmdtests supplies stagetests. Regeneration selects lesson parts and module
  p02installer/02-installer.
- P/03: use --lesson 03-worker with flags,refusals,stagetests,slot-capture,families,vectors. P/04 uses04-controller,
  slot-fate and slot-release. Their vector transport uses wire_draft.py until its full wire form.
- A machine from another lesson refuses without its form. Machine impl files remain editable under the adapter seed rule.
- --seed <previous-worktree> protects model code when a cycle copies a whole kit over a seed: emit editable files only
  if absent or still equal to the prior kit manifest SHA. Record seed kept/refreshed lists.
- gate.py parses stages.tsv gate lists using the same header grammar as check_forms.
- Non-execution fails every judge. Expected steps come from scenarios/projection,not reports. Missing results,empty/truncated
  reports and unfinished Go runs fail. flag_judge readiness means a live daemon listening on admin.sock under -sockets;
  groups without peers are unverified with a reason rather than passed.
- flag_judge.py --cmd <daemon> supports --stub for flags/stub value comparisons and --box for no-raft builds.
  Probes write only inside temporary directories.
- Door judging uses the CT103 queue (/srv/cammeta-checks,check.py submit --env go --with-git). Input contains RUN.py,
  runner,export pinned by --spec-version and a build_stub implementation Git repository. Judge out/report with door_judge.py.
- Launch judging: `launch_judge.py job <input> --spec-version <SHA>` -> queue `check.py submit ... -- python3.12 RUN.py`
  -> `launch_judge.py judge <out/report>`.

## Subsequent inventory items (3-5, checkpoint a17871069)

| Item | Existing at this checkpoint | Next input needed |
|---|---|---|
| 3: vector-backed bodies | P/02 loader covers manifest parsing/canonical; shared contracts belongs to Generators-2; other local lesson functions remain scaffolds | Separate workers-script/install-order slice after an algorithm form. Vectors are an external judge,not an implementation response table; no new semantics are inferred from prose |
| 4: constants/journal-kinds/steps | P/06 runtime-constants.tsv has25rows,read by gen_flags into flags/constants.go | Reuse name/value/unit/norm in later lessons with spec103-owned forms. Journal kinds/ordered steps lack a complete form; no generator is declared |
| 5: P/06,P/08-P/10 forms | P/06 flags/refusals/stages/seams/constants and corresponding generators/kits are in main | At this checkpoint P/08-P/10 await spec103 forms; P/06 row-checks/new machines await theirs. Full P/06 wire was NOT READY and partial bindings must not switch it |

P/02's ready wire switched separately from P/01,whose gen_tests retained its output. This inventory records input
readiness at its checkpoint. coord103 assigns subsequent items 3-5; shared contracts is outside that list.

## Package consumers and cross-lesson tables

vector_consumers.py reads consumers.tsv under common validation: full `(common|NN-name)/package`,lesson from lessons.tsv,
existing package/table. Duplicate (package,table,lesson) refuses even with a different norm; invalid foreign-lesson rows
also refuse before selection. Consumers are explicit rows union the package's owning lesson. Local tables therefore
remain without explicit rows; common has no implicit owner. common_vectors.composition preserves the five common adapter
APIs and projects this full roster; gen_tests/gen_vectors handle local and cross-lesson packages.

consumer_vectors.py declares only assigned cross-lesson Go APIs. At spec103 `7b96ff9f84e8090e11922131bc77799f0a0b54e1`,
these are JCS(02/03/06/08/09) and rid/request-digest/requests-body(03). Inputs,expectations,selection and comparisons come
from wire.tsv. P/02 JCS has a separate adapter from manifest canonical. Missing bindings/APIs never disappear silently.

test_consumer_packages.py extracts that exact pin to a temporary tree without changing Platform. Check current/new forms,
the exact nine added assignments,owner union,negatives,compile/execution across five lessons and mutants. Worker executes
only its requests-body projection; this does not close console layout/HTTP debt. rid/template supports CEL json and
ignore /detail; native.schema checks the full response before ignored fields are removed.

wire.parse(...,keys=...,surfaces=...) limits grammar to a selected slice; without selection it validates the whole form.
Other partial P/06 rows did not switch its prior wire_draft generation. Full at/map/stand arg_file.json grammar and
check_wire followed this reader slice. Pin7b96ff9f is not an export or a claim of full P/06 readiness.

## Full P/06 wire executor (form 4f0cff2e)

wire.py expands all90bindings without prose:at,map,arg_file.json,exact raw-json fragments,CEL json() in when,explicit
group_by,whole,ignore in expectations,and assertions without test. Direct marker.ignore refuses;marker.assert.ignore is
allowed. Layout and inactive surfaces stay excluded.

Shared wire_vectors API:declarations(root,lesson="02-installer",api=API_P02),build(root,g,decls=None,lesson=None),
render(root,g,decls,runs,excluded,known=(),scaffold=True). APIs contain only package/table/surface/fn/args;the form owns
inputs,selection,expectations,frames and checks. Require declarations only for active Runs:console does not need
stand:group-of because it uses vectors/raw. go_vectorcmd(...,full_wire=True) explicitly selects full rendering;vectors
args=input forwards one cell's raw bytes without JSON reconstruction. The form closes variants/cells/files. StandResult
distinguishes panic/non-execution from native exits;nonnegative codes retain stdout.

wirert/full/go/check.go validates full native/schema before ignore/compare/assert. Independent probes cover JSON decode,
ignore,nested pointers,whole/no-leak and JSON Lines comparison. Published P/02 retains wirert/go/check.go so broader
execution does not change old bytes for old inputs. A new form alone never enables another lesson's canonical mode.

test_wire_full.py tests constructs/mutants,compiles a temporary full P/06 module through the shared API and executes3184
fixture-response tests. This judges form execution/translation,not lesson implementation,and does not replace published
P/06 out. frames_of and judges understand _form/_runs;positive replies receive required native fields and separate
jsonschema validation. The nine-assignment delta uses frozen testdata/consumer-owners-8af61893a.json rather than mutable ROOT.
