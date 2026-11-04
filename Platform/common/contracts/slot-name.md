# The slot name contract: grammar, «by name», slot order, next number, role process

This English text is the source; the Russian translation `ru/contracts/slot-name.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

A common contract of the module «Платформа» (ADR-0083 addendum (5), addendum (13), addendum (30); the stage C guess POOL-ORDER-51-01, the
Architect's decision of 2026-10-25). The owner is chapter [P/03.2](../../03-worker/spec/03.2-worker.norms.md) Н1.4 (the slot and its name). The participants are
the slot capture (P/03.2 Н3), the controller ([P/04](../../04-controller/spec/04-controller.norms.md): the keeper of a place, «number above
want», the victim of shrinking), [the pool contract](pool.md), the worker script ([P/02.4](../../02-installer/spec/02.4-installer.norms.md) Н1.5),
the console. Moved from P/03.2 Н1.4 («The order of names and the next number») without a change of behaviour; the name of a role process and the number
N are the Architect's answers of 2026-10-25 (P/04 was silent about the form).

Normative keywords follow [the course canon](../../../НОРМАТИВНЫЕ-СЛОВА.md).

## Form

Slot names are the keys `<sub>/slots/<имя>` (taken and given up — by the slot rows); the server of a role process is the field `server`
of the heartbeat `<sub>/heartbeats/<имя>`. Forms and outcomes: `Platform/03-worker/data/slots.schema.json`,
`Platform/03-worker/data/slots.outcomes.tsv`, `Platform/03-worker/data/heartbeats.schema.json`,
`Platform/03-worker/data/heartbeats.outcomes.tsv` (layout audit, В-58; the Architect's decision of 2026-10-25).

## Grammar and «by name»

```yaml
name:      <prefix>-<suffix>; prefix — slot.prefix of the manifest (1–8 lowercase Latin letters, default w); the suffix
           ^[a-z0-9]+(-[a-z0-9]+)*$; the name is checked by the grammar and the prefix of its own manifest
by_name:   lexicographic comparison of the full name by ASCII bytes; a row's own prefix comes before its continuation
           (w-a < w-a-b < w-ab); the locale and the traversal order of the store do not matter
```

## Slot order

For choosing a free slot and the keeper of a place:

1. First the names whose whole suffix after `<prefix>-` is digits 0–9: by the numeric value of the suffix (a non-negative
   decimal integer without machine overflow; the length of the suffix is not limited), on equality — by name. `w-01` and `w-1` are
   different names with an equal number.
2. Then the other admissible names — by name. The final digits of `w-srv-a-2` are not taken out as a number: it is a name of the second group.

Example: `w-0`, `w-01`, `w-1`, `w-2`, `w-10`, `w-a`, `w-b`, `w-srv-a-1`.

## Next number

A new name is `<prefix>-<max + 1>`: max is the largest number among the digit suffixes of this subsystem and prefix, including taken
and given-up names; if there are none, max = 0; the new suffix has no leading zeros; other names do not take part in max; without overflow.

## Role process name and its number

```yaml
role_name: <prefix>-<s>-<N> — the instance name from the unit (P/02.4 Н1.1, %i), s — SERVER_NAME (the environment file contract «Environment variables»; it may contain «-»)
parse:     prefix — that of its own manifest; N — the last segment after «-»: a decimal integer without leading zeros, ≥ 1, without
           overflow; s — everything between «<prefix>-» and «-N», by the grammar of SERVER_NAME ^[a-z0-9]+(-[a-z0-9]+)*$ (the environment file contract «Environment variables»; layout audit Б-24)
server:    s equals the field server of the worker heartbeat — a role process of the server s with the number N; s ≠ server, there is no heartbeat or server in it does not
           read — not a role process (neither of this nor of any server): «number above want» does not apply to it, it does not
           enter live(s)
not_role:  out of form — not a role process: w-5 (no server in the name), w-srv-a-02 (a leading zero), w-srv-a-0 (N < 1), a foreign
           prefix, the last segment is not a number
use:       the number above want (P/04 Н3) and the victim of shrinking compare N as an integer, not by the slot order; 1 — the base role process,
           2…99 — ordered by the controller (P/04 Н3 «order()», ADR-0084)
```

## Vectors

The package [`slot-name`](../vectors/slot-name/README.md): the slot order (the example of P/03.2, a suffix longer than 64 bits, «by name»),
the next number, the number of a role process and «not a role process» (a server with «-», s ≠ server, no heartbeat, out of form). A participant:
the package [`pool`](../vectors/pool/README.md) is the package of the common contract pool, executed by common; this contract is a participant there
(the pool order, the keeper, «number above want»; В-59; CM-RECORD-VECTORS-128, the Architect's decision of 2026-10-25).

## Correspondence to former lessons

From P/03.2 Н1.4 «The order of names and the next number» — whole; P/03.2, P/04 and the pool contract refer here. The Architect's answers
of 2026-10-25 (POOL-ORDER-51-01) on the form of the name of a role process are the section «Role process name and its number».
