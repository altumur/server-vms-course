"""Shared cross-cluster scenarios executed where their trigger events originate."""
from __future__ import annotations

import math

from w2cplatform.rows import PARSE_ERRORS
from .recording_books import Unconfirmed

VALID = 30.0
RATE = 6


class NoAskRoad(Unconfirmed):
    """The verified ask book has no road for this target."""



def scenarios(settings):
    """Current valid entries and non-secret refusal reasons (ADR-0074 C6)."""
    held = settings.get('shared', {}) if isinstance(settings, dict) else None
    auto = held.get('auto', {}) if isinstance(held, dict) else None
    items = auto.get('scenarios', []) if isinstance(auto, dict) else None
    if not isinstance(items, list):
        return [], {'#1': 'scenarios is not a list'}
    names = {}
    for item in items:
        name = item.get('name') if isinstance(item, dict) else None
        if isinstance(name, str) and name:
            names[name] = names.get(name, 0) + 1
    valid, refused = [], {}
    from .ingest import ASK_DEADLINE_MAX
    for index, item in enumerate(items, 1):
        name = item.get('name') if isinstance(item, dict) else None
        named = isinstance(name, str) and bool(name)
        key = name if named and names[name] == 1 else f'#{index}'
        if not named:
            refused[key] = 'name is required'
            continue
        if names[name] != 1:
            refused[key] = 'name is repeated'
            continue
        if set(item) - {'name', 'when', 'then', 'enabled', 'rate_per_minute'}:
            refused[key] = 'unknown scenario field'
            continue
        when, then = item.get('when'), item.get('then')
        if not isinstance(when, dict) or set(when) != {'camera', 'kind'} \
                or any(not isinstance(v, str) or not v for v in when.values()):
            refused[key] = 'invalid trigger'
            continue
        if not isinstance(then, dict) or set(then) - {'camera', 'action', 'arg', 'within'} \
                or any(not isinstance(then.get(k), str) or not then[k] for k in ('camera', 'action')) \
                or 'arg' in then and type(then['arg']) not in (int, str):
            refused[key] = 'invalid action'
            continue
        within = then.get('within', VALID)
        if type(within) not in (int, float) or not 0 < within <= ASK_DEADLINE_MAX:
            refused[key] = 'invalid deadline'
            continue
        if type(item.get('enabled', True)) is not bool:
            refused[key] = 'invalid enabled flag'
            continue
        rate = item.get('rate_per_minute', RATE)
        if type(rate) is not int or rate < 0:
            refused[key] = 'invalid rate'
            continue
        if item.get('enabled', True):
            valid.append(item)
    return valid, refused


class Executor:
    """A cluster event reader or an embedded executor uses the same logic.

    ``shared`` supplies verified settings; ``asker(ref)`` is the caller's ordinary
    member-book/role-door requester. The executor never sees a signing key.
    Local ownership and sole active execution are established by its host.
    """
    def __init__(self, shared, asker, clock):
        self.shared, self.asker, self.clock = shared, asker, clock
        self.refused = {}
        self.fired = {}
        self._valid = []

    def refresh(self):
        valid, self.refused = scenarios(self.shared.settings())
        present = {item['name'] for item in valid}
        for gone in set(self.fired) - present:
            self.fired.pop(gone, None)
        self._valid = valid
        return valid

    def heartbeat(self):
        return {'refused': dict(self.refused)} if self.refused else {}

    def on_event(self, serial, kind, event=None, *, refresh=True):
        valid = self.refresh() if refresh else self._valid
        if event and event.get('repeats'):
            return []
        now = self.clock()
        try:
            at = event.get('ts', now) if event else now
            if type(at) not in (int, float) or not math.isfinite(at):
                return []
        except PARSE_ERRORS:
            return []
        done = []
        for item in valid:
            when, then = item['when'], dict(item['then'])
            if when['camera'] != str(serial) or when['kind'] != kind or then['camera'] == str(serial):
                continue
            target, within = then['camera'], then.get('within', VALID)
            outcome = {'target': target, 'action': then}
            if at + within <= now:
                done.append({**outcome, 'state': 'seen after its deadline: not asked'})
                continue
            name, cap = item['name'], item.get('rate_per_minute') or RATE
            recent = self.fired[name] = [t for t in self.fired.get(name, []) if now - t < 60.0]
            if len(recent) >= cap:
                done.append({**outcome, 'state': f'over its ceiling of {cap}/min: not asked'})
                continue
            recent.append(now)
            from .ingest import Refused
            from w2cplatform.domain.federation import Unreachable
            from .recording_books import Unconfirmed
            try:
                left = self.asker(str(serial)).ask(target, then, at + within - now)
            except NoAskRoad:
                done.append({**outcome, 'state': f'the book of asks names no door for {target}: not asked'})
                continue
            except (Refused, Unreachable, Unconfirmed, OSError):
                # Refusals must not serialize tokens, URLs or arbitrary action contents into the pulse.
                self.refused[name] = 'ask transport or authority refused'
                done.append({**outcome, 'state': 'not asked'})
                continue
            if left is None:
                done.append({**outcome, 'state': 'no ingest answered: not asked'})
            else:
                ingest, aid = left
                done.append({**outcome, 'state': 'asked', 'ingest': ingest, 'ask': aid, 'deadline': at + within})
        return done


