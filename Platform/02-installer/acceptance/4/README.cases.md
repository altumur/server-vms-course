# Judge-only case data

This English text is the source; the Russian translation `ru/acceptance/4/README.cases.md` is derived from it.

Generic rules remain in [README.md](README.md). The following original passages preserve the existing named case associations as judge-only provenance.

### Original passage 1

| Scenarios | Subject | Norm |
|---|---|---|
| `s1-put-invalid-source` | an invalid candidate is refused by manifest put with code 2 and the source name; the source file stays intact | P/02.3 N3 «Manifest change» step 1, N4 |
| `s2-new-existing`, `s3-rotate-invalid` | a refused creation or ring check leaves the existing file byte-for-byte intact | P/02.4 N1.9 secrets; P/02.4-R400, P/02.4-R401 |
| `s4-new-exclusive` | concurrent O_EXCL creation at one path directly in `$data` succeeds once; the command creates no parent directory ([layout](../../forms/README.md#scenario-layout)) | P/02.4 N1.9 secrets new; P/02.4-R371 |
| `s16-command-options` | options out of `daemon-flags.tsv` are refused with code 2 before any file and stderr names the option: an unknown `-bogus` and a foreign `-last` (of `rollout`) at `secrets new` — the target file stays absent | P/02.4 «Command options»; P/02.4-R271; `command_options` of the refusal catalogue |
| `s12-secrets-walk-unknown`, `s13-secrets-walk-kept` | the selection of the secrets walk: an unknown `identity/x` is listed with code 1, the kept rows leave the selection | P/02.4 N1.9 «Walk»; P/02.4-R383, P/02.4-R386, P/02.4-R388, P/02.4-R394 |
| `s15-secrets-walk-unreadable` | a walked row `domain/book-seal` without `seed_secret` (out of the form of its family) under the prefix `domain/`: not listed as unknown, untouched, code 1 | P/02.4 N1.9 «Walk»; P/02.4-R396 |
| `s5-poll-healthy`–`s11-poll-read-equality` | the pure poll: catch-up under writes, a break, last at a follower, membership, two voters, equality at tick/read deadline | P/02.4 N1.9 poll; P/02.4-R305, P/02.4-R307, P/02.4-R319, P/02.4-R321, P/02.4-R324, P/02.4-R330, P/02.4-R332 |

### Original passage 2

[`inputs/seam-bad.subsystem.yaml`](inputs/seam-bad.subsystem.yaml) is the owned fixture of `s1-put-invalid-source`: a YAML document with only `name`, missing the mandatory manifest structure. The scenario copies it with `@file`, calls the normal `manifest put`, and checks the refusal and unchanged source bytes. It is deliberately outside the accepted manifest corpus. The remaining file inputs are literal owned strings in the seam table.

### Original passage 3

after the call. In `s12` (the default D) `identity/x` matches no row family: it is listed, code 1; the kept rows
`domain/testsub/ledger` and `domain/testsub/badges/b1` (testsub `domain.kept: [ledger, badges/]`) are not listed. In `s13` (the given
prefix `domain/`, only kept rows) nothing is walked: code 0. `s15` walks one row `domain/book-seal` of its family without the required `seed_secret`: unreadable by the outcome of the reader `admin`, code 1, `unknown` empty. The three seams are excluded from the judgement (README, «Secrets walk selection»).
