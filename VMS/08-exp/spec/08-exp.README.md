# V/08 Export — instructions for an implementation

This English text is the source; the Russian translation `ru/spec/08-exp.README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

What an implementation of the subsystem `exp` builds and how to check the result. The canon is the norms of the chapters `08.K-exp.norms.md`; these instructions
do not add to them. The platform is the export `cammeta-specs` `7a875c75`.

## Inputs and their priority

- The canon: the norms of the chapters `08.K-exp.norms.md` (N1–N5 of each chapter; the addresses `V/08.K N…`).
- The canon of the manifest: [`exp.subsystem.yaml`](../exp.subsystem.yaml): the bytes as they are.
- The door: [`08-exp.api.openapi.yaml`](08-exp.api.openapi.yaml).
- Neighbours: the archive doors V/02.5, the frame route V/03.3 N1.5, reading an interval V/05.2, `backend` V/11.
- The lecture (`ru/08-exp.md`, for people, not in the export) explains the reasons.

## What to create — the result by chapter

| Chapter | What the implementation has | Check |
|---|---|---|
| V/08.6 | the worker `exp` holds the parts by placement, the part's volume `files` with the share `exp.files`, `cursor` at least every 5 s, `result`, the camera log `export.*` | acceptance |
| V/08.7 | reading the segments through the doors of `rec` by the rule of V/05.2, audio, holes — `partial`, the gateway's live frame, the archive frame, remuxing and transcoding, splitting, ZIP AES-256 and the PDF password, «in one file» by the leading part | acceptance |
| V/08.8 | the requests `cancel`, `delete`, the expiry `result.expires` from the end of the part, deletion of the files and of the row by the holder | acceptance |
| V/08.9 | the door `files` (token, author, `attachment`, `Range`, log), `parts` by role | acceptance |

## Order

First the platform and lessons 02, 03 with the role `expworker`, then `exp`, then `backend` with `/exports` (V/11).

## Pitfalls

| Norm | Possible mistake | How to keep the behaviour |
|---|---|---|
| V/08.6 N1.1 | keeping the order as a separate row or in the leading part alone | the common fields — in each part; the order — in the leading one |
| V/08.6 N1.2 | removing a part by `ends` or `retire_when` | the holder removes it by deleting the row at `result.expires` |
| V/08.6 N1.6 | writing the password into the log | only the flag `password: true` |
| V/08.7 N1.1 | waiting for a catch-up recording of a hole | a file with a hole, `partial` |
| V/08.7 N1.2 | taking the frame from the camera holder or from the last block of the recording | only the gateway `live`, `/frame` |
| V/08.8 N1.4 | keeping the files longer than `result.expires` or counting the expiry from creation | delete the files and the row, `export.deleted` |
| V/08.9 N1.2 | letting a person to the bytes by the log right | only the part's `by` |
| V/08.9 N1.2 | writing `export.read` on each `Range` | one row per download |

## Done when

The lesson's acceptance passes on the stand; the manifest loads with the strict loader without edits.

## On a divergence

The order of sources: the chapter norms → the manifest → the lecture. If a norm is silent or contradicts itself — a question to VMS Specification with the place,
a counterexample and a proposal.