BOOK = 'domain/auto/asks'


def contribution(worker, settings, *, elect=True):
    """Advertise local ingests; ordinary workers elect, an embedded process is sole."""
    import json
    from w2cplatform.contract import parse_heartbeat
    from w2cplatform.domain.memberbook import members, read as member_book
    from w2cplatform.domain.placement import placed
    from w2cplatform.domain.topology import member_topology, poll_home
    from w2cplatform.trust.jcs import jcs
    from .recording_books import source, Unconfirmed
    from .recording_publication import member

    own = member(worker.vars)
    if not own or not worker.name:
        return {}
    live, urls = [], set()
    for sub in (('auto', 'rec') if elect else ('rec',)):
        for key in worker.objects.list(sub + '/heartbeats/'):
            hb = parse_heartbeat(key, worker.objects.get(key))
            if hb is None or not worker.eyes.fresh(key, hb.token, 45):
                continue
            if sub == 'auto':
                live.append(hb.worker)
            elif isinstance(hb.extra.get('ingest'), str) and hb.extra['ingest']:
                urls.add(hb.extra['ingest'])
    if not urls or elect and (not live or min(live) != worker.name):
        return {}
    try:
        topology = member_topology(worker.vars, own)
        roster = members(worker.vars, own)
        centre, via = topology['centre'], topology['via']
        if own not in roster or any(n not in roster for n in
                ([centre] if centre else []) + list(via) + list(via.values()) + topology['star']):
            return {}
    except PARSE_ERRORS:
        return {}
    valid, _ = scenarios(settings)
    grouped = {}
    for item in valid:
        target, trigger = item['then']['camera'], item['when']['camera']
        try:
            assignment = placed(worker.vars, 'rec', target)
            if assignment:
                home = assignment['cluster']
                if home in topology['star']:
                    home = centre
            elif own == centre:
                # The centre is always on the path, including an unassigned target.
                home = centre
            else:
                try:
                    camera = source(member_book(worker.vars, 'domain/cam/sources', own), target)
                    home = poll_home(worker.vars, camera.member)
                except Unconfirmed:
                    # A trigger's relay need not receive the target's source book.
                    # It can advertise an upward road; the signer independently
                    # decides whether this particular pair may use that hop.
                    if not centre or own not in via.values():
                        continue
                    home = None
            if home is not None and home not in roster:
                continue
        except (Unconfirmed, *PARSE_ERRORS):
            continue
        up = None
        if own in (home, centre):
            recipients = list(roster)
        else:
            recipients = sorted(n for n, relay in via.items() if relay == own)
            if not centre or not recipients:
                continue
            up = centre
        row = grouped.setdefault(target, {'target':target, 'by':set(), 'acts':{},
                                          'urls':sorted(urls), 'to':recipients})
        row['by'].add(trigger)
        row['acts'][jcs(item['then'])] = item['then']
        if up:
            row['up'] = up
    result = {}
    for target, row in sorted(grouped.items()):
        row['by'] = sorted(row['by'])
        row['acts'] = [row['acts'][key] for key in sorted(row['acts'])]
        result[target] = json.dumps(row, ensure_ascii=False, allow_nan=False, sort_keys=True)
    return result


def roads(items, own, target, by, action=None):
    """Read collected observations, refusing partial or malformed generations."""
    from .recording_books import read, Unconfirmed
    from w2cplatform.trust.jcs import jcs
    facts = read(items, target, value_key='target')
    if facts.missing:
        raise Unconfirmed('ask book is incomplete')
    selected = []
    for fact in facts.entries:
        value = fact.value
        if set(value) - {'target', 'by', 'acts', 'urls', 'up', 'to'} \
                or {'target', 'by', 'acts', 'urls', 'to'} - set(value):
            raise Unconfirmed('invalid ask observation')
        for field in ('by', 'urls', 'to'):
            names = value[field]
            if not isinstance(names, list) or not names or any(not isinstance(n, str) or not n for n in names) \
                    or len(set(names)) != len(names):
                raise Unconfirmed('invalid ask observation list')
        if not isinstance(value['acts'], list) or not value['acts'] \
                or any(not isinstance(act, dict) or act.get('camera') != target for act in value['acts']) \
                or 'up' in value and (not isinstance(value['up'], str) or not value['up']):
            raise Unconfirmed('invalid ask authority observation')
        if own not in value['to'] or by not in value['by']:
            continue
        if action is not None and not any(jcs(action) == jcs(act) for act in value['acts']):
            continue
        selected.append(fact)
    return tuple(selected)


