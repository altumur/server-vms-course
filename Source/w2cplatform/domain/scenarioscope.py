"""Derive a token's document scope from declared paths and accepted member facts."""
from __future__ import annotations

import hashlib

from w2cplatform.canonical import parse_json
from w2cplatform.rows import PARSE_ERRORS
from w2cplatform.trust.documents import NotTaken, verify
from w2cplatform.trust.jcs import jcs
from .carry import Refused
from .federation import Unreachable, _a_shard
from .reports import pinned
from .steps import one_pass


def field(value, path):
    for part in path.split('.'):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def references(door, spec, member):
    """Only the complete generation accepted by the holder, never mutable live data."""
    if not spec.domain.ref or door.objects is None:
        raise Refused(403, 'scope has no accepted unit report')
    try:
        result = set()
        objects = pinned(member, door.objects).document()['objects']
        for key, shard in objects.items():
            if not key.startswith(spec.name + '/snapshot/'):
                continue
            if not isinstance(shard, dict) or not isinstance(shard.get(spec.rows), list):
                raise ValueError()
            _a_shard(shard, spec.rows)
            for row in shard[spec.rows]:
                value = row.get(spec.domain.ref)
                if type(value) in (str, int) and str(value):
                    result.add(str(value))
        return result
    except (Unreachable, *PARSE_ERRORS):
        raise Refused(403, 'scope has no complete accepted unit report') from None


def _items(door, binding):
    from .agent import ClusterTrust, Untrusted
    from .shared import POINTER
    try:
        pointer, _ = door.vars.get(POINTER)
        raw = door.objects.get(pointer['object']) if pointer else None
        if raw is None or hashlib.sha256(raw).hexdigest() != pointer['sha256']:
            raise ValueError()
        doc = verify(parse_json(raw), ClusterTrust(door.vars).keyset(), door.wall())
        if doc['rev'] != int(pointer['rev']) or doc['term'] != int(pointer['term']):
            raise ValueError()
        value = doc['settings']['shared'][binding['doc']]
        items = field(value, binding['items'])
        if not isinstance(items, list):
            raise ValueError()
        return items
    except (NotTaken, Untrusted, *PARSE_ERRORS):
        raise Refused(403, 'scope has no verified shared document') from None


@one_pass()
def claims(door, spec, member, ref, by, binding):
    from .members import Members
    from .placement import read
    from .topology import TOPOLOGY, poll_home
    admitted = Members(door.vars).read()['members']
    from types import SimpleNamespace
    policy_rows = {}
    def policy_get(key):
        if key not in policy_rows:
            policy_rows[key] = door.vars.get(key)
        return policy_rows[key]
    policy = SimpleNamespace(get=policy_get)
    try:
        # The same strict authoritative policy as unit scope, including holder confirmation.
        poll_home(policy, member, authoritative=True)
        row, _ = policy.get(TOPOLOGY)
        topology = parse_json(row['doc']) if row else {}
        via, centre = topology.get('via', {}), topology.get('centre')
        if any(n not in admitted for n in ([centre] if centre else []) + list(via) + list(via.values()) + topology.get('star', [])):
            raise ValueError()
    except PARSE_ERRORS:
        raise Refused(409, 'scope has no confirmed topology') from None

    # A forwarder may ask for the original reporter behind it; no other member's unit grants authority.
    reporters = [member] + sorted(n for n, relay in via.items() if relay == member)
    owners = []
    for reporter in reporters:
        if by in references(door, spec, reporter):
            owners.append(reporter)
    if len(owners) != 1:
        raise Refused(403, 'the member does not uniquely report this trigger')
    source = owners[0]

    items = _items(door, binding)
    names = {}
    for item in items:
        name = field(item, binding['name'])
        if isinstance(name, str) and name:
            names[name] = names.get(name, 0) + 1
    actions = {}
    for item in items:
        name = field(item, binding['name'])
        enabled = field(item, binding['enabled'])
        if not isinstance(name, str) or not name or names[name] != 1 or enabled is not None and type(enabled) is not bool:
            continue
        if enabled is False or field(item, binding['target']) != ref or field(item, binding['trigger']) != by:
            continue
        act = field(item, binding['act'])
        if isinstance(act, dict):
            try:
                actions[jcs(act)] = act
            except PARSE_ERRORS:
                raise Refused(403, 'scope has an invalid action') from None
    if not actions:
        raise Refused(403, 'no enabled document item grants this request')

    try:
        placed = read(door.vars, binding['placement'], ref) if binding.get('placement') else None
        if placed:
            links = [placed['cluster'], *placed['copies'], *([placed['origin']] if placed['origin'] else [])]
            if any(n not in admitted for n in links):
                raise ValueError()
            home = centre if placed['cluster'] in topology.get('star', []) else placed['cluster']
        else:
            target_owners = [n for n in sorted(admitted) if ref in references(door, spec, n)]
            if len(target_owners) != 1:
                raise Refused(403, 'target has no unique accepted home')
            home = poll_home(policy, target_owners[0], authoritative=True)
    except PARSE_ERRORS:
        raise Refused(403, 'target assignment is unreadable') from None
    if not home or home not in admitted:
        raise Refused(409, 'target has no admitted home')

    extra = {binding['ref_claim']: ref, binding['trigger_claim']: by,
             binding['acts_claim']: [actions[key] for key in sorted(actions)]}
    relay = via.get(source)
    if source != member:                       # the authenticated relay's upward request
        if relay != member or not centre:
            raise Refused(409, 'relay has no confirmed centre')
        audience = [centre]
    elif relay and relay != home:
        if not centre:
            raise Refused(409, 'relay has no confirmed centre')
        audience = [relay]
        extra[binding['up_claim']] = centre
    elif relay == home:
        audience = [home]
    else:
        audience = sorted({home, *([centre] if centre and centre != home else [])})
    if any(n not in admitted for n in audience):
        raise Refused(403, 'scope has no admitted audience')
    extra[binding['audience_claim']] = audience
    return extra
