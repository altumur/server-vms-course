# Judge-only case data

This English text is the source; the Russian translation `ru/vectors/password-hash/README.cases.md` is derived from it (ADR-0121).

Generic rules remain in [README.md](README.md). The following original passages preserve the existing case data as judge-only provenance.

### Original passage 1

«Specification»; the expectations were computed by two independent implementations of PBKDF2-HMAC-SHA256.

### Original passage 2

13 cases: 3 hashes, 10 checks (2 `true`, 8 `false`, of them 6 — a string not of the form; the count was corrected by the generator's finding PH-G01).

### Original passage 3

Who performs is by the form of `input`: `{password, salt}` (the rows `hash-*`) — the process `domain` (`08-domain`, writes the hash of people and of the break-glass account, P/08.4 N1.1, N1.6); `{hash, password}` (the rows `verify-*`) — the process `domain` (the login of people, P/08.4 N1.2) and the console (`06-console`, the break-glass entry, P/06.7 N1.10, the gate-and-pass contract «Break-glass entry»). The console does not write the hash; the agent (`09-agent`, `carry`) and the installer (`02-installer`, `secrets seal`) carry the string and seal it ready-made (ACC-VECTORS-CONNECT-03: a row is performed by the role whose norm calls its function; the Architect's decision of 2026-10-27).

End of judge-only case data.
