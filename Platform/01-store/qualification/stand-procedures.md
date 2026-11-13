# Stand procedures of the store qualification

This English text is the canonical `qualification/stand-procedures.md`; the Russian text is a derived translation for people, not in the export.

This file completes [the production qualification of the store](README.md) with three parts: the environment that the entries with D7 bindings need, the means and the qualification of the D7 providers on a virtual machine, and the procedures of the three probes that need only the input of [N6.2](../../common/acceptance/spec/acceptance.norms.md#n62-input-of-the-qualification): `prod-disk-fd`, `prod-replay-limit` and `prod-admin-limit`. The observed outcomes stay those of [N6.3](../../common/acceptance/spec/acceptance.norms.md#n63-probes) and of the [case groups](README.md#case-groups); the results stay those of [N6.5](../../common/acceptance/spec/acceptance.norms.md#n65-results-and-controls). The file adds no outcome, refusal, route, flag, profile field or numeric value of a norm.

It names no actual provider. The `identity`, `invoke`, `observer_ref` and `qualification_ref` of a provider are written by the stand that builds and qualifies it on its machine ([stand data](../forms/production/README.md)); until then an entry that needs the capability is `not_executed` with the capability as the reason.

## Environment of the stand

The capabilities `fault` and `storage` and the probe `prod-disk-fd` need a machine whose block storage, power and wall clock the stand controls. A container shares them with its host and gives none of them. The stand is a virtual machine (the guest) driven by a controller outside it.

| Need | Requirement | Entries |
|---|---|---|
| Controller outside the guest | The judge, the observers and the provider that resets the guest run outside the guest or survive its reset. Evidence written inside the guest before a reset counts only as read after the reset. | RUN-F02, RUN-F04, `prod-fault-stage`, `prod-recover-interrupted` |
| Power reset | The hypervisor resets the guest on a call of the stand, without a shutdown of the guest and without a flush of its caches. The cache mode of the virtual disk is recorded. In a mode where the host acknowledges a flush of the guest without making the data durable on the host, a reset proves nothing about barriers, and the storage binding is not qualified. | RUN-F02, RUN-F04, `prod-fault-stage`, `prod-recover-interrupted` |
| Block device with faults | The store directory lies on its own virtual disk or partition under device-mapper, never on the system disk of the guest. The guest has the targets `linear`, `error`, `flakey`, `dust` and `log-writes` and can replace the table of a live device. The kernel, the `dmsetup` version and the table at each activation are recorded. | RUN-F01, RUN-F02, RUN-F03, RUN-F04, RUN-L01, `prod-backup-temp` |
| Medium | ext4 on that device, the medium named by the storage rows of [`bindings.tsv`](../forms/production/bindings.tsv). The journal mode and the other mount options are recorded; barriers are not disabled. tmpfs is not that medium. | every entry with `storage` |
| Limited volume | A separate small ext4 filesystem of known size: the `volume` of N6.2, its `path` and `bytes`. Its blocks reserved for root are zero or recorded, so that the user of the store meets the full disk at the recorded size. | `prod-disk-fd`, the phase `pre_effect` |
| Block and system-call observation | An observer of the block requests of the store device (data writes, flushes, forced-unit-access writes, their completions and errors) and an observer of the system calls of the store processes (`write`, `pwrite`, `fsync`, `fdatasync`, `sync_file_range`, `rename`, `unlink`, `openat`, with their results). Both run outside the candidate; `blktrace`, `strace -f` and kernel tracepoint programs are examples. | every entry with `storage` or `fault` |
| Wall clock | Root in the guest stops time synchronisation and steps (`clock_settime`) and slews (`adjtimex`) the wall clock of the guest. The monotonic clock of the controller is the independent baseline. | RUN-W03, `prod-id-age`, `prod-clock-group` |
| Separate wall-clock domains | One guest per controlled domain. Processes in one guest share one wall clock: a time namespace does not shift the wall clock, and a preloaded library does not reach a program that reads the clock without the C library. | `prod-clock-group` |
| Descriptors | The stand sets the descriptor limit of one process (`prlimit` or the `LimitNOFILE` of its unit) and reads its actual descriptors and limits (`/proc/<pid>/fd`, `/proc/<pid>/limits`). | `prod-disk-fd` |
| Declared environment | The conditions of [N3.3](../../common/acceptance/spec/acceptance.norms.md#n33-declared-environment) hold in the guest; the cgroup of the load gate is the unit of the candidate in the guest. | the numeric groups |

Under N3.3 the processes of a credited run have only the loopback, and the [group stand](../acceptance/3/README.md#store-group-stand) puts all members on the loopback of one machine. The voters of one run therefore share one guest and one wall clock, and `prod-clock-group` stays `not_executed` with the reason `clock`, as the [stand data](../forms/production/README.md#bindings) say for members that share one wall clock.

Every run records the guest: its virtual processors and memory, the virtual disk and its cache mode, the kernel, the device-mapper tables, the filesystems and their mount options, the clock source and the state of time synchronisation.

## D7 providers on the virtual machine

A provider qualifies only by its activated positive and negative controls on the same guest, kernel and device as the case; a receipt from another machine qualifies nothing. A positive control shows that the activation reaches the named boundary of a reference program of the stand. A negative control is a known defect of the provider or of the reference program that the observer must detect. The observers are the judge's: block and system-call observation, file identity and public state. Counters, logs and answers of the candidate are not observations of a binding.

The reference programs are small programs of the stand, not candidates: a reference writer appends one record to a file and calls its barrier before it acknowledges; its defective copies acknowledge before the barrier or skip the barrier.

### fault

| Activation (`bindings.tsv`) | Means on the guest | Independent observation | Positive control | Negative controls |
|---|---|---|---|---|
| `pre_effect`, `refuse` (RUN-F01, RUN-F04) | The stand fills the limited volume with its own file outside the store directory until the first changing call of the operation gets `ENOSPC` with no byte written. | The system-call trace shows `ENOSPC` on the first changing call of the operation and no successful changing call into the store directory between activation and answer; the storage states `before` and `after` are equal. | The reference writer gets `ENOSPC` on its first write, and its file is unchanged. | Free space left by the filler (inactive); a refusal after a partial write (that is not `pre_effect`); an activation of another scope. |
| `medium`, `unknown` (RUN-F02, RUN-F04) | A reset of the guest while operations of the case are between their writes and the end of their barriers; or a recording of the store device by `log-writes`, replayed to a chosen mark between flushes onto a copy device that the store then opens. | The block observer or the log gives the completed writes and flushes before the reset or the mark; the state is read on reopen after the reset. | The reference writer keeps every acknowledged record after each reset or mark. | The copy that acknowledges before its barrier loses an acknowledged record at some reset or mark; if it never does, the reset does not reach the medium and the binding is not qualified. A kill of the process presented as a reset is detected: the cache of the guest survives a kill. |
| `barrier`, `barrier_error` (RUN-F03, RUN-F04) | After the data writes of the operation have completed on the device, its flush fails: a table that fails only flushes, or a table swap at that point. The barrier call of the store returns `EIO`. The fault stays active for the crossings that the case names and is then cleared. | The block observer shows the completed data writes of the operation and the failed flush; the system-call trace shows `EIO` from the barrier call; storage `before`, `after` and `reopen`. | The reference writer gets `EIO` from its barrier after its data reached the device. | A flush that succeeds while the provider reports a failure (no-op); an error before the data writes (that is another phase); a table left in place after deactivation (stale). |
| `recover_mark`, `interrupt` (`prod-recover-interrupted`) | The stand runs `recover` on the directory of a stopped member and interrupts it after the phase mark is written with its barrier and before the mark is removed: by a kill of its process group, or by a reset of the guest. The interruption points cover every changing system call of `recover` between the mark and its removal, the removal of the input included. | The system-call trace numbers the changing calls of `recover`; the file listing and hashes of the store directory are taken at each interruption; the mark is present at the interruption. | At each point the trace shows the mark present and its removal not yet made. | An interruption before the mark or after its removal (wrong phase); an interrupter that lets `recover` complete (inactive). |
| `backup_output`, `output_error` (RUN-L01, `prod-backup-temp`) | The destination of `backup` lies on its own small filesystem or on a device of the `error` or `flakey` target; a write or a barrier of the output fails. | The system-call trace of `backup` (temporary file, writes, barrier, rename) and the listing of the destination directory before and after. | The reference writer, writing the destination, gets the failure. | A failure injected into the store directory instead of the destination (wrong target); no failure (inactive); a failure after the rename (wrong phase). |
| `copy_after_headers`, `stream_close` (RUN-H03) | No guest is needed: the daemon is killed or its connection closed after the raw-stream observer of the judge has received the status line `200` and the headers. | The raw stream of the judge. | The stream ends after the headers. | A kill before the headers (wrong phase); no kill (inactive). |

A `barrier` fault that stays active across a checkpoint also reaches the barriers of the background work of the store, as every crossing of its phase does; the history check below then covers every write answered before and during it.

### storage

The binding injects nothing; it observes. The provider records the identity of each object of the store directory (path, inode, bytes, `sha256`) in the states `before`, `after` and `reopen`, the barrier attempts and errors of the store processes from the system-call trace, and their completion on the device from the block observer. Under a fault of the medium the state `reopen` is the start of the store after the reset of the guest; a restart of the process alone is the state `after`, not `reopen`.

Negative controls: the reference writer without barriers shows no device flush (no-op barrier); an observation of another directory (wrong object); barriers reported by the provider that the trace did not see (false counter); a `reopen` state copied from before the reset (stale reopened data: inode, bytes or times differ from the files the store opened).

### clock

In the mode `observe` (RUN-W03, `prod-id-age`) the provider shifts nothing. Time synchronisation of the guest is stopped or its state recorded. The provider samples the wall clock and the monotonic clock of the guest; the baseline is the monotonic clock of the controller, and the round trip of each sample is recorded as its uncertainty. Positive control: a step of the guest wall clock made by the stand in a control run appears in the observations with its size within the recorded uncertainty. Negative controls: a provider that reports without reading the guest (self-report) and a provider that reads the controller instead of the guest (wrong domain) both miss that step; samples out of order (reversed timing); samples of another scope (stale).

In the mode `control` (`prod-clock-group`) the provider steps or slews the wall clock of each guest by its `offset_seconds` at activation and returns it at deactivation; it needs one guest per domain. Positive control: each domain shows its offset against the baseline after activation and its return after deactivation. Negative controls: the offset applied to another guest (wrong domain); an offset that the observer does not see (unactivated); an offset reported without effect.

### progress

The binding needs no guest. The latch is a sink of the judge that stops reading; resources are read from `/proc/<pid>` of the targets (descriptors, resident memory) and from public status. Its negative controls are those of the [D7 contract](../../common/acceptance/seams.md#d7-test-side-evidence-bindings).

## History check across faults

An entry with a `fault` or `storage` binding keeps the history of the operations of its load: the request, the answer and the monotonic times of sending and receipt. After each fault and after the final reopen the judge checks every operation of the history, not only the one at the fault:

- a write answered with success is present with its version after reopen (P/01.1 R144);
- no version is issued twice, and issued versions are kept (P/01.1 R295);
- an operation answered `ambiguous` is present whole or absent whole, with its batch and its `id` (P/01.1 R144);
- an operation answered `unavailable` on a proven refusal before the effect is absent, and its `id` is not occupied (P/01.1 R295).

The checker has its own negative controls: a history with a deleted acknowledged write, with a repeated version and with half a batch must each be detected.

## Probes on the input of N6.2

Each probe reads the input of N6.2. A field or key it needs that is absent, or whose `threshold_ref` is not approved, makes the probe `not_executed` with that name as the reason. Before it scores the candidate the probe runs its controls: the same procedure against the reference fixtures of the stand, small servers that implement only the observed slice, either correctly or with one named defect. The correct fixture must come out GREEN and each defective one with its named mismatch; a failed control is red, class `stand` (N6.5). Each run records the flags the stand passed, the actual limits of the processes and the raw requests, answers and times.

### prod-disk-fd

Input: `volume`; keys `disk` and `descriptors`. One daemon, started by the store command of the profile.

Full disk:

1. The store directory (`-dir`) lies in `volume.path`. The size of that filesystem matches `volume.bytes` up to the recorded filesystem overhead; otherwise red, class `stand`.
2. The probe writes a known set of rows and records their versions; storage `before`.
3. The stand fills `volume.path` with its own file, outside the store directory, to a free-space level, and runs a write load: puts of new and existing keys and batches, each with a fresh `id`. The levels go down from the size of several rows to zero, so that refusals fall before the effect, after the effect and during the background work of the store. At each level the load runs until the store refuses or the space is exhausted.
4. Each answer is classified with the system-call observation: 503 `unavailable` (`disk_full`) is lawful only if no changing call of that operation succeeded in the store directory; a success must survive reopen; an `ambiguous_*` outcome is lawful at any level.
5. While the disk is full, reads of the known rows answer as before, with the same versions.
6. The stand removes its file without restarting the daemon (the same process, observed). Writes with fresh `id` succeed; a repeat of an `id` answered before follows the replay rules of P/01.1.
7. The daemon is stopped and reopened; on the virtual machine also after a reset of the guest. The history check above runs over the whole load.

The disk budget bounds the largest size of the store directory (`-dir`) under the declared workload (P/01.3 R036). The `threshold_ref` of `disk` names the record that approved the threshold for that result; without it the threshold is not approved, and the probe is `not_executed` with the reason `disk`. The observations of the steps above are still recorded as measured scope and make no GREEN.

Exhausted descriptors:

1. The daemon starts with its descriptor limit, soft and hard, equal to the value of `descriptors`; `/proc/<pid>/limits` confirms it, otherwise red, class `stand`. The connection-limit flags (`-max-conns`, `-api-conns`, `-api-per-address`) are set above that value, so that descriptors run out before a connection limit; the values are recorded.
2. The probe starts requests that the daemon has begun to read before exhaustion and holds them within the input-phase intervals declared by the implementation.
3. The probe opens connections until the descriptor count of the daemon (`/proc/<pid>/fd`) reaches the limit, and then opens more.
4. A new connection gets `connection_limit`, 503 `unavailable` with `Retry-After`, if it is accepted, and is closed otherwise; a connection that stays open with no answer beyond the declared idle interval is a mismatch. Each started request ends with its own definite outcome, not a close without an answer. The process of the daemon stays alive throughout, and after the probe closes its connections `/v1/status` answers.
5. The probe confirms that the descriptor count actually reached the limit; otherwise red, class `stand`.

Controls: a fixture that exits on exhausted descriptors; one that closes started requests without an answer; one that leaves a new connection open without an answer; one that answers `disk_full` after it has written into its directory; one whose acknowledged write is gone on reopen; one that writes again only after a restart.

### prod-replay-limit

Input: the key `replay_limit`: a value and the unit declared by the implementation (P/01.3 R329). The procedure makes load in units of concurrent replay requests or of replay requests per second; a unit it cannot make is an instrument error, red, class `stand`.

1. One daemon. The probe applies distinct writes with fresh `id`, enough to replay above the limit, and records each first answer.
2. Below the limit (half the value in its unit) each replay gets its first answer with `again`, and no new version appears.
3. Above the limit (a recorded multiple of the value) the probe measures from its own times that the load exceeded the value; otherwise red, class `stand`.
4. Each answer above the limit is either the first answer with `again` or 503 `unavailable` with `Retry-After` in whole seconds; the replays served within the unit do not exceed the value beyond the recorded uncertainty of the judge.
5. After the load the rows and versions are unchanged, and each `id` that got 503 gets its first answer with `again` on a later replay: neither the record nor the `id` memory was touched.

Controls: a fixture with no limit; one that answers 503 without `Retry-After`; one that applies a refused replay as a new write; one that forgets the `id` after a 503.

### prod-admin-limit

Input: the key `admin_connections`.

1. One daemon, the connection limits of [daemon-flags.tsv](../forms/daemon-flags.tsv) or recorded other values; the descriptor limit of N3.3.
2. The probe holds `-max-conns` connections on each role socket and `-api-conns` on the API listener if it listens; one more connection on each gets 503 `unavailable` with `Retry-After: 1`. If it does not, the limits were not exhausted: red, class `stand`.
3. A connection to `admin.sock` is admitted, and `GET /v1/status` on it answers.
4. The probe holds `admin_connections` connections on `admin.sock`, each admitted; one more gets 503 `unavailable` with `Retry-After`.
5. After release the operator connects as before.

The daemon may close a connection that waits for its next request after the declared idle interval. The probe completes each step within that interval from the oldest held connection; a held connection closed by the daemon before the check makes the step an instrument error, red, class `stand`.

Controls: a fixture whose `admin.sock` shares the ordinary limits; one without a limit on `admin.sock`; one that closes the connection above the limit instead of 503; one that answers 503 without `Retry-After`.
