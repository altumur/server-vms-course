# Change 0133-p03-command-counts-before-call

change: 0133-p03-command-counts-before-call rev 1 · lessons P/03.4 · author spec103 · state review

Publication parent `5c2aa1c47b74df4d722c8daa8366b0a9d342ba35`. Task P01.10.5.1 (ADR-0133 addendum (1) item 3): the heartbeat field `command_counts` was defined as outcomes of action calls, while `refused` and `expired` marks are written before a call; that they count stood only in checklist pointers to judge-only scenarios. The comment of the field now states it. No new outcome, number or field.

| Artifact | Operation | Before blob | After blob | After SHA256 |
|---|---|---|---|---|
| `Platform/03-worker/ru/spec/03.4-worker.norms.md` | MODIFIED | 434a1d2cf6b7cd80388c0099cd86dc1add4efb88 | 690f6cf040ac248b6539da5001376fd9c661bac5 | 964ad51a606b37e95a2d21dbcf42b686af73335614c504d84fb0c2ea11326851 |
| `Platform/03-worker/spec/03.4-worker.norms.md` | MODIFIED | cdf27d2d9e9a993ab9005b4e4285a8f50f8b8ba0 | c3b8d90dcdd2dbe851f9a10a9a98e02c1b27119a | addf65bf37e67f63117fb469ba2e5ff1b687bceb73836dbc157554bcc1fed1c5 |
