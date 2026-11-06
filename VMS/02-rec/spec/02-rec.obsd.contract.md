# The contract of the archive engine `obsd` (lesson V/02)

This English text is the source; the Russian translation `ru/spec/02-rec.obsd.contract.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The contract of the part `obsd` of the subsystem `rec` — the socket protocol and the properties of the engine that the recorder (chapters
V/02.3, V/02.4) and the archive door (V/02.5) rely on. This file is the canon; the norms of chapter [V/02.2](02.2-rec.norms.md) are what `rec` requires of the
part (the service, the share, the environment, the timeouts, the engine version). The engine is ObjectStorage (tree `2bbee4a`, 2026-10-02) with the patches
01–07 (V/02.2 N1.4); the contract describes what is observable on the socket and in the volume, not the structure of the client.

## Transport

- A unix socket (`SOCK_STREAM`) — the socket of the share `rec.obsd` (V/02.2 N1.2); the path MUST be shorter than `sun_path` (107 bytes on Linux, 103 on
  macOS), otherwise the daemon does not start.
- The daemon creates the socket `0660`; a peer of a foreign uid is admitted only if it is in the group `OBSD_CLIENT_GROUP` (Linux — any group
  of the process, macOS — the primary one); otherwise the connection is rejected.
- A second daemon on the same socket does not start (the lock `<socket>.lock`).

## Frame

```
u32 len | u32 id | u16 op | u16 flags | i32 status | u32 jsonLen | json[jsonLen] | tail
```

- All integers of the header are little-endian; `len` is the bytes after itself (16 + `jsonLen` + the length of `tail`).
- `id` is chosen by the client; an answer carries the `id` of its request; answers may come out of order — matching is by `id`; an answer with a foreign
  `id` the client discards.
- `flags` bit 0 — `REPLY`. The `status` of a request is 0; of an answer — 0 success, otherwise a code (below) and the JSON `{detail}`.
- JSON is a UTF-8 object (an empty one reads as `{}`); 64-bit numbers and handles are JSON numbers, exact unsigned.
- `tail` — the binary data of the operation up to the end of the frame.
- The frame limit is `maxFrame` from the `HELLO` answer (default 256 MiB); larger — `FRAME_TOO_LARGE`, the connection is closed.
- `CANCEL` (op 4) `{id}` — without an answer: the answer to this `id` is no longer needed.

## Session, connection, handles

- The first frame of every connection is `HELLO` (op 1): the request `{proto: [1, 1], client, pid, session, logLevel}`, the answer
  `{proto, server, engine, pid, maxFrame}`. `client` is the process name (`[A-Za-z0-9._-]`); `session` is the client's session token, a string,
  new for every session; `logLevel` is the word of `OBSD_LOG_LEVEL` (V/02.2 N1.3), the client sends `warning`.
- A session ≠ a connection: handles belong to the session; a session may have several connections, any of them uses any of its
  handles. A repeated `HELLO` with the same token before `OBSD_SESSION_LINGER_MS` (3000 ms) expires — the same session; later, or
  after a restart of the daemon — a new empty session: the old handles answer `UNKNOWN_HANDLE` (`pid` in the `HELLO` answer is the sign
  of a new daemon).
- `BYE` (op 2) `{}` → `{}` — after all handles of the session are closed, the writers too. The last connection is gone for the
  linger without `BYE` — a disappearance: the readers and the volumes are released, the writers are detached (below, «Grace»).
- A handle is `u64`: the high byte is the kind (1 volume, 2 reader, 3 writer), the rest is a counter of the daemon without repeats. Not of the right kind —
  `WRONG_HANDLE_KIND`; unknown to the session — `UNKNOWN_HANDLE`. A writer holds its volume: closing the volume before the writer is
  harmless.

## Operations

| op | Name | Request → answer |
|---|---|---|
| 3 | `PING` | `{}` → `{}` |
| 5 | `STATS` | `{}` → `{uptimeSec, sessions, writers: [{key, owner, state, graceLeftMs, progress}], jobs: [{op, volume, client, state, ageMs}]}` |
| 10 | `VOLUME_OPEN` | `{uri}` or `{params: {k: v}}`, `maxParallelReads?` → `{volume}`; the params of a file — `{schema: file, path}`, of a bucket — `{schema, host, port?, region, bucket, path, access_key, secret_key}`; a volume is recognised by `schema://host/path`, not by the credentials |
| 11 | `VOLUME_CLOSE` | `{volume}` → `{}` |
| 12 | `VOLUME_EXISTS` | `{volume}` → `{exists}` |
| 13 | `VOLUME_FORMAT` | `{volume, size, tunables?: {maxBlockSize, optimalReadSize, lockRefreshSec}, label, checkSpace}` → `{info}` |
| 14 | `VOLUME_RECOVER` | `{volume}` → `{result}`: 0 clean, 1 recovered, 2 error |
| 15 | `VOLUME_SPACE` | `{volume}` → `{available, capacity, free}` |
| 16 | `VOLUME_MOUNT_RO` | `{volume}` → `{reader}` |
| 17 | `VOLUME_MOUNT_RW` | `{volume, owner}` → `{writer, reattached}` |
| 20 | `READER_CLOSE` | `{reader}` → `{}` |
| 21 | `READER_INFO` | `{reader}` → `{info: {formatVersion, uuid, createdAtUnixSec, maxVolumeSize, tunables, label}, label}` |
| 22 | `READER_STATUS` | `{reader}` → `{status: {firstBlockId, numBlocks, usedSize, availableSize, totalWritten, reindexBlockId?}}`; `usedSize`, `availableSize`, `totalWritten` are bytes; `totalWritten` is a counter of the engine: the bytes written into the volume since its formatting, it grows, the ring does not decrease it |
| 23 | `READER_STREAMS` | `{reader}` → `{streams: [name]}` |
| 24 | `READER_TIMELINE` | `{reader, stream, from, to, minGap, mode}` → `{intervals: [{start, end, size, streamId}], ready}`; `mode`: `""` — build, `boundary` — from memory, `quick` — only from memory, otherwise `ready: false` and the reads are started |
| 25 | `READER_SEQUENCES` | `{reader, stream, from, to, pageHint}` → `{entries: [{streamId, tag, start, end, blockId, offset, size}]}` (`pageHint` — 1000) |
| 26 | `READER_FIND` | `{reader, stream, from, backwards}` → `{found, entry}` |
| 27 | `READ_SEQUENCE` | `{reader, entry}` → `{info, count}`, in `tail` — `count` SMPL records |
| 30 | `WRITER_CONFIGURE` | `{writer, settings: {maxBlockSize, optimalReadSize, incomingBufferSize, blockFlushPeriodSec, sequenceFlushPeriodMs, secureSealBlocks}}` → `{}`; 0 — the engine default; after `reattached` the settings already set — success |
| 31 | `PUT_MEDIA` | `tail`: `writer:u64le streamLen:u16le stream[streamLen] SMPL`; the answer is a status (below) |
| 32 | `FINISH_MEDIA` | `tail`: `writer:u64le streamLen:u16le stream`; `EMPTY_RESULT` — there was no open sequence |
| 33 | `WRITER_FLUSH` | `{writer}` → `{}`: the tail goes to the medium, the block is not closed |
| 34 | `WRITER_RESIZE` | `{writer, size}` → `{status}`; smaller than what is written — the oldest blocks are released in steps of `OBSD_RESIZE_STEP_MB` (1024), writing stands still meanwhile |
| 35 | `WRITER_CLOSE` | `{writer}` → `{}` after the flush (up to 30 s); after the answer what was written is readable; how long the client waits for the answer — V/02.4 N1.5 «close deadline» |
| 36 | `WRITER_ABANDON` | `{writer}` → `{}`: give up the volume without writing (no queue, no status, no index); the lock is removed only if it is still this writer's; the next mount may require a recovery |

