# Acceptance profiles and assembly

This contract describes the generic acceptance interface for Platform implementations. A lesson's acceptance README and the [common stand](README.md) assign the commands, inputs and outcomes of that lesson. A profile declares how the implementation exposes those interfaces. It does not change their behavior or replace the lesson's acceptance data.

This English text is the source; the Russian text in `../ru/acceptance/PROFILE.md` is a derived translation for people.

The profile is `acceptance.yaml`, with integer `format: 2`. The composition is `assembly.yaml`, with integer `format: 1`. The vector envelope has its own integer `format: 1`. These are different documents and independent format versions.

## Files and scalar syntax

A profile belongs to one module and lives in that module's implementation directory. The assembly maps module identities to profile files. The implementation repository has a root `SPEC_VERSION`; a profile cannot select a different specification from the external pin or that repository pin.

Both YAML documents contain block mappings with two spaces per nesting level, scalar strings or integers, and explicit empty mappings written `{}`. They have no sequences, flow mappings other than `{}`, anchors, aliases, tags, multiline scalars or quoted mapping keys. Duplicate keys, unknown fields and incorrect field types are format errors before builds or processes start. Empty implicit mapping blocks are not accepted: write `{}`.

Mapping keys contain one or more ASCII letters, digits, `_`, `.` or `-`. Keys of `vectors` additionally use the package namespace described below. Comments occupy a line or follow a scalar after whitespace. A command occupies one physical line. Single and double quotes delimit string values and do not belong to the resulting command; doubled single quotes and the supported YAML double-quote escapes represent characters in the value. A command or other nonempty text field cannot be blank or contain NUL, CR or LF after decoding.

The files are UTF-8. The reader accepts an initial UTF-8 BOM and LF, CRLF or CR line endings. NEL, Unicode line/paragraph separators and nonbreaking spaces are content, not indentation or line delimiters. Raw characters obey YAML's printable-character range; a character written as a permitted quoted escape is a different raw input. Ordinary unquoted nulls, booleans, nonfinite values and floating-point scalars are not converted into strings. Quote their textual spelling when a string is intended. Decimal integers and the supported `0x`/`0o` integer spellings remain integer scalars; quoted numbers remain strings. A quoted string that is not valid for the destination field is still refused there.

Inline-comment separation uses ASCII space or TAB. Indentation itself uses spaces in pairs; a TAB in indentation is refused. Single-quoted strings represent a quote by `''`. Double-quoted strings support the YAML escape letters `0 a b t n v f r e`, escaped space, quote, slash and backslash, and `N _ L P`, plus `x` with 2 hexadecimal digits, `u` with 4 and `U` with 8. Hex escapes must name a Unicode scalar, not a surrogate or a value above U+10FFFF. Destination text fields still reject decoded NUL, CR or LF. These Source documents use LF; this does not impose a new LF-only restriction on profile input.

## Profile fields

The top-level field set is closed:

| Field | Required | Type and meaning |
| --- | --- | --- |
| `format` | yes | Integer `2`. |
| `implementation` | yes | Nonempty single-line string identifying the implementation; it is neither a command nor a language selector. |
| `module` | yes | Canonical module identity. |
| `spec_version` | yes | String of exactly 40 hexadecimal digits naming the specification export commit. |
| `build` | yes | Nonempty single-line shell command for this module's own build or packaging. |
| `unit` | no | Nonempty single-line shell command for this module's own regressions. |
| `stand` | yes | Mapping of owned command or address names to nonempty single-line strings; `{}` is allowed. |
| `keys` | yes | Mapping of the profile parameters below; `{}` is allowed. |
| `adapters` | no | Mapping of the owned executable adapters below; `{}` is allowed. |
| `vectors` | no | Mapping of package names to owned command templates containing `{input}`; `{}` is allowed. |
| `artifacts` | yes | Nonempty mapping of labels to relative public build-result paths. |

The Platform module identities are `01-store`, `02-installer`, `03-worker`, `04-controller`, `05-resource`, `06-console`, `07-console-module`, `08-domain`, `09-agent` and `10-domain-console`. Their identity is independent of the implementation directory's name. The library profile `07-console-module` has `stand: {}`; its build and public artifacts remain required. The relay is a mode of the agent of `09-agent`, not another Platform profile.

