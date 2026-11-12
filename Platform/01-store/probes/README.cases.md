# Judge-only probe instructions

This English text is the source; the Russian translation `ru/probes/README.cases.md` is derived from it (ADR-0121).

The observation contract remains in [README.md](README.md). The following original passages preserve the description of the judge's own runs and programs.

### Original passage 1

These are the public observation checkers of [production acceptance](../qualification/README.md). They judge supplied observations. They do not start, discover or qualify an implementation, and an implementation does not import them. Python 3.12 standard library only.

### Original passage 2

`OBSERVATION_PASS` means only that the supplied observations passed that check. It is not a native run or a production result: the command always reports `native_executed: 0` and `production_passed: 0`.

### Original passage 3

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

### Original passage 4

Groups are partial slices of the [case groups](../qualification/README.md#case-groups): a probe does not execute a whole group. `--list` prints the owning norm references and required bindings of each probe.

### Original passage 5

## Provenance

The four modules are unchanged bytes of the acceptance runner commit `05f81051b72eb758f7d2f91cbffd4006db2b6c91`. Commit identifiers and carrier lines inside them are the historical provenance of those checks, not this export's identity.