**`PUT_MEDIA`:** `OK` — taken; `SEQUENCE_LOST` — taken, but an earlier sequence is lost; `WRITER_STOPPED` — not
taken, the writer will take nothing more; `SEQUENCE_TOO_LARGE` and the other `SEQUENCE_*` — not taken.

**Repeat:** a break of the connection after sending a non-idempotent request (`PUT_MEDIA`, `FINISH_MEDIA`, `VOLUME_FORMAT`,
`VOLUME_MOUNT_RW`, `WRITER_CLOSE`, `WRITER_RESIZE`) does not mean «not executed»: the daemon may have executed it, only the answer is lost;
the client MUST NOT repeat such a request blindly. An answer with a non-zero status is an answer, not a break.

## Time and the SMPL record

- Archive time is milliseconds since 1900-01-01 UTC: `archive_ms = r(unix_s × 1000) + 2208988800000`, where `unix_s` is a
  binary64 number, the product is one binary64 multiplication (rounded to nearest), `r(p)` is round half up: `⌊p⌋ + 1` if the
  fractional part of `p` is (exactly) ≥ 0.5, otherwise `⌊p⌋` (not a language function). Examples: `1700000000.0004` → `p` = `1700000000000.4001…`
  → `3908988800000`; `1700000000.0005` → `p` = `1700000000000.5` → `3908988800001` (round half to even would give `…800000`);
  `1700000000.0006` → `3908988800001`. The vectors come with the VMS data family (the analysis of the V/01 review, question 5).