class Asker:
    """An ordinary executor requests a RAM token on its own role's agent socket."""
    def __init__(self, serial, flash, dial, tokens=None, clock=None, env=None):
        import time
        from .role_tokens import RoleTokens
        self.serial, self.flash, self.dial = str(serial), flash, dial
        self.clock = clock or time.time
        self.tokens = tokens if tokens is not None else RoleTokens('autoworker', env=env)

    def _roads(self, target, action=None):
        from w2cplatform.domain.memberbook import read as member_book
        from .recording_publication import member
        from .recording_books import Unconfirmed
        try:
            own = member(self.flash)
            if not own:
                raise Unconfirmed('ask executor has no member identity')
            return own, roads(member_book(self.flash, BOOK, own), own, target, self.serial, action)
        except PARSE_ERRORS:
            raise Unconfirmed('ask book or member identity is invalid') from None

    def ask(self, target, action, within):
        return self.ask_until(target, action, self.clock() + within)

    def ask_until(self, target, action, deadline):
        """Carry an existing ask without restarting its deadline at this hop."""
        from w2cplatform.domain.agent import ClusterTrust, Untrusted
        from w2cplatform.domain.topology import member_topology
        from w2cplatform.domain.placement import placed
        from w2cplatform.trust.tokens import verify, TokenError
        from w2cplatform.trust.jcs import jcs
        from w2cplatform.domain.federation import Unreachable
        from .recording_books import Unconfirmed
        try:
            valid_deadline = type(deadline) in (int, float) and math.isfinite(deadline) and deadline > self.clock()
        except OverflowError:
            valid_deadline = False
        if not valid_deadline:
            raise Unconfirmed('ask deadline has passed or is invalid')
        own, facts = self._roads(target, action)
        if not facts:
            raise NoAskRoad('ask has no confirmed road')
        def current_scope(member, observations):
            return (member, jcs(action),
                    jcs([{'member': f.member, 'item': f.item, 'value': f.value} for f in observations]),
                    jcs(member_topology(self.flash, member)), jcs(placed(self.flash, 'rec', target)))
        try:
            scope = current_scope(own, facts)
        except PARSE_ERRORS:
            raise Unconfirmed('ask topology or assignment is invalid') from None
        token = self.tokens.get('ask', target, scope, by=self.serial)
        try:
            current, latest = self._roads(target, action)
            if current_scope(current, latest) != scope:
                raise Unconfirmed('ask road changed during token request')
        except (OSError, *PARSE_ERRORS):
            self.tokens.forget('ask', target, scope, by=self.serial)
            raise Unconfirmed('ask road changed during token request') from None
        trust = ClusterTrust(self.flash)
        try:
            keys = trust.keyset()
            if keys is None:
                raise Unconfirmed('ask has no trusted key set')
            at = self.tokens.verification_time('ask', target, scope, token, by=self.serial)
            claims = verify(token, keys, trust.revoked(), now=at, kind='ask')
            if claims.get('sub') != own or claims.get('ref') != target or claims.get('by') != self.serial \
                    or not isinstance(claims.get('aud'), list) or not claims['aud'] \
                    or not isinstance(claims.get('acts'), list) \
                    or not any(jcs(action) == jcs(act) for act in claims['acts']):
                raise Unconfirmed('role token does not authorize this ask')
        except (TokenError, Untrusted, *PARSE_ERRORS):
            raise Unconfirmed('ask role token could not be verified') from None
        if self.clock() >= deadline:
            raise Unconfirmed('ask deadline passed during token request')
        # Authority comes from the signer; a book never adds a token audience or an upward hop.
        for fact in facts:
            if fact.member not in claims['aud'] or fact.value.get('up') != claims.get('up'):
                continue
            for url in fact.value['urls']:
                if self.clock() >= deadline:
                    raise Unconfirmed('ask deadline passed while trying its roads')
                try:
                    ingest = self.dial(url)
                    aid = ingest.ask(token, target, action, deadline, camera_now=self.clock())
                    return ingest, aid
                except Unreachable:
                    continue
        return None

    def outcome(self, target, aid, deadline):
        from .ingest import ANSWER_GRACE
        from .recording_books import Unconfirmed
        from w2cplatform.domain.federation import Unreachable
        try:
            _, facts = self._roads(target)
        except Unconfirmed:
            facts = ()
        for fact in facts:
            for url in fact.value['urls']:
                try:
                    out = self.dial(url).ask_outcome(target, aid)
                except Unreachable:
                    continue
                if out is not None:
                    return out
        if self.clock() > deadline + ANSWER_GRACE:
            return 'unknown: no ingest knows this ask'
        return None
