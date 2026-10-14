# C6 — runtime asks / scenario tokens

Branch: codex/course-c6-runtime, base C5 merge c4e7f27d; accepted forms
through main 101c2b44 (merged into this branch as c7587656). Product and lessons
are untouched. C6 is not merged. The independently approved live readers are
already in main as 9021e4d0.

1. Form: FORM.md records the accepted ADR-0074 and inbox decisions.
2. Code: generic scenario scope and optional by in the authenticated role path;
   per-target/trigger RAM token cache. Shared fixture follows 2ab84bcd.
   `vms/autoask.py` adds the shared event executor, elected local contribution
   builder and member-book reader with signed per-pair role tokens. A reply
   arriving after a route/topology/assignment change is discarded before dial.
3. Review: final diff has not been submitted; platform changes stay in branch.
4. Checks: `evidence-components.json` records the actual commands, exits,
   counts and external artifact hashes. Python unit part 1: 1085/0/0;
   part 2: 923/4/0. The four failures were corrected: obsd test startup now
   waits for a connection, the role-agent double preserves request_id,
   testsub2 uses block YAML, and the now-readable scenario load debt is gone.
   Affected modules, including malformed-policy refusal: 131/0/0. Earlier
   Cluster 117/0/0, Domain 228/0/0, DomainVMS 164/0/0 and JS 42/0/0 passed.
   This is not a full green run on the corrected tree or C6 acceptance.
5. Runtime: auto publisher/reader/executor are implemented as components but
   not connected to the worker loop. Relay lift and camera embedding remain
   to connect. Old asks are active until the atomic branch switch. This is
   an implementation checkpoint, not completed C6 acceptance.
6. Deferred: C6b upstream fallback, C7 domainpart removal, ADR-0075 windows3/4
   after C7, new M10 lessons after C7. Common fixture sync is course debt
   recorded here per 2ab84bcd; VMS parity ledger is not used for that debt.

Raw logs: /Users/murat/w2c/course-book-merge-evidence/c6-*.log.
Final evidence will record commands, actual exits and artifact SHA256.
No raw logs are committed.