This document's ownership and substitution tables below cover Platform. Existing VMS profile namespaces and their VMS-specific parameters are outside that table's review; their admission by the current reader is not removed or redefined here.

`spec_version` matches the external full specification commit. The repository's root `SPEC_VERSION` resolves to that same commit. A short repository pin has 7–40 hexadecimal digits and requires the pinned specification Git repository to resolve it unambiguously. The full profile pin is not shortened. When the profile is inside a Git checkout, the pin belongs to that checkout's root, including when the checkout is a worktree; a nested module metadata file does not replace it. Standalone profile reading and preparing an actual implementation repository are separate operations.

The profile and repository pin name the export's Git commit, not the source-course commit recorded in delivery `COURSE_COMMIT` markers. Delivery-marker validation does not change that external pin.

## Command ownership and build results

Each profile declares only its own commands. Equal algorithm names in different modules remain separate commands of those consumers. A missing required command or neighbor blocks the selected target before execution; another module's command does not replace it. A partial profile does not imply complete acceptance.

| Platform module | Its `stand` keys |
| --- | --- |
| `01-store` | `store1`, `store`, `backup`, `import`, `jcs`, `store-op`, `spoil-row` |
| `02-installer` | `load`, `manifest-put`, `canonical`, `rights`, `rights-check`, `ring`, `workers-script`, `platform-lists`, `exec`, `install-order`, `env-line` |
| `03-worker` | `worker`, `creates-key`, `said-id`, `said-read`, `door-token-verify`, `group-of` |
| `04-controller` | `controller`, `pass_print`, `order`, `shrink-victim`, `shrink-allowed`, `group-of`, `near-of`, `fresh-age` |
| `05-resource` | `resource`, `object-put`, `object-spoil` |
| `06-console` | `console`, `console3`, `fault`, `rid`, `request-digest`, `values-by-type`, `resolve`, `said-id`, `said-read`, `door-token-issue`, `fresh-age`, `password-hash`, `covers` |
| `07-console-module` | none |
| `08-domain` | `install-domain`, `first-admin`, `domain`, `move`, `view`, `assemble`, `issue`, `password-hash` |
| `09-agent` | `agent`, `join`, `join-batch`, `token-door`, `follow` |
| `10-domain-console` | `domain-console`, `alarms`, `covers` |

Except for `07-console-module`, the reader also permits the shared algorithm names `keys`, `agent-sig`, `accept`, `record`, `ask-sig`, `may`, `peer`, `token`, `seal`, `seal-round`, `seal-member`, `seal-member-round`, `sealing-aad`, `sealing-envelope`, `sealing-open`, `sealing-ring`, `revoked` and `crl`. Admission of a name does not assign every shared package to every module: the package README and the published [vector wire form](../vectors/wire.md) assign its consumers, tables, directions and native interface. A profile entry does not establish execution coverage.

Every `build`, `unit`, `stand`, `adapters` and vector command runs from the directory containing its own profile, including when the assembly replaces a part. Commands use `/bin/sh`. The implementation chooses its program names, flags and wrappers, except the flag of `{rights}` in the command `store` below. `build` and `unit` receive no template substitutions. The explicit build phase builds each needed module once before inputs are fixed. A nonzero build result stops the stand before acceptance. Without a build phase, declared artifacts must already exist. Unit commands run only when explicitly requested. No rebuild occurs after source, profile and artifact identities are fixed or during acceptance. During a run the export's `HEAD` equals the pinned commit and its working tree is clean; the stand checks this before the build, after the build and after acceptance.

Build and unit stdin is closed (`/dev/null`). Their inherited environment is limited to present values of `PATH`, `HOME`, `USER`, `LOGNAME`, `SHELL`, `TMPDIR`, `TMP`, `TEMP`, `LANG`, `LC_ALL`, `LC_CTYPE` and `TZ`; the driver environment, including `CAMMETA_SPECS`, is not inherited. These build/unit rules do not define a new environment map in a profile. After a `build` or `unit` command exits, no process of its process group remains: the stand ends the whole group.

