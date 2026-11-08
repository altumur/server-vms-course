# Store production probes

These are the public observation checkers of [production acceptance](../spec/production-acceptance.md). They judge supplied observations. They do not start, discover or qualify an implementation, and an implementation does not import them. Python 3.12 standard library only.

`OBSERVATION_PASS` means only that the supplied observations passed that check. It is not a native run or a production result: the command always reports `native_executed: 0` and `production_passed: 0`.

## Commands

Run from this directory with `PYTHONPATH` unset:

```sh
python3.12 -B -m store_probes --list
python3.12 -B -m store_probes
python3.12 -B -m store_probes --capture <file> --probe <name>
```

`--list` is the inventory and exits 0. With no capture every probe reports its concrete missing bindings and the command exits 3. `--capture` reads a JSON file of format `cammeta-store-probes-v1`; omit `--probe` to keep the rows of all eight.

| Exit | Meaning |
|---|---|
| 0 | observation checks passed |
| 1 | normative observation mismatch |
| 2 | instrument or form error |
| 3 | missing inputs |

## Probes

Groups are partial slices of the [case groups](../spec/production-acceptance.md#case-groups): a probe does not execute a whole group. `--list` prints the owning norm references and required bindings of each probe.

| Name | Property | Case groups | Budgets |
|---|---|---|---|
| `01-connections` | Connection limits and refusal above them | none | `BUDGET_OVERFLOW_REFUSAL` |
| `02-input-drain` | Input phase deadlines and raw drain | RUN-T01, RUN-T02, RUN-T03 | `BUDGET_IDLE`, `BUDGET_HEADERS`, `BUDGET_BODY`, `BUDGET_DRAIN` |
| `03-lock-wait` | Finite wait for the mutation lock | RUN-L02 | the `-leader-wait` value |
| `04-barrier-replay` | Barrier failure and same-id replay | RUN-F03 | none |
| `05-data-ownership` | Exclusive ownership of the data directory | none | none |
| `06-cost-id` | Write and import cost, id retention | RUN-W01, RUN-W02, RUN-W03, RUN-W04 | `BUDGET_WRITE_P99`, `BUDGET_WRITE_GROWTH`, `BUDGET_WRITE_BYTES`, `BUDGET_IMPORT_ORDINARY`, `BUDGET_IMPORT_WORST`, `BUDGET_IMPORT_GROWTH`, `BUDGET_MEMORY_ORDINARY`, `BUDGET_MEMORY_WORST` |
| `07-framing` | Raw HTTP framing | RUN-T02, RUN-H02 | none |
| `08-backup-rows` | Backup rows and incomplete output | RUN-L01, RUN-H01, RUN-H02, RUN-H03 | `BUDGET_BACKUP_ORDINARY`, `BUDGET_BACKUP_WORST` |

The checkers take budget values from the supplied capture and do not read the budget table. Binding the approved values, launching a stand and collecting observations belong to the acceptance programme; this directory adds no profile field, port, flag or adapter.

## Provenance

The four modules are unchanged bytes of the acceptance runner commit `05f81051b72eb758f7d2f91cbffd4006db2b6c91`. Commit identifiers and carrier lines inside them are the historical provenance of those checks, not this export's identity.
