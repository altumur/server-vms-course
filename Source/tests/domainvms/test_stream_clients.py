"""C5 cluster account CRUD -> signed member reports -> generic unique book -> agent carry -> RTSP.

Stream-client rows are published by ordinary member workers. RTSP uses its existing adapter fake;
HTTP account operations, domain human tokens, slot publications, member signatures, collection and secret carry are real.
"""
import contextlib
import http.client
import json
import os
import tempfile
import threading
from unittest.mock import patch

from tests.reporting import sync as report_sync
from tests.test_book_runtime import site as book_site
from vms.config import SPEC, LIVE_SPEC, REC_SPEC, AUTO_SPEC, DET_SPEC, DETJOB_SPEC, SURVEY_SPEC
from vms.liveworker import LiveWorker
from vms.live_accounts import ACCOUNTS, BOOK, stream_accounts
from vms.rtspdoor import FakeRTSPServer, RTSPDoor
from w2cplatform import catalog
from w2cplatform.console import Mount, SpecConsole, door_server
from w2cplatform.domain import booknames, bookruntime
from w2cplatform.domain.agent import DomainAgent, DomainPublisher
from w2cplatform.domain.api import ConsoleAPI
from w2cplatform.domain.carry import CarryClient, HolderDoor
from w2cplatform.domain.console import Console
from w2cplatform.domain.declared import guarded
from w2cplatform.domain.federation import DomainDirectory
from w2cplatform.domain.grants import Grant, domain_may, grants_from_items, set_domain_grants
from w2cplatform.domain.identity import IdentityStore
from w2cplatform.domain.members import Members
from w2cplatform.domain.reports import pinned
from w2cplatform.domain.term import DomainHolder
from w2cplatform.sealing import is_sealed
from w2cplatform.spec import SpecController
from w2cplatform.trust.documents import sign
from w2cplatform.trust.tokens import PERSON, verify
from w2cplatform.variables import Forbidden


def request(srv, method, path, token=None, body=None):
    conn = http.client.HTTPConnection('127.0.0.1', srv.server_port, timeout=4)
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer '+token
    try:
        conn.request(method, path, None if body is None else json.dumps(body).encode(), headers)
        reply = conn.getresponse()
        return reply.status, json.loads(reply.read() or b'{}')
    finally:
        conn.close()


