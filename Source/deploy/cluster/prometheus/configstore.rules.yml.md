# configstore.rules.yml — the store's alerts over its raft metrics

**Role in the module.** Lesson 2 (the store) and ADR-0070, step 1: the product's `deploy/prometheus/configstore.rules.yml`, the same three rules, over the lines every configstore daemon gives on `GET /metrics` of its doors (`w2cplatform/configstore.py`, the notes: /metrics). Installed beside the scrape of the doors as `/etc/w2c/prometheus/configstore.rules.yml`.

## The rules
- `ConfigstoreVotersNotAsDeclared` — `configstore_raft_voters != configstore_raft_voters_expected` for 5 minutes: a server taken out, or a join with `-force` never followed by the third.
- `ConfigstoreFollowerBehind` — a server's `configstore_raft_index{kind="applied"}` more than a thousand entries behind the group's furthest, for 2 minutes. The lag is a difference between servers in the rule; no member asks another.
- `ConfigstoreElectionsChurn` — more than three elections in ten minutes (`configstore_raft_elections_total`).

## Notes
- `tests/test_configstore.py::test_every_door_says_its_raft_on_metrics_in_the_products_words` holds every `configstore_raft_*` name a rule reads to the names a live daemon gives.
