"""C4: the poll home's recorder publishes addresses; a camera reads one complete fact."""
import json

from w2cplatform.contract import parse_heartbeat
from w2cplatform.domain.memberbook import read as member_book
from w2cplatform.domain.placement import placed
from w2cplatform.domain.topology import poll_home
from .recording_books import Unconfirmed, read, source
from .recording_publication import member

POLLS_PATH = "domain/rec/polls"


def confirmed(items, own, ref, home):
    """A unique, complete address from this camera's currently confirmed home."""
    facts = read(items, ref)
    if facts.missing or len(facts.entries) != 1:
        raise Unconfirmed("poll home is absent, conflicting or incomplete")
    fact = facts.entries[0]
    value = fact.value
    if set(value) != {"ref", "to", "urls"} or value["to"] != [own] \
            or not isinstance(value["urls"], list) or not value["urls"] \
            or any(not isinstance(url, str) or not url for url in value["urls"]):
        raise Unconfirmed("invalid poll home address observation")
    if not isinstance(home, str) or not home or fact.member != home:
        raise Unconfirmed("poll origin is not the confirmed home")
    return fact


def observation(vars_, own, ref):
    try:
        home = poll_home(vars_, own)
        items = member_book(vars_, POLLS_PATH, own)
    except (ValueError, TypeError, KeyError, OverflowError):
        raise Unconfirmed("poll home policy is not confirmed") from None
    return confirmed(items, own, ref, home)


def polls(worker, status):
    """Build an ordinary guarded input after this recorder's heartbeat, without issuing tokens."""
    own = member(worker.vars)
    if not own or not isinstance(worker.ingest_url, str) or not worker.ingest_url:
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
    try:
        items = member_book(worker.vars, "domain/cam/sources", own)
    except (ValueError, TypeError, KeyError, OverflowError):
        return {}
    out = {}
    for ref in sorted(set(items or {}) - {""}):
        try:
            camera = source(items, ref)
            if camera.value.get("polls") is not True or own not in camera.value["to"] \
                    or placed(worker.vars, "rec", ref) is not None or poll_home(worker.vars, camera.member) != own:
                continue
        except (ValueError, TypeError, KeyError, OverflowError):
            continue
        out[ref] = json.dumps({"ref": ref, "to": [camera.member], "urls": urls}, sort_keys=True)
    return out