Artifact labels use ASCII letters, digits, `_`, `.` and `-`. Each path is nonempty and relative to the profile directory. Its resolved target must remain inside that directory and must not be the directory itself. An artifact is a file or a separate result directory. File identities use exact bytes; directory identities use relative file names and their bytes. Instance data belongs to stand directories rather than artifacts. A shared library follows its published common contract and its source/dependency identities enter the run passport; this does not authorize importing a neighboring module's private code.

Profile loading resolves artifact ownership; it does not require outputs to exist before their build. After optional builds, and before unit or acceptance, the runner fixes source/profile/artifact identities, including permissions and safe link targets. Escaping links, cycles and special files are refused. Source inventory includes Git-tracked and nonignored untracked files; declared artifacts are sealed separately even when ignored by Git. Build may not change the assembly, profiles or repository `SPEC_VERSION`. A unit command or an acceptance run that changes sealed inputs does not pass. Packaging `07-console-module`, when selected, precedes the builds of its `06-console` and `10-domain-console` consumers.

## Parameters in `keys`

The key set is closed. Parameter values belong to their profile rather than a merged last-writer-wins map.

The recognized key `store_build` is used by store-group targets. `raft` selects group execution; `box` makes the group target not applicable; omission or any other selection remains unexecuted, never PASS. The current profile loader recognizes this key without a separate type or value check. This admission boundary is not permission to add new build kinds or to infer a successful group run.

| Key | Value and purpose |
| --- | --- |
| `role` | Nonempty single-line role name; the owning acceptance contract sets permitted roles and its default. |
| `role_header` | Nonempty single-line name of the role-forwarding HTTP header. |
| `request_line_limit` | Positive integer: the implementation's request-line limit, counted without CRLF. Missing it leaves the limit-boundary checks unexecuted. |
| `path_style` | String `json` or `dotted` for loader diagnostic paths. |
| `tls_stand` | Integer `0` or `1`. A capability declaration does not itself request a TLS run. |
| `pass_stand` | Integer `0` or `1`. |
| `store_build` | Store build selection used by the owning group acceptance; `raft` and `box` retain their distinct applicability. |

An optional key is omitted rather than supplied as YAML null. A key's presence, defaults and applicability are judged by its owning acceptance. An accepted YAML profile is not proof that an implementation or an acceptance target is complete.

## Substitutions

A template may use only the names available to that particular command. There is no union of all stand values available to every command. An unknown name, field lookup, conversion or format specifier is a format error. Literal braces are `{{` and `}}`.

| Command | Available names |
| --- | --- |
| `store1`, `store` | `data`, `rundir`, `socket`, `rights`, `body_limit`, `row_ceiling` |
| `store-op` | `socket`, `dir`, `id`, `tls`, `args` |
| `spoil-row` | `data`, `key`, `what` |
| `backup` | `socket`, `file` |
| `import` | `data`, `file`, `index_base` |
| `load` | `file` |
| `manifest-put` | `socket`, `file` |
| `rights`, `rights-check` | `manifests`, `deployment`, `file` |
| `ring` | `file` |
| `worker` | `data`, `rundir`, `socket`, `manifest`, `sub`, `name`, `server`, `agent_tokens` |
| `controller` | `data`, `rundir`, `socket`, `manifest`, `sub`, `server` |
| `resource` | `data`, `rundir`, `socket`, `manifest`, `rport`, `server` |
| `console` | `data`, `rundir`, `socket`, `manifest`, `port`, `cport` |
| `console3` | `data`, `rundir`, `socket`, `manifest`, `port` |
| `pass_print` | `data`, `sub` |
| `object-put` | `data`, `socket`, `key`, `file` |
| `object-spoil` | `data`, `socket`, `key` |
| `install-domain` | `data`, `socket`, `domain`, `recovery` |
| `first-admin` | `data`, `socket`, `name` |
| `domain`, `domain-console` | `data`, `socket`, `port` |
| `agent` | `data`, `rundir`, `socket`, `agent_tokens`, `relay_port` |
| `join` | `data`, `socket`, `domain`, `recovery` |
| `join-batch` | `data`, `socket`, `domain`, `recovery`, `batch`, `batch_key` |
| `token-door` | `agent_tokens`, `role` |
| `move` | `console`, `recovery`, `args` |
| Other admitted algorithm keys | `input` |
| `adapters.door` | `data` |
| `adapters.load` | none |
| `adapters.tables7` | `fields` |
| Every `vectors` entry | `input`, required in the template |

