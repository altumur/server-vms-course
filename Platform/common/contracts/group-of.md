# The group-by-host contract: `group_by` with `cut_at: host`

This English text is the source; the Russian translation `ru/contracts/group-of.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

A common contract of the module «Платформа» (ADR-0083 addendum (5), addendum (13): a common algorithm of several processes is a contract, not copies
in chapters; the stage C guess W03-GROUP-01, the Architect's decision of 2026-10-23). The owner is lesson
[P/04](../../04-controller/spec/04-controller.norms.md) (Н1.3 `group_by`; ADR-0011, ADR-0053). Participants: the controller —
the placement of a group whole on one worker (P/04 Н1.3, Н3); the worker — the stamp `group` of a request submitted by the worker, and one
unfinished action call per group ([P/03.6](../../03-worker/spec/03.6-worker.norms.md) Н1.5, Н3); the unit door — the refusal
of the source by the url step of [the row check](row-check.md). The rules are moved from P/04 Н1.3 `group_by` and the header of the vectors
[`group-of`](../vectors/group-of/README.md) without a change of behaviour.

Normative keywords follow [the course canon](../../../НОРМАТИВНЫЕ-СЛОВА.md).

## Group

```yaml
group:      one value of the field placement.group_by.field; for a field type: url with cut_at: host — the host of the address in one spelling:
            lowercase, without the trailing root dot; an IP literal — as netip writes it: IPv6 without brackets, zeros collapsed,
            the zone removed, IPv4-mapped — as IPv4; the scheme and the port do not enter the group (rtsp:// and ipint:// to one host, :554 and
            without a port — one group)
host:       the place of the host is by the schemes of the field ([the address contract](../url-credentials.md) «Schemes»): host: authority — the host of the authority
            after the last «@» (for a scheme with fragment: none «#» is an ordinary character); host: path — the first segment of the path, the node
            of the authority is a hub and does not enter the group; the path is empty — there is no place of the host
none:       a node of the authority from none of its scheme — the unit is not in a group; none applies only in its own scheme (rtsp://file/x —
            the group file); the node is compared as written, with userinfo and port, the host in it — in one spelling (the address contract «Schemes» node);
            the conversion of IPv4-mapped to IPv4 — only for the group key, not for a node of none (GROUP-NODE-01)
readable:   a host is RFC 1123 labels (a label of 1–63 characters, a name ≤ 253 characters without the root dot; longer — the host does not read;
            the stage C guess GO-DNS-01, the Architect's decision of 2026-10-23) or an IP literal; anything else — %-encoding, «_», non-ASCII characters, a numeric last label not
            written as a decimal IPv4 whole (010.0.0.50, 10.1, 0x0a.0.0.1; numeric — including octal with a leading 0
            and hexadecimal 0x…: cam.0x50 — the stage C guess GROUP-NUMERIC-01, the Architect's decision of 2026-10-23), a non-numeric port
            after the host — the host does not read
alone:      there is no value, it is empty, the host does not read or there is no place of the host — the unit is not in a group and is placed alone;
            there is no common «group without a value»; no value or empty — without a group and without a refusal, whether the field is required is П4
            of [the row check](../row-check.md) (the stage C guess GO-EMPTY-01, the Architect's decision of 2026-10-23)
refusal:    the refusal of the source is the url step of the row check (bad_url: the address contract А15 and «Schemes»): with cut_at: host an unreadable
            host is a refusal, not «accepted without a group»; a refusal by the url rule does not cancel the group of a readable host — the old row
            stays with its neighbours (the vector names both the group and the refusal)
```

## Vectors

The package [`group-of`](../vectors/group-of/README.md): an address → a group (`<none>` — not in a group) and a refusal. (ADR-0083 addendum (32) item 2)