- The SMPL record is big-endian: `"SMPL" major:u32 subtype:u32 flags:u32 begin:u64 end:u64 subLen:u32 bodyLen:u32 sub body`.
  Video — `major = 2`; `subtype` — a FourCC in u32 LE (`H264`; `H265` is a form of the engine, the input of `rec` is only `H264`, V/02.4 N1.2); `sub` — `width:u32le height:u32le`; `body` — an Annex B
  access unit, the codec parameters are in every key frame; `end` — `begin` + the buffer duration, if there is none — 40 ms.
- Sound — `major = 3`; `subtype` — a FourCC in u32 LE (`AAC ` with a space); `sub` — `channels:u8 rate:u32le`; `body` — an AAC frame with an ADTS header; `end` — `begin` +
  the frame duration; every frame is a key frame, flags 0. The frame type does not change inside a sequence (`SEQUENCE_TYPE_CHANGED`): sound is a stream of its own (V/02.3 N1.1).
  This is a requirement on the engine, not an observed property: it is confirmed on the first run with a live `obsd` (V/02.2 N1.4).
- Flags: `NEED_KEY_FRAME = 1<<0`, `NEED_PREVIOUS_FRAME = 1<<3`; a key frame — neither of the two; a dependent frame —
  `NEED_KEY_FRAME`.

## Engine properties

- **Visibility:** a reader sees only closed blocks, the ones closed by the moment of its mount; `WRITER_FLUSH` does not close a
  block. A block is closed when: it is full (`maxBlockSize`); `blockFlushPeriodSec` has passed since a finished
  sequence was put into the queue; the writer is closed. An unfinished sequence the engine cuts by
  `sequenceFlushPeriodMs`.
- **A sequence** is opened by a key frame: a dependent first one — `SEQUENCE_NEEDS_KEY_SAMPLE`; the engine cuts
  sequences by `optimalReadSize` at key frames; a sequence does not cross a block boundary: a frame that does not
  fit into the block — `SEQUENCE_TOO_LARGE`, the following ones up to a key frame — `SEQUENCE_NEEDS_KEY_SAMPLE` (the frames are lost). A block
  is fit for a stream if it is ≥ the read size + 3 MB.
- **A stream** is a name; a stream has no other metadata. Time grows inside a sequence; a new sequence of a stream
  MAY start earlier than the previous one.
- **Ring:** a volume is formatted by size (quota), a full one overwrites the oldest blocks; nothing is deleted by
  age; `firstBlockId > 0` — the ring has closed.