`data` is the instance data directory; `rundir` is the directory that holds `socket` and the role sockets, one run directory per instance. `socket` is the selected store socket; `rights` is the prepared rights file; the command `store` holds exactly one occurrence `-rights {rights}` or `-rights={rights}`. `manifest` and `manifests` are stand manifest directories for commands assigned them. `file` and `input` are operation/vector input paths. `port`, `rport`, `cport` and `relay_port` are the corresponding stand ports. Store test parameters are `body_limit`, `row_ceiling` and `index_base`. The remaining values name the subsystem, instance/worker, server, deployment, object key, fields file, domain, recovery file, console URL, local token-door directory, role or join batch named by the owning stand contract. The meaning of `dir`, `id`, `tls`, `what`, `batch` and `batch_key` is fixed by the command's owning acceptance contract, not inferred from another command with a similar name.

The runner shell-quotes substituted paths and individual values. Do not add shell quotes around a placeholder. `args` is a prepared sequence of quoted arguments where the owning command assigns it, not arbitrary shell text. `token-door` is an address rather than a shell command: its entire value is exactly `unix:{agent_tokens}/{role}.sock`; its URI substitutions are raw. Do not prefix this address with a command or a directory change.

The `worker` and `agent` command strings begin with the unquoted assignment `AGENT_TOKEN_DIR={agent_tokens}` followed by whitespace and their command. There is exactly one assignment of that name in the template; quoting the assignment, putting it after the command or prefixing a directory-change wrapper is not equivalent. The stand chooses the shared token directory. Profile fields do not create new environment variables, HTTP doors or cross-module protocols; the published lifecycle and stand assign process environment and role sockets. The closed list of the admitted variables is [the environment of stand processes](README.md#environment-of-stand-processes).

## Executable adapters

Adapters are child commands, not imported implementation libraries. The closed adapter ownership is `01-store` → `door`, `02-installer` → `load`, `06-console` → `tables7`; other Platform modules have none. The profile may omit an optional adapter or declare an empty map. Missing adapter coverage remains unexecuted and is named in the plan.

### Store door

`adapters.door` serves one isolated ordinary/admin API instance. Its only substitution is the absolute `data` path. The parent exists; the adapter creates the data subdirectory if its API needs it. The command receives no store socket, rights file, role field or input file through this ABI. It takes its instance path from the argument, not from an inferred working directory or process environment.

The transport is sequential UTF-8 JSON objects on stdin/stdout, one object per physical line ending with LF. Flush each response before waiting for another request. There is no greeting, id, startup frame, pipelining or shutdown frame. Diagnostics go to stderr. One process can receive several requests or EOF before any request; another instance uses another process and data path.

Each request has all four fields: `method` (string), `target` (standard RFC 4648 Base64 of the whole target bytes), `body` (Base64 string or JSON null) and `admin` (boolean). A textual target is first encoded as UTF-8; its query and original percent escapes remain unchanged. The transport does not URL-decode it. Null body means absent body, empty Base64 string means present zero bytes, and Base64 of the text `null` means those four bytes. `admin` selects the administrative side of the same instance; the ordinary role comes from the owning acceptance, not from this frame.

The response has required `status` (integer operation status) and `body` (Base64 string of exact response bytes, including the empty string for zero bytes). Additional response fields are ignored by the current receiver. An application JSON body is serialized to bytes before Base64 encoding; it is not an object in the outer `body` field. Standard Base64 uses `A–Z a–z 0–9 + /` with `=` padding and no line breaks.

No request headers or role credentials cross this channel. The receiver presents a synthetic `content-type: application/json` response header; it does not read response headers from the frame. Raw HTTP and repeated headers belong to the separate HTTP door. An operation refusal is a normal response, not an adapter exit or an outer error frame. The current receiver does not uniformly validate status types/ranges, malformed Base64 or missing fields; those decoder limitations do not authorize malformed frames.

For each flushed request the runner reads one response line before sending another. The transport adds no per-request timeout or line-size ceiling; outer execution can have a timeout. Premature EOF, I/O failure or invalid outer JSON is a transport failure rather than an API refusal. There is no automatic retry. Normal shutdown is EOF on stdin after the last response; the adapter exits normally with code zero and leaves no background service using the temporary instance directory. A final line without LF can currently be read at EOF, but a live response still requires LF and flush to make progress. Local closure waits up to 10 seconds before killing the main process; outer cleanup also removes the registered process group.

### Manifest loader

`adapters.load` is a persistent process with no substitutions. Each stdin request is the absolute UTF-8 path of one manifest file followed by LF, without shell quoting or JSON wrapping. It loads that file alone through the implementation's normal loader.

Each response is one JSON object with exactly the two fields `verdict` (string `ok` or `refused`) and `text` (string), followed by LF and flush. `crash` is not a response verdict; transport, decoder or process failure is not a loader refusal. On success the normal loader has produced a complete manifest; the manifest itself is not this adapter's output. On refusal `text` names the submitted file and preserves the normal class, paths and line information required by the owning tables. Embedded newlines are JSON escapes. A refusal stays inside the stream; it does not terminate the adapter with native exit two. EOF on stdin ends normal execution with code zero. An exception, nonzero exit, premature EOF, absent response, bad JSON or other verdict is not a successful representation of a loader refusal.

`path_style: json` represents diagnostic paths as arrays of string keys and integer indexes. It can distinguish a key containing `.` from multiple path segments, and a string key from an integer index. `dotted` uses dots and `[N]`, without an escaping rule for dots inside keys; it does not represent every diagnostic path. Use a representable path form to transmit the loader's own diagnostics. Line numbers start at one. Whether a diagnostic divergence is a hint or a failing check remains exactly the owning acceptance's rule. Diagnostics are obtained from the actual loader outcome, not a case identifier or expected table row.

The separate `stand.load` launches once per file, uses `{file}` and exposes its native exit/text contract. It is not the persistent adapter protocol.

### Console tables

`adapters.tables7` is an optional admitted adapter of `06-console`; its only substitution is the fields-file path `{fields}`. The existing transport uses one UTF-8 JSON request and response per LF-terminated line, sequentially, flushing a response before the next request. A `secret_in` request has `table`, `field` and `raw`; the reply carries `shown`, nullable `secret`/`login` field names and `why`. A `log_mask` request has `table` and `raw`; its reply carries `masked`. No expected answer is passed in a request. This describes the existing transport, not an added format2 C execution connection: accepting this optional profile key does not execute its checks. Native meanings and outcomes remain in the owning table/package contract.

## Unified vector command

Each optional `vectors` key names a package and its value is the implementation's own shell command containing `{input}`. For Platform packages the name is `common/<package>` or `<module>/<package>`. The namespace owner is canonical; package components use lowercase ASCII letters, digits, `_` or `-`, begin with a letter or digit and contain no `/`. The selected package's README and the [single wire form](../vectors/wire.md) assign consumers, tables, input columns, fixture files, directions and native outcomes. The form's [`wire.tsv`](../vectors/wire.tsv) rows select `vectors`, `stand:<key>` or a nonexecuted layout surface; the generic envelope does not turn one surface into another. The profile map does not grant a neighboring process's code or the runner's expected answers to the implementation.

The runner writes `{input}` as one UTF-8 JSON object, followed by LF. Its field set is closed and every field is required:

| Field | Value |
| --- | --- |
| `format` | Integer lexeme `1`. |
| `package` | Package name from the profile entry. |
| `table` | Nonempty relative table name inside the package, without empty, `.` or `..` slash segments, NUL, CR or LF. |
| `case` | Nonempty UTF-8 row identity; a headerless row without a case uses `line-<physical source line>`. |
| `variant` | String `""`, `write` or `read`, as assigned by the package. |
| `cells` | Object mapping nonempty input-column names to UTF-8 strings, including empty strings. |
| `files` | Object mapping relative input-fixture names to canonical standard RFC 4648 Base64 of exact file bytes; `{}` is allowed. |

The registry may describe other published variants on other/native surfaces. That declaration vocabulary does not widen this envelope: its `variant` is currently only the empty string, `write` or `read`. A new envelope variant is not inferred from a profile entry.

Only input columns and input fixtures are supplied. Expected columns, expected canonical output, expected digest and notes are excluded. A cell's text is not stripped, numerically normalized or parsed/reserialized as JSON by this outer wire: `1.0` remains the string `"1.0"`. The implementation's command interprets the cell and its package markers under the published native form and constructs the native input required by its own function. Native `stand` inputs keep their owning contracts.

For marked source tables the common source-cell transport decodes the declared outer cell wrapper exactly once before the existing semantic interpretation. That transport is [source-cells](../contracts/source-cells.md); it adds no runtime aliases or alternate protocol words. Fixture bytes come from the same export. The package selects only its declared input fixtures, with names assigned by its README; expected tables are not input fixtures. Temporary files needed by the implementation's function are its responsibility in the provided temporary area, without writing foreign paths or changing system owners/groups. The command's working directory is still the profile directory.

The command's successful outer process exits zero and returns one UTF-8 JSON object with exactly `exit_code`, `stdout_b64` and `stderr_b64`. `exit_code` is the native package outcome, an integer lexeme from 0 through 255. The two other fields contain canonical standard RFC 4648 Base64 of exact native stdout/stderr bytes; empty bytes are `""`. For example, the native status can be two while the outer process successfully exits zero. An invalid outer request uses outer exit two and empty stdout; another nonzero outer exit or malformed response is a command failure. Signals, timeouts, inability to start and cleanup failures are stand failures rather than substituted semantic outcomes.

The outer response is compared as JSON, without requiring a trailing LF, key order or particular whitespace. Duplicate object fields, fractional/exponent numeric lexemes, booleans in integer fields and non-JSON numbers are invalid. Base64 must re-encode to the same spelling. The runner unwraps the native bytes and applies the package's published wire form and outcome comparison: whole JSON, subset, exact bytes, raw id without LF, refusal markers or native exit. It does not compute the algorithm for the implementation. An empty object expected by subset comparison means exactly empty; an unconstrained present value and an absent field retain the markers defined by the common stand.

Each executed row is identified by full export SHA, source/table path and SHA, package, consumer, case and variant. A source line number identifies only the row at that exact pin. Every assigned row and direction must execute over the same candidate for full acceptance; a missing profile entry, blocked target or unexecuted check is not success.

## Assembly and input identity

The assembly has exactly two required fields: integer `format: 1` and `modules`, a mapping. Each entry maps a canonical module identity to a nonempty profile-file path, relative to the assembly or absolute. The loaded file is named `acceptance.yaml`, and its `module` equals the assembly key. The assembly has no build, unit, commands, keys or inherited root defaults. A partial assembly is allowed for preparation; absence of a part required by a selected target blocks that target before execution. A complete Platform assembly names all ten Platform modules.

An explicit part replacement replaces one complete, already-listed profile, not selected command values. Duplicate replacement of one module is an error. The replacement retains its own working directory, build results, keys, commands and adapters. Neighboring profiles remain unchanged. Every selected profile names the same external specification commit. The runner does not infer implementation language from the `implementation` string.

The default directory selector uses `assembly.yaml`; an explicitly named index path is not additionally checked for that basename by the current reader. Index entry paths are relative to that index directory or absolute. A relative explicit replacement path is resolved from the invoking working directory. A replacement names an already listed module and replaces its whole profile; it cannot add an unlisted module. An empty module map can be read as an index, but cannot be prepared as an implementation.

Before building or starting processes, the plan names selected targets, commands with their module/profile/working directory, and missing dependencies. The run passport fixes the selected composition, repository commits, source/profile/artifact identities and specification/runner pins, and records build and execution context without secrets. Profile fields cannot override published scenarios, expectations, response forms or coverage assignments. Declaring a complete generic file shape does not prove an approved positive catalog, a finite test provider, sufficient stand parameters, recovery execution or lesson acceptance.