class Site:
    def __init__(self, env):
        self.e, self.wall, self.servers = env, env.wall, []
        self.north, self.south = env.fed.clusters['north'], env.fed.clusters['south']
        # All processes of the holder cluster use that cluster's ring, including its gateway.
        env.rings['north'] = env.holder.sealer
        for name, cluster in env.fed.clusters.items():
            env.memberkeys[name].save(cluster.vars, env.rings[name])
        self.north.vars.as_writer('domain', ['domain/*']).delete('domain/members')
        roster = Members(self.north.vars, self.wall, domain='north')
        assert roster.add('south', 'voucher', key=env.memberkeys['south'].pub, seal=env.memberkeys['south'].seal_pub)
        record = sign({'term': 1, 'holder': 'north', 'at': self.wall()}, env.root)
        term = DomainHolder(env.fed, 'north', env.signer, 1, self.wall, objects=self.north.objects, record=record)
        term.claim()
        env.holder.term = term
        assert set(roster.read()['members']) == {'north', 'south'}
        door = HolderDoor(self.north.vars, self.north.objects, env.holder.sealer, self.wall)
        self.agents = {
            name: DomainAgent(name, CarryClient(door, name, env.memberkeys[name], self.wall), cluster.vars,
                              now=self.wall, sealer=env.rings[name], key=env.memberkeys[name],
                              published=cluster.objects, seen_store=cluster.objects)
            for name, cluster in env.fed.clusters.items()}
        self.gateways, self.gateway_doors, self.cameras, self.rtsp, self.rtsp_doors = {}, {}, {}, {}, {}
        self.local_consoles = {}
        self.controllers = {name: SpecController(SPEC, cluster.vars, cluster.objects, wall=self.wall, cluster=name)
                            for name, cluster in env.fed.clusters.items()}
        for ctl in self.controllers.values():
            ctl.publish_snapshot()
        self._agents()
        # A complete initial index comes from accepted empty member reports, never from a hand-written flat book.
        bookruntime.collect(env.holder, LIVE_SPEC, 'stream-accounts')
        assert booknames.complete(self.north.vars, 'live', 'stream-accounts') == {}
        self.ids = IdentityStore(env.signer, self.north.vars, self.north.objects, now=self.wall, sealer=env.holder.sealer)
        self.ids.create_local('anna', 'a-long-password', [])
        self.ids.create_local('boris', 'a-long-password', [])
        set_domain_grants(self.north.vars, [Grant('anna', 'admin', None, 0), Grant('boris', 'view', None, 0)], self.wall())
        env.holder.ids = self.ids
        self.tokens = {name: env.signer.tokens.issue(name, 900, now=self.wall(), kind=PERSON) for name in ('anna', 'boris')}
        for name in env.fed.clusters:
            DomainPublisher(self.north.vars).publish_grants(name, self.people())
        self._agents()
        signer_door = self.serve(env.holder.handler())
        subject = lambda token: verify(token, env.signer.tokens.keyset(), set(), now=self.wall(), kind=PERSON)['sub']
        self.console = Console(DomainDirectory(env.fed), env.holder.view,
                               ConsoleAPI(DomainDirectory(env.fed), verifier=subject),
                               admin=lambda who: domain_may(self.north.vars, who, 'admin', self.wall()),
                               viewer=lambda who: domain_may(self.north.vars, who, 'view', self.wall()),
                               holder_vars=self.north.vars, holder_objects=self.north.objects,
                               signer_url=f'http://127.0.0.1:{signer_door.server_port}')
        self.domain_door = self.serve(self.console.handler())
        env.holder.console_url = f'http://127.0.0.1:{self.domain_door.server_port}'
        env.holder.view.refresh()
        env.holder.publish_view()
        for name, cluster in env.fed.clusters.items():
            ctl = self.controllers[name]
            cam = ctl.create({'name': 'camera '+name, 'ref': '7', 'source': 'driverpack://file/7.mp4'})
            self.cameras[name] = str(cam['id'])
            local_console = Mount(SpecConsole(ctl, wall=self.wall))
            local_door = local_console.serve('127.0.0.1', 0)
            self.servers.append(local_door)
            self.local_consoles[name] = f"http://127.0.0.1:{local_door.server_port}"
            root = tempfile.mkdtemp(prefix='c5-gateway-'+name+'-')
            gateway = LiveWorker('g-1', cluster.vars, cluster.objects, clock=self.wall, wall=self.wall,
                                 resource_root=root, env={'CONSOLE_URL': f'http://127.0.0.1:{local_door.server_port}',
                                                         'W2C_TLS_DIR': os.path.join(root, 'no-kit')})
            gateway.sealer = gateway.account_doors.accounts.sealer = env.rings[name]
            gateway_door = gateway.serve('127.0.0.1', 0)
            self.servers.append(gateway_door)
            self.gateways[name], self.gateway_doors[name] = gateway, gateway_door
            rtsp = FakeRTSPServer()
            self.rtsp[name] = rtsp
            self.rtsp_doors[name] = RTSPDoor(rtsp, lambda cam: 'rtsp://camera-source/'+cam,
                                             cluster.vars, sealer=env.rings[name], wall=self.wall)
        self.carry()

    def serve(self, handler):
        srv = door_server(('127.0.0.1', 0), handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.servers.append(srv)
        return srv

    def people(self):
        return [Grant('anna', 'admin', None, self.wall()+3600), Grant('boris', 'view', None, self.wall()+3600)]

    def _agents(self):
        for agent in self.agents.values():
            assert report_sync(agent), (agent.cluster, agent.keys, agent.reported)
            assert agent.reported == 'reported through the door', (agent.cluster, agent.reported)

    def carry(self):
        self.wall.advance(1)
        for gateway in self.gateways.values():
            gateway.heartbeat_once()
        self._agents()
        got = bookruntime.collect(self.e.holder, LIVE_SPEC, 'stream-accounts')
        assert got.missing == (), got
        self._agents()
        for rtsp in self.rtsp_doors.values():
            rtsp.sync()
        return got

    def call(self, method, path='/live/accounts', *, cluster='north', who='anna', body=None):
        return request(self.gateway_doors[cluster], method, path, self.tokens.get(who), body)

    def domain(self, method, path, body=None, who='anna'):
        return request(self.domain_door, method, path, self.tokens.get(who), body)

    def grants(self, cluster, *names):
        lines = [{'subject': g.subject, 'cap': g.capability, 'scope': '*', 'until': g.valid_until} for g in self.people()]
        lines += [{'subject': name, 'cap': 'view', 'scope': 'unit:cam/'+self.cameras[cluster], 'until': self.wall()+3600}
                  for name in names]
        status, answer = self.domain('PUT', '/domain/grants/'+cluster, {'lines': lines})
        assert status == 200, (status, answer)

    def denied_play(self, member, name, password):
        try:
            self.rtsp[member].play(name, password, self.cameras[member])
        except PermissionError:
            return
        raise AssertionError('RTSP accepted an account/password that should no longer authorize play')

    def close(self):
        for srv in reversed(self.servers):
            srv.shutdown()
            srv.server_close()


@contextlib.contextmanager
def site():
    with book_site() as env:
        specs = (SPEC, LIVE_SPEC, REC_SPEC, AUTO_SPEC, DET_SPEC, DETJOB_SPEC, SURVEY_SPEC)
        with patch.object(catalog, '_loaded', {s.name: s for s in specs}), patch.object(catalog, '_derived', {}):
            s = Site(env)
            try:
                with patch.dict(os.environ, {'CLUSTERS': ','.join(name+'='+url for name, url in s.local_consoles.items()),
                                             'W2C_TLS_DIR': tempfile.mkdtemp(prefix='c5-no-console-kit-'),
                                             'W2C_ROLE': 'console'}):
                    yield s
            finally:
                s.close()


def test_cluster_http_crud_is_published_signed_carried_sealed_and_rtsp_observes_disable_and_password_reset():
    with site() as s:
        assert s.call('POST', body={'name': 'wall'}, who='boris')[0] == 403
        assert s.call('POST', body={'name': 'wall'}, who=None)[0] == 401
        status, created = s.call('POST', body={'name': 'wall'})
        assert status == 200 and set(created) == {'account', 'password'}, (status, created)
        password = created['password']
        row = s.north.vars.get(ACCOUNTS+'wall')[0]
        assert is_sealed(row['password_secret']) and password not in json.dumps(row)
        assert s.call('GET', who='boris')[1]['accounts'][0]['by'] == 'anna'
        s.grants('south', 'wall')
        s.carry()
        signed = pinned('north', s.north.objects)
        assert signed.mark['signature'] and password not in signed.raw.decode()
        assert password not in json.dumps(s.north.vars.get(BOOK+'/south')[0])
        assert password not in json.dumps(s.south.vars.get(BOOK)[0])
        assert stream_accounts(s.south.vars, 'south', s.e.rings['north']) == {}
        assert s.rtsp['south'].play('wall', password, s.cameras['south'])
        status, reset = s.call('POST', '/live/accounts/wall/password')
        assert status == 200 and reset['password'] != password
        s.carry()
        s.denied_play('south', 'wall', password)
        assert s.rtsp['south'].play('wall', reset['password'], s.cameras['south'])
        assert s.call('PUT', '/live/accounts/wall', body={'disabled': True}) == (200, {'account': 'wall', 'disabled': True})
        s.carry()
        s.denied_play('south', 'wall', reset['password'])
        assert s.call('PUT', '/live/accounts/wall', body={'disabled': False})[0] == 200
        s.carry()
        assert s.rtsp['south'].play('wall', reset['password'], s.cameras['south'])


def test_grant_revocation_and_delete_use_domain_console_then_remove_carried_rtsp_access_and_release_the_name():
    with site() as s:
        password = s.call('POST', body={'name': 'wall'})[1]['password']
        s.grants('south', 'wall')
        s.carry()
        assert s.rtsp['south'].play('wall', password, s.cameras['south'])
        s.grants('south')
        s._agents()  # final delivery rechecks current grants even before the next collection
        s.rtsp_doors['south'].sync()
        s.denied_play('south', 'wall', password)
        s.grants('south', 'wall')
        s.carry()
        assert s.rtsp['south'].play('wall', password, s.cameras['south'])
        assert s.call('DELETE', '/live/accounts/wall', who='boris')[0] == 403
        status, removed = s.call('DELETE', '/live/accounts/wall')
        assert (status, removed) == (200, {'account': 'wall', 'deleted': True, 'grants_changed': ['south']})
        assert all(g.subject != 'wall' for g in grants_from_items(s.north.vars.get('domain/grants/south')[0]))
        assert domain_may(s.north.vars, 'anna', 'admin', s.wall())
        assert s.north.vars.get(ACCOUNTS+'wall')[0] is None
        s.carry()
        s.denied_play('south', 'wall', password)
        assert 'wall' not in booknames.complete(s.north.vars, 'live', 'stream-accounts')
        assert s.domain('POST', '/domain/users', {'name': 'wall', 'password': 'a-long-password', 'roles': []})[0] == 200


class AsDaemon:
    """Exercise the committed domainconsole role, whose name-index reads grant no account secret reads."""
    def __init__(self, inner):
        from w2cplatform.storemachine import Rights
        import w2cplatform
        self.inner = inner
        source = os.path.dirname(os.path.dirname(w2cplatform.__file__))
        self.rights = Rights.load(os.path.join(source, 'deploy', 'cluster', 'configstore-rights.json'))

    def check(self, action, path):
        if not self.rights.allows('domainconsole', action, path):
            raise Forbidden('domainconsole may not '+action+' '+path)

    def get(self, path):
        self.check('read', path)
        return self.inner.get(path)

    def put(self, path, items, cas=None, **kwargs):
        self.check('write', path)
        return self.inner.put(path, items, cas, **kwargs)

    def delete(self, path, cas=None, **kwargs):
        self.check('delete', path)
        return self.inner.delete(path, cas, **kwargs)

    def list(self, prefix):
        return self.inner.list(prefix)


def test_collected_name_index_guards_users_and_grant_ceiling_without_reading_secret_accounts():
    with site() as s:
        assert s.call('POST', body={'name': 'anna'})[0] == 409
        assert s.call('POST', body={'name': 'wall'})[0] == 200
        s.carry()
        console_vars = AsDaemon(s.north.vars)
        try:
            console_vars.get(ACCOUNTS+'wall')
        except Forbidden:
            pass
        else:
            raise AssertionError('committed domainconsole role can read the local account password')
        s.console.holder_vars = guarded(console_vars)
        index = booknames.complete(s.north.vars, 'live', 'stream-accounts')
        assert index['wall'] == ('north',)
        assert 'password' not in json.dumps(s.north.vars.get('domain/names/live/stream-accounts')[0])
        assert s.domain('POST', '/domain/users', {'name': 'wall', 'password': 'a-long-password', 'roles': []})[0] == 409
        status, answer = s.domain('PUT', '/domain/grants/south', {'lines': [{'subject': 'wall', 'cap': 'edit', 'scope': '*'}]})
        assert status == 400 and 'view' in answer['detail'], (status, answer)
        assert s.domain('PUT', '/domain/grants/south', {'lines': [{'subject': 'anna', 'cap': 'admin', 'scope': '*'}]})[0] == 200


def test_two_cluster_creators_can_race_but_unique_collection_delivers_neither_and_indexes_both_owners():
    with site() as s:
        # No report containing the first new account has reached the holder before the second local create.
        status, north = s.call('POST', cluster='north', body={'name': 'shared'})
        assert status == 200, (status, north)
        status, south = s.call('POST', cluster='south', body={'name': 'shared'})
        assert status == 200, (status, south)
        assert north['password'] != south['password']
        s.grants('north', 'shared')
        s.grants('south', 'shared')
        s.carry()
        assert booknames.complete(s.north.vars, 'live', 'stream-accounts')['shared'] == ('north', 'south')
        for member, password in (('north', north['password']), ('south', south['password'])):
            cluster = s.e.fed.clusters[member]
            assert stream_accounts(cluster.vars, member, s.e.rings[member]) == {}
            s.denied_play(member, 'shared', password)
        assert s.domain('POST', '/domain/users', {'name': 'shared', 'password': 'a-long-password', 'roles': []})[0] == 409
        status, answer = s.domain('PUT', '/domain/grants/south', {'lines': [{'subject': 'shared', 'cap': 'edit', 'scope': '*'}]})
        assert status == 400 and 'view' in answer['detail'], (status, answer)
