"""Explicit initial holder pass for VMS integration sites, before operator writes."""
import math

from w2cplatform.domain import booknames
from w2cplatform.domain.federation import Unreachable
from w2cplatform.domain.members import Members
from w2cplatform.domain.reports import read
from w2cplatform.domain.signer_service import Holder
from w2cplatform.domain.uplink import publication
from w2cplatform.domain.carry import HolderDoor, publication_bytes
from w2cplatform.trust.memberkey import MemberKey, sign_request


def initial_books(fed, signer, wall, publishers, *, objects=None):
    """Admit the fixture's explicit local publishers and collect their actual reports.

`publishers` maps member to its LOCAL (Variables, Objects), never a domain copy.
Existing reports are retained; an unreported recorder-only cluster publishes the
real controller's empty snapshot. No account/name index is seeded or repaired.
"""
    home = fed.domain_holder
    objects = home.objects if objects is None else objects
    keys = {name: MemberKey.load_or_make(vars_) for name, (vars_, _) in publishers.items()}
    members = Members(home.vars, wall, configured=lambda: sorted(publishers), domain=home.name)
    members.settle()
    if home.name in keys:
        key = keys[home.name]
        members.list_holder(home.name, key.pub, key.seal_pub)
    for name, key in keys.items():
        members.set_key(name, key.pub, key.seal_pub, by="fixture enrollment")
        admitted = members.read()["members"][name]
        assert (admitted.get("key"), admitted.get("seal")) == (key.pub, key.seal_pub), name
    door = HolderDoor(home.vars, objects, sealer=getattr(signer, "sealer", None), wall=wall)
    for name, (vars_, published) in publishers.items():
        try:
            read(name, objects)
            continue
        except Unreachable:
            pass
        if not published.list('cam/snapshot/'):
            # A generic empty member report is enough for the holder's pass; no subsystem controller is involved.
            import json
            published.put(f"cam/snapshot/{name}", json.dumps({"cluster": name, "worker": name,
                "ts": wall(), "cameras": []}).encode())
        # Earlier than this fixture's first agent pass, without changing media time.
        sent = math.nextafter(wall(), -math.inf)
        body = publication_bytes(publication(name, vars_, published, sent, key=keys[name]))
        signature = sign_request(keys[name], "POST", "/api/member/" + name, body, sent)
        door.member(name, body, signature)
    holder = Holder(home.vars, objects, signer, fed=fed, wall=wall)
    holder.run_pass()
    for spec, book, _ in booknames.declarations():
        booknames.complete(home.vars, spec.name, book)
    return holder
