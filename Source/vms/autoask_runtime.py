"""Hosts of the same scenario executor: ordinary worker and embedded member."""
from __future__ import annotations

import hashlib
import logging
import uuid

from w2cplatform.contract import parse_heartbeat, read_slot
from w2cplatform.domain.shared import SharedView
from w2cplatform.rows import PARSE_ERRORS
from w2cplatform.trust.jcs import jcs

from .autoask import Asker, Executor, VALID, contribution
from .recording_books import Unconfirmed
from .role_tokens import RoleTokens

log = logging.getLogger(__name__)


def elected(worker):
    if not worker.name or not worker.writing_allowed or worker.seeking is not None:
        return False
    key = worker.sub.slot_key(worker.name)
    row, _ = worker.vars.get(key)
    slot = read_slot(key, worker.name, row)
    if slot is None or slot.holder != worker.instance or slot.released or slot.until <= worker.wall():
        return False
    names = []
    for key in worker.objects.list('auto/heartbeats/'):
        hb = parse_heartbeat(key, worker.objects.get(key))
        if hb is not None and not hb.extra.get('fenced') and worker.eyes.fresh(key, hb.token, 45):
            names.append(hb.worker)
    return bool(names) and min(names) == worker.name


class WorkerScenarios:
    def __init__(self, worker, dial, tokens):
        self.worker, self.dial, self.tokens = worker, dial, tokens
        self.shared = SharedView(worker.vars, worker.objects, worker.wall)
        self.executor = Executor(self.shared, self._asker, worker.wall)
        self.seen = {}
        self.watched = set()

    def _dial(self, url):
        # A token request may have blocked while this process lost its slot.
        if not elected(self.worker):
            raise Unconfirmed('ask executor is no longer active')
        return self.dial(url)

    def _asker(self, by):
        if not elected(self.worker):
            raise Unconfirmed('ask executor is not active')
        return Asker(by, self.worker.vars, self._dial, self.tokens, self.worker.wall)

    def step(self, now):
        from .config import SPEC
        worker = self.worker
        valid = self.executor.refresh()
        self.watched = set()
        if not valid or not elected(worker):
            return []
        local = {}
        duplicate = set()
        for key in worker.vars.list(SPEC.sub.config(SPEC.rows, '')):
            raw, _ = worker.vars.get(key)
            if not raw or raw.get('deleted') == 'true':
                continue
            row = SPEC.row(raw)
            ref = str(row.get(SPEC.domain.ref) or '')
            if ref and row.get('enabled', True):
                if ref in local:
                    duplicate.add(ref)
                local[ref] = str(row['id'])
        needed = {}
        for item in valid:
            ref, kind = item['when']['camera'], item['when']['kind']
            if ref in duplicate:
                self.executor.refused[item['name']] = 'trigger identity is not unique locally'
            elif ref in local:
                key = ref, kind
                needed[key] = max(needed.get(key, 0), item['then'].get('within', VALID))
                self.watched.add(('cam', kind, local[ref]))
        self.seen = {key: until for key, until in self.seen.items() if until > now}
        result = []
        for (ref, kind), within in sorted(needed.items()):
            answer = worker.index.query(max(0, now-within), now, subsystem='cam', kind=kind,
                                        unit='cam/'+local[ref], limit=worker.PER_KIND)
            if answer.get('truncated') or answer.get('incomplete'):
                for item in valid:
                    if item['when'] == {'camera':ref,'kind':kind}:
                        self.executor.refused[item['name']] = 'trigger event window is incomplete'
                continue
            for event in answer.get('events', []):
                if event.get('fenced') or event.get('epoch_is') not in (None, 'current'):
                    continue
                identity = ref, kind, hashlib.sha256(jcs(event)).digest()
                if identity in self.seen:
                    continue
                # Mark before attempting: an unresolved ask must not be repeated on each pass.
                self.seen[identity] = now+within
                at = event.get('occurred', event.get('t', now))
                result.extend(self.executor.on_event(ref, kind, {**event,'ts':at},refresh=False))
        return result

    def publish(self):
        from .recording_publication import publish
        try:
            publish(self.worker, 'asks', contribution(self.worker, self.shared.settings()))
        except (OSError, *PARSE_ERRORS):
            log.warning('%s: ask contribution unavailable', self.worker.name)


class AgentDoor:
    """An embedded executor has the agent in process, with a fixed executor role."""
    def __init__(self, agent):
        self.agent = agent

    def request(self, kind, ref, by=None):
        if kind != 'ask' or not isinstance(by, str) or not by:
            raise Unconfirmed('invalid embedded ask request')
        request_id = uuid.uuid4().hex
        reply = self.agent.request_token('cam', kind, ref, 'autoworker', by, request_id)
        if not isinstance(reply, dict) or set(reply) != {'request_id','token','exp'} \
                or reply['request_id'] != request_id:
            raise Unconfirmed('embedded ask reply is not correlated')
        return reply


class Embedded:
    def __init__(self, serial, vars_, objects, agent, dial, wall, steady):
        self.serial = str(serial)
        tokens = RoleTokens('autoworker', AgentDoor(agent), clock=steady)
        asker = Asker(self.serial, vars_, dial, tokens, wall)
        self.executor = Executor(SharedView(vars_,objects,wall),lambda _:asker,wall)

    def on_event(self, kind, event=None):
        return self.executor.on_event(self.serial,kind,event)

    def heartbeat(self):
        return self.executor.heartbeat()
