# Public target and stand requirements

`runner-targets.tsv` declares the public interfaces and build results needed for
a selected target. A target name identifies a contract scope; it does not select
an implementation or a set of inputs. Each command retains its own module owner.
The implementation chooses its executable names and wrappers.

## Table form

The table is UTF-8 with physical LF rows and TAB-separated cells. Its first row has the following fields (`\t` denotes TAB):

```text
target\towner\tstand_commands\tstand_addresses\tkeys\trequirements\tnorm_anchors
```

`target` and `owner` are strings. Every other cell is a compact JSON value.
Object fields described below are closed and required. Arrays may be empty;
duplicate entries are invalid. Target names are unique.

| Column | Public meaning |
|---|---|
| `target` | Target name. |
| `owner` | Module responsible for the target. |
| `stand_commands` | Required callable interfaces, each `{owner,section,key}`. |
| `stand_addresses` | Required addresses, each `{owner,key}`. |
| `keys` | Required existing profile parameters, each `{owner,key}`. |
| `requirements` | Build-result owners, alternatives and conditional requirements, as below. |
| `norm_anchors` | Repository-relative public normative document links with heading fragments. |

A callable's `section` is exactly `stand`, `vectors` or `adapters`: it identifies
the existing map in the owning profile. `key` is that map's existing command,
package or adapter name. For example,
`{"owner":"01-store","section":"stand","key":"store"}` refers to the store
owner's `stand.store`. The callable column groups these interfaces without
converting a vector or adapter into a `stand` key. Equal names in two modules
remain two separately owned interfaces. These table fields add no profile field,
command, substitution, address or parameter.

An address is not a shell command. In particular, `09-agent`'s `token-door`
retains its published address form. Parameter values and admitted command
substitutions remain those of the owning public profile and protocol.

## Conditional requirements

`requirements` has exactly four fields:

- `artifacts`: module names whose public build results are needed in the ordinary
  target scope. A library can supply build results without supplying a command.
- `any_of`: callable references in the same `{owner,section,key}` form. When
  nonempty, at least one listed interface is required; declaring both is allowed.
  The alternatives do not become simultaneous unconditional requirements.
- `when`: objects `{condition,require}`. `require` is one callable reference.
- `replace`: objects with exactly `condition`, `stand_commands`,
  `stand_addresses`, `keys` and `artifacts`. An applicable replacement supplies
  the complete command/address/parameter/build-result dependency set for that
  scope instead of the ordinary set. It is not added to the full-target set.

The finite condition vocabulary describes the operation being exercised:

| Condition | When the requirement applies |
|---|---|
| `row_spoil` | The operation uses the published durable row/body/index spoil interface. |
| `object_put` | The operation uses the published object-put interface. |
| `object_spoil` | The operation uses the published object-spoil interface. |
| `join_batch` | The operation uses the published batch-join interface. |
| `rights_check` | The selected rights-validation operation requires the rights-check interface. |
| `console_only_pass` | Only the console PASS scope is selected, rather than the full multi-module PASS scope; the listed complete replacement applies. |

The first five conditions occur only in `when`; `console_only_pass` occurs only
in the PASS target's `replace`. Conditions describe existing obligations, not
new command words or configuration switches. The actual operation determines
which condition applies. An unused optional interface is not an unconditional
dependency. An operation using it still requires its declaration: absence leaves
that dependent operation unexecuted, rather than satisfying the requirement.
Requirements in `when` continue to apply to operations that use those interfaces.

For the console-only replacement, build-result owners are the owners of its
listed interfaces and parameters, including the target owner. The replacement
does not require the full PASS scope's unrelated module build results.

## Normative interfaces

The canonical [profile contract](PROFILE.md#command-ownership-and-build-results)
owns command/module ownership and public build results. Its
[substitutions](PROFILE.md#substitutions),
[parameter forms](PROFILE.md#parameters-in-keys),
[executable adapters](PROFILE.md#executable-adapters), and
[vector command](PROFILE.md#unified-vector-command) retain their existing
meanings. Table links use repository-relative paths so that each resolves in the
same public document tree. No file-content identity is a substitute for a norm.

The target's public operation and interface contracts govern its inputs and
outcomes. This table describes dependencies; it does not define those algorithms
or their expected outputs.
