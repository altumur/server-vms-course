# member-report-policy.hcl — a member's agent, in the domain holder

**Role.** Lesson 10, step 7. A camera may never be reachable from the domain, so every connection between them is opened by the camera's agent: it reads what the domain publishes for it (as before) and, on the same pass, writes its REPORT — `objects/domain/members/<member>/…`: the member's heartbeats and snapshot shards, the outcomes of kept edits, its copy of the shared settings' pointer, the holder record it follows, its epochs, its alarm pages, and `reported` last. The domain reads its own cluster's store and nothing else (`domain/uplink.py`, `member_copy`).

**One policy per member**, rendered with its name, so that a member writes only its own report: the same one-writer-per-prefix rule the cluster's ACLs keep for `vms/*`. `destroy` because a report drops what the member no longer has. The member's agent keeps its own cluster's policy (`agent-policy.hcl`) unchanged.

**Not exercised by the tests** (no Nomad here); what it grants is what `tests/domain/test_uplink.py` does.

**Lesson 17.** A camera that can reach only its relay has no connection to the domain holder at all. It gets this policy in the RELAY's cluster: it reads `relay/*` — what the relay's agent relayed down for it (`chain.relay`) — and writes its report into the relay's store, which the relay folds into one bundle for the domain. The relay's agent writes `relay/*` under its own policy (`agent-policy.hcl`).
