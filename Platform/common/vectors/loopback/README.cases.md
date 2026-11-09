# Judge-only case data

This English text is the source; the Russian translation `ru/vectors/loopback/README.cases.md` is derived from it (ADR-0121).

Generic rules remain in [README.md](README.md). The following original passages preserve the existing case data as judge-only provenance.

### Original passage 1

31 rows: a v4 loopback (including the boundary and the scheme `http`), leading zeros, three parts, a part outside 0–255, a hexadecimal
notation — a name; an IP outside the loopback, `0.0.0.0`; v6 `::1` in three notations — a loopback; with a zone, `::ffff:127.0.0.1`, `::`, another v6 — `ip`;
names (`localhost` in two cases, a server name); a dot at the end — a name; `[::0.0.0.1]` (a v4 tail, the value `::1`) — a loopback;
`[::127.0.0.1]` — `ip`; `userinfo@` before the host does not interfere; not a URL, an empty host, an input not an object, without `url`, `url` not a string — `@exit 2`. The notation of the host is taken as

End of judge-only case data.
