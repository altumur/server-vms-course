# Judge-only case data

This English text is the source; the Russian translation `ru/forms/README.cases.md` is derived from it (ADR-0121).

Generic rules remain in [README.md](README.md). The following original passages preserve the existing named case associations as judge-only provenance.

`domain-role-http` invokes ordinary authenticated role POST/PUT/GET/DELETE and batch handlers, the real spread pass, the real member copy receiver and its local `may`. Fixtures seed valid neutral users/groups/roles, live folders and confirmed member rows. A forbidden legacy role is inserted only to test the ordinary family reader and spread refusal, not to bypass the tested door. Read back actual supervision after creation, omitted-field edit, replacement and clear; exercise unknown/unconfirmed references, self-reference, builtin admin and final-snapshot batch guards. Counters observe actual target writes, not only response codes.

`domain-person-login` invokes the real person login and PBKDF2/signature code. Pause the old request after its confirmed credential read, without a common process lock; through ordinary doors delete the person, advance both clocks beyond the deletion hold and create a new person with the same name and a different password. Resume the old real verification and observe that it produces no token; a fresh ordinary login of the new person succeeds. Output verified iat/exp and flags only, never passwords or JWT bytes.

The two-target-attempt handover fixture uses two real trusted, signed and sealed backups. Suspend actual old restore I/O while the process and its ordinary turn renewals remain live; source call-off/disconnect is not a target completion. Concurrent authorized prepare/take/move must refuse without pending or restore writes. The first claim is made to conflict at its actual store boundary; resume and join old work, then complete a fresh prepare/take of the second copy. Observe the I/O history and actual rows/keys/signer: no old restore write follows the accepted second prepare, and the final state belongs to one copy. No canned claim, crypto verdict, expected state or lock flag replaces these effects.

The cleanup fixture fails an actual obsolete-object delete after a confirmed accepted mark, then issues exact same and nonrefreshing heard requests before a new generation. Count real deletion attempts: the early-return paths neither promise cleanup nor undo the accepted report. The last request reaches cleanup and removes the remainder.
