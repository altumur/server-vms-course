# Store production probes

This is the observation contract of [production acceptance](../qualification/README.md) (judge-only: qualification procedures): the properties that are judged over supplied observations. A check does not start, discover or qualify an implementation, and an implementation does not import it.

`OBSERVATION_PASS` means only that the supplied observations passed that check. It is not a native run or a production result.

## Outcomes

A check ends in one of four outcomes: the observation checks passed; a normative observation mismatch; an instrument or form error; missing inputs, where the check names its concrete missing bindings.

## Probes

Groups are partial slices of the [case groups](../qualification/README.md#case-groups) (judge-only: qualification procedures): a probe does not execute a whole group.

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