- **One writer per volume per host:** a second `VOLUME_MOUNT_RW` — `ALREADY_LOCKED`.
- **Grace:** the writer of a disappeared session closes the open sequences (as `FINISH_MEDIA`), detaches,
  remembers `owner` and waits for `OBSD_WRITER_GRACE_S`; `VOLUME_MOUNT_RW` with the same non-empty `owner` — `reattached: true`, without a new
  lock and recovery; another one — `ALREADY_LOCKED` until the end of the grace, then a clean volume. `owner` is a claim of identity, not
  a secret.
- **Mount in a disappeared session:** a `VOLUME_MOUNT_RW` finished after its session disappeared detaches the
  writer at once (as in «Grace»). This is a requirement on the engine, not an observed property: it is confirmed on the first run with a live
  `obsd` (V/02.2 N1.4).
- **Volume fence** (patch 07): before every block, status, release, deletion and resize the engine checks
  the volume lock by path; a writer with a foreign lock stops — `PUT_MEDIA` → `WRITER_STOPPED`, `detail` «volume lock
  lost»; a foreign lock file is never deleted. The lock of a dead daemon holds until it becomes stale (`lockRefreshSec`, 30 s).
- **`VOLUME_UNCLEAN`** on `VOLUME_MOUNT_RW` — the volume was not closed cleanly: mount it after `VOLUME_RECOVER`.
- **Daemon stop** (SIGTERM): closes all writers in parallel (each up to 30 s); a writer that takes longer
  than 45 s to close is named in the log, the daemon exits with code 3.

## Status codes

A closed list; a non-zero `status` of an answer is one of them, `detail` — the engine's words:

| Code | Name |
|---|---|
| 0 | `OK` |
| 1–25 | `GENERIC_ERROR`, `PERMISSION_DENIED`, `OPERATION_IN_PROGRESS`, `OPERATION_CANCELED`, `IO_ERROR`, `INTERNAL_ERROR`, `DATA_CORRUPTED`, `INVALID_CIPHER_KEY`, `ALREADY_FORMATTED`, `PATH_NOT_EMPTY`, `NOT_A_VOLUME`, `ALREADY_LOCKED` (12), `UNSUPPORTED_FORMAT`, `READ_ONLY` (14), `VOLUME_UNCLEAN` (15), `NO_BLOCK`, `INVALID_BLOCK_RANGE`, `PARTIAL_CONTENT`, `EMPTY_RESULT` (19), `NO_SPACE` (20), `BLOCK_ALREADY_EXISTS`, `UNEXPECTED_BLOCK_ID`, `PROTECTED_VOLUME` (23), `DEVICE_OR_RESOURCE_BUSY`, `GENERIC_NETWORK_ERROR` (25) — in order |
| 100 | `INVALID_ARGUMENT` |
| 110–118 | `SEQUENCE_SAMPLE_TIME_INVALID`, `SEQUENCE_TIME_INVALID`, `SEQUENCE_TYPE_CHANGED`, `SEQUENCE_DUPLICATE_INIT_DATA`, `SEQUENCE_LATE_INIT_DATA`, `SEQUENCE_MISSING_INIT_DATA`, `SEQUENCE_NEEDS_KEY_SAMPLE`, `SEQUENCE_DISCONTINUITY`, `SEQUENCE_DURATION_INVALID` |
| 120–123 | `QUEUE_FULL`, `WRITER_STOPPED`, `SEQUENCE_TOO_LARGE`, `SEQUENCE_LOST` |
| 130–131 | `WRONG_HANDLE_KIND`, `INDEX_REPLAY_PENDING` |
| 1000–1005 | `PROTOCOL_ERROR` (a frame or JSON out of form), `UNKNOWN_HANDLE`, `PROTO_VERSION` (there is no common version — the connection is closed), `SHUTTING_DOWN`, `UNKNOWN_OP`, `FRAME_TOO_LARGE` |

## Not served

Multi-volume readers and writers, protected volumes, erasure, encryption, the sequence builder, recovery with
progress.
