# Connecting copies to the P/01 store

`gen_box.py` reads the format, limits and floor calculation from P/01.1/P/01.3. The complete store procedure lives
in `go/*.go`: this is the kit's closed **handwritten runtime**, with `origin: handwritten`. The codec and formulas
remain `generated`. The F1/continuation rule was published in 809c168d1 and merged in main1655; its KIT uses official
export `32d2bb12d97ca8f2c32fba19723db78077b5bf94`. Neither runtime nor judge reads a line's implementation files.
For the known form preceding 809, the generator preserves the old box primitives and excludes the new executor/API.
A partially specified F1 rule errors rather than allowing a weaker transfer.

`CopyStorage.WithCopyLock` holds the same lock as ordinary writes and batches. Its callback receives `CopyTxn`:

| Method | Store owner's responsibility |
|---|---|
| `Snapshot` | Read actual rows, the upper index and durable `ImportProgress` |
| `BeginImport` | Persist progress and **the new F1 as the first row write** under one barrier, advancing the index; the source carries no id/admission memory, and the owner preserves its floor operation's ordinary metadata |
| `WriteImport` | Write the supplied row at its exact version, without allocating a new version through ordinary put |
| `FinishImport` | Persist Done after the kit procedure verifies the actual rows |

Every success means the ordinary durability barrier has completed. Errors may have an unknown outcome: after reopening,
`Snapshot` must expose what actually survived. `ImportProgress` contains the immutable input's SHA-256, base, phase and
the complete first F1, including items/index/generation_at. Continuation compares them and skips already written rows;
it never computes a new generation from a changed clock. The copy's floor contributes to upper/clock but is not copied.

Implementation wiring:

- Connect these operations to your data format and barriers. The kit does not choose that format.
- Supply `CopyControl.Open(command)`: backup opens the actual live store through its existing admin transport;
  box import/restore exclusively opens a stopped target. Also return close.
- Connect `admin.Env.Copy` to this `CopyControl` through existing `launch.App.Admin` -> `admin.Run`. Remote backup may
  implement the same `admin.CopyOps` through a transport invoking the procedure on the live store.
- Supply the actual Dir, effective ceiling and clock. Backup has **no** -dir flag: empty `f.Dir` does not stand for
  the live daemon's directory. Import/restore targets `f.Dir`; a zero ceiling selects the normative default.
- Read progress during ordinary open. `CopyStartAllowed` refuses an unfinished phase: startup maps this to
  `launch.Refusal`/exit 2, and ordinary read/write HTTP handling maps it to 503. Continuation uses a separate path.
- Existing YOURS Backup/Import/Restore remain implementation-owned. New scaffolds delegate to connected CopyOps;
  older edited scaffolds may call the same port. A missing port explicitly refuses.

`test_copy_storage.py` is the runtime's external judge. Its file-backed owner persists actual state with sync/rename;
ordinary Get/Put read and modify that state, and CLI calls use ordinary flags/admin. The judge selects all **51**
ordinary `daemon_copy` rows through stages.tsv and executes their acceptance/3 inputs. Source-store preparation comes
from P/01.3's README: two actual manifest rows. It compares normalized expectations only after execution.

A separate YOURS `CallSeam` connects to those same native owner functions. It executes published `store-copy-floor`:
restore -> external backup -> partial import -> reopen -> continuation. Observations come from actual writes, F1 and
completeness; expectations are never passed into the adapter. The live DataDir fixture is an immutable sentinel.
Other checks cover refusal before mutation, a lost floor response, immutable input/base, exact versions, id memory,
0600 mode and temporary files. Five executable mutants check floor non-transfer, continuation, versions, index and false Done.

This judges kit code through a file port. Acceptance of the line implementation and MiniMax39 remains with its runner.
