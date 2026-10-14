"""The centre's ordinary recorder publishes its address; relays read C3 facts."""
import json

from w2cplatform.contract import parse_heartbeat
from w2cplatform.domain.memberbook import read as member_book
from w2cplatform.domain.placement import placed
from w2cplatform.domain.topology import member_topology, poll_home
from .recording_books import Unconfirmed, read, source
from .recording_publication import member


def confirmed(items, own, ref, centre):
    """One complete upstream observation for this recipient and confirmed centre."""
    facts = read(items, ref)
    if facts.missing or len(facts.entries) != 1:
        raise Unconfirmed("upstream is absent, conflicting or incomplete")
    fact = facts.entries[0]
    value = fact.value
    if set(value) != {"ref", "to", "urls"} or not isinstance(value["to"], list) \
            or value["to"] != [own] or not isinstance(value["urls"], list) or not value["urls"] \
            or any(not isinstance(url, str) or not url for url in value["urls"]):
        raise Unconfirmed("invalid upstream address observation")
    if not isinstance(centre, str) or not centre or fact.member != centre:
        raise Unconfirmed("upstream origin is not the confirmed centre")
    return fact


def observation(vars_, own, ref):
    topology = member_topology(vars_, own)
    if topology["rev"] <= 0:
        raise Unconfirmed("upstream topology is not confirmed")
    return confirmed(member_book(vars_, "domain/rec/upstream", own), own, ref, topology["centre"]), topology


def upstream(worker, status):
    own = member(worker.vars)
    if not own or not worker.ingest_url:
        return {}
    try:
        topology = member_topology(worker.vars, own)
    except (ValueError, TypeError, KeyError, OverflowError):
        return {}
    if topology["rev"] <= 0 or topology["centre"] != own:
        return {}
    live = []
    for key in worker.objects.list("rec/heartbeats/"):
        hb = parse_heartbeat(key, worker.objects.get(key))
        if hb is None:
            continue
        url = hb.extra.get("ingest")
        if isinstance(url, str) and url and worker.eyes.fresh(key, hb.token, 45):
            live.append((hb.worker, url))
    if not live or worker.name != min(name for name, _ in live):
        return {}
    urls = sorted(set(url for _, url in live))
    refs = set()
    for prefix in ("domain/placed/rec/", "domain/placement/rec/"):
        refs.update(key[len(prefix):] for key in worker.vars.list(prefix))
    out = {}
    for ref in sorted(refs):
        try:
            assignment = placed(worker.vars, "rec", ref)
        except ValueError:
            continue
        if assignment and assignment["cluster"] != own:
            out[ref] = json.dumps({"ref": ref, "to": [assignment["cluster"]], "urls": urls}, sort_keys=True)
    sources = member_book(worker.vars, "domain/cam/sources", own)
    for ref in sorted((sources or {}).keys() - {""}):
        try:
            if placed(worker.vars, "rec", ref) is not None:
                continue
            fact = source(sources, ref)
            home = poll_home(worker.vars, fact.member)
            if fact.value.get("polls") is True and own in fact.value["to"] and home != own:
                out[ref] = json.dumps({"ref": ref, "to": [home], "urls": urls}, sort_keys=True)
        except (ValueError, TypeError, KeyError, OverflowError):
            continue
    return out
