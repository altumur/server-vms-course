# Judge-only case data

This English text is the source; the Russian translation `ru/acceptance/pass/README.cases.md` is derived from it (ADR-0121).

Generic rules remain in [README.md](README.md). The following original passages preserve the existing named case associations as judge-only provenance.

### Original passage 1

| № | Scenario | Norms |
|---|---|---|
| 01 | the ticket lives with the request: the credentials do not leave, the door of the list works, a write by the ticket; outside the list, the write `/session`, a foreign subsystem, without a ticket, over TCP — 401; the answer is given — the ticket is dead; the series and the journal `pass.called` | `ticket`, `journal`, `counter`, P/06.3 N1.9 |
| 02 | the headers to the worker and to the client; 412 `problem+json`, 204, a type outside the list — 502; `nosniff`, `sandbox`; the limit `wait` — 504 | `to_worker`, `to_client`, `types`, `timeout` |
| 03 | a fresh `may` — 403; two tokens, one revoked: the ticket of the first is 401, the second works; a switched-off person on a member: the ticket is alive, `grants: []`, the stream is closed | `ticket` step 5, `close` |
| 04 | the console is open: there is a ticket, the kind of the session gives no callback | `ticket` step 3 |
| 05 | the stream: reads and `/changes`, a write — 401, `Last-Event-ID`, the answer as it arrives; the stream closes with the request and on the revocation of the token | `stream`, `close`, `ticket` step 4 |
| 06 | a table `service: true` by the ticket: a person without rights reads and writes their own, a row in a batch; a row outside the list — 401 of the whole batch; without a ticket the door is closed; the feed by the ticket: a row of one's own `user` comes also on removal, a foreign one and one without the field `user` — do not | `service`, P/06.3 N1.9 «Batch rows», P/06.1 N1.6, N2 «Change feed» |
| 07 | the common lane is busy with passes, their callbacks go through | P/06.5 N2, the contract `order` step 1 |
| 08 | the callback listener: its own role and server — yes; without a ticket, a foreign role, another server — 401; without a leaf, a foreign CA, the validity, EKU — a handshake refusal; the main listener does not accept a ticket; a server leaf not of the role of the addressee — no pass, the body did not leave | `callback_transport`, `transport`, «The callback leaf» |
| 09 | a switched-off person at the holder: the ticket is 401, the stream is closed by `domain/disabled` | `ticket` step 5, `close` |
| 10 | a write of the first kind: the worker of the door receives the token of the person in `Authorization`, the addressee of the ticket does not see it, the door has no ticket header; a door outside the list — 401 | `first_kind`, P/06.3 N1.9 |
| 11–13 | the check without login under a race (ADR-0119 addendum (18)): `POST /domain/verify` by the ticket of `probe-p`; at the bounds of the keys 4 (pair), 19 (author), 9 (name, three authors) two simultaneous wrong ones (`@together`) — one 401, the second 429; after — 429 also with the right password: the count is not more than 5/20/10; a success at the bound does not spend the budget; an author whose only exhausted key is the name key checks another name | the gate contract «Attempt limit» `verify` `answer`, `outcome`, `retry`; P/08.4 N1.2a, N1.10; P/06.7 N1.15 |
