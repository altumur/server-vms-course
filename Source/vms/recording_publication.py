"""C2/C3/C4 facts produced by ordinary camera/recorder workers (ADR-0074).

Recipients come from the copied assignment, or the declared poll home for an unassigned camera.
No domain issuer, remote store, persistent road or configuration write.
"""
from __future__ import annotations

import json
import logging

from w2cplatform.domain.placement import placed
from w2cplatform.rows import PARSE_ERRORS, finite
from w2cplatform.variables import GuardFailed
from .recording_books import recording_value, source_value


def publish(worker, family, items):
    """A failed slot guard never retries and never suppresses the worker's pulse."""
    if not worker.name:
        return False
    prefix = f"{worker.sub.name}/{family}/"
    domain = worker.spec.domain
    if domain is None or not any(rule.source == prefix for rule in domain.merged.values()):
        return False
    try:
        worker.put_under_slot(prefix + worker.name, items)
        return True
    except GuardFailed:
        return False


def publish_facts(worker, family, status):
    if not worker.name:
        return False
    try:
        from .recording_upstream import upstream
        from .recording_polls import polls
        items = {"sources": sources, "primaries": primaries, "upstream": upstream, "polls": polls}[family](worker, status)
        return publish(worker, family, items)
    except OSError:
        # A store outage leaves the last publication intact and never suppresses a pulse.
        logging.getLogger(__name__).warning("%s: control facts unavailable for %s", worker.name, family)
        return False


def member(vars_):
    row, _ = vars_.get("domain/member")
    value = (row or {}).get("cluster")
    return value if isinstance(value, str) and value else None


def recipients(assignment, *, include_origin=False):
    names = ([assignment["origin"]] if include_origin else []) + [assignment["cluster"], *assignment["copies"]]
    return list(dict.fromkeys(names))


def ref_of(vars_, row):
    cam = str(row.get("cam", ""))
    if cam.startswith("ref:"):
        return cam[4:]
    camera, _ = vars_.get(f"cam/cameras/{cam}")
    return str((camera or {}).get("ref") or "")


def sources(worker, status):
    own, out = member(worker.vars), {}
    now = finite(worker.wall())
    for st in status:
        ref = st.get("ref")
        if not own or not isinstance(ref, str) or not ref:
            continue
        assignment = placed(worker.vars, "rec", ref)
        if assignment is None:
            if st.get("polls") is not True:
                continue
            from w2cplatform.domain.topology import poll_home, member_topology
            try:
                home = poll_home(worker.vars, own)
                centre = member_topology(worker.vars, own)["centre"]
            except PARSE_ERRORS:
                continue
            targets = list(dict.fromkeys([home] + ([centre] if centre else [])))
            value = {"ref": ref, "to": targets, "polls": True, "live_url": "",
                     "server": str(worker.server or ""), "as_of": now}
            out[str(st["id"])] = json.dumps(source_value(value), ensure_ascii=False, allow_nan=False, sort_keys=True)
            continue
        if assignment["origin"] != own:
            continue
        value = {"ref": ref, "to": recipients(assignment), "live_url": str(st.get("live_url") or ""),
                 "server": str(worker.server or ""), "as_of": now}
        for field in ("codec", "push", "polls"):
            if st.get(field):
                value[field] = st[field]
        out[str(st["id"])] = json.dumps(source_value(value), ensure_ascii=False, allow_nan=False, sort_keys=True)
    return out


def primaries(worker, status):
    own, out = member(worker.vars), {}
    rows = {str(row["id"]): row for row in worker.rows}
    volume, _ = worker.vars.get(f"rec/volumes/{worker.volume}") if worker.volume else (None, 0)
    kind = (volume or {}).get("kind", "local")
    memory = getattr(worker, "_push_sources", None)
    if memory is None:
        worker._push_sources = memory = {}
    seen = set()
    for st in status:
        row = rows.get(str(st["id"]))
        if not own or row is None:
            continue
        ref = ref_of(worker.vars, row)
        assignment = placed(worker.vars, "rec", ref) if ref else None
        if assignment is None:
            continue
        if kind == "edge" and own == assignment["origin"]:
            role = "card"
        elif kind == "backup" and own in assignment["copies"]:
            role = "backup"
        elif kind not in ("edge", "backup", "incidents") and own == assignment["cluster"]:
            role = "primary"
        else:
            continue
        key = str(row["id"])
        seen.add(key)
        source = getattr(worker, "_look", lambda: None)()
        source_row = source.sources() if source is not None else None
        from .recording_books import Unconfirmed, source as source_fact
        try:
            camera = source_fact(source_row, ref).value
        except Unconfirmed:
            camera = None
        # A pull failure stays in this recorder's memory until the source or assignment changes.
        previous = memory.get(key, ((None, None, None),))[0]
        mark = (assignment["rev"], camera.get("live_url") if camera else previous[1],
                camera.get("server") if camera else previous[2])
        if memory.get(key, (None,))[0] != mark:
            memory.pop(key, None)
        failed = st.get("source_unreachable") is True
        if failed:
            memory[key] = (mark, True)
        push = role != "card" and bool((camera or {}).get("push") or memory.get(key))
        value = {"ref": ref, "recording": key, "role": role,
                 "enabled": bool(row.get("enabled") and (not row.get("until") or finite(row["until"]) > worker.wall())),
                 "running": st.get("phase") == "running", "to": recipients(assignment, include_origin=True)}
        for field in ("retention_days", "when", "home"):
            if field in row and row[field] is not None:
                value[field] = row[field]
        coverage = st.get("coverage")
        if coverage is None and hasattr(worker, "our_coverage"):
            spans = worker.our_coverage(row["id"])
            if spans:
                coverage = {"from": spans[0][0], "to": spans[-1][1], "fragments": len(spans)}
        if coverage:
            value["coverage"] = coverage
        if role != "card" and worker.archive_url:
            value["peer_url"] = worker.archive_url
        if (push or (camera or {}).get("polls")) and worker.ingest_url:
            value["ingest"] = [worker.ingest_url]
        if push and worker.ingest_url:
            value["push"] = True
        if role == "primary":
            from .recording_upstream import observation
            from w2cplatform.domain.topology import member_topology
            try:
                topology = member_topology(worker.vars, own)
                if own in topology["star"]:
                    # A star never advertises its own unreachable ingest as a fallback.
                    value.pop("ingest", None)
                    value.pop("push", None)
                    if topology["rev"] <= 0:
                        raise Unconfirmed("primary topology is not confirmed")
                    up, _ = observation(worker.vars, own, ref)
                    value.update(ingest=up.value["urls"], ingest_cluster=up.member, push=True)
            except PARSE_ERRORS:
                value.pop("ingest", None)
                value.pop("push", None)
        out[key] = json.dumps(recording_value(value), ensure_ascii=False, allow_nan=False, sort_keys=True)
    for key in set(memory) - seen:
        memory.pop(key)
    return out
