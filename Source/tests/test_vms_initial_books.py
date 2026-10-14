"""The VMS names collector protects bootstrap writes until all members report."""

def test_a_fresh_holder_requires_complete_signed_reports_before_its_first_grant():
    from vms.domainpart.device import DeviceCluster
    from w2cplatform.cluster.variables import FakeVariables
    from w2cplatform.domain import booknames, declared
    from w2cplatform.domain.agent import DomainPublisher
    from w2cplatform.domain.federation import Federation
    from w2cplatform.domain.grants import Grant
    from w2cplatform.domain.identity import IdentityStore
    from w2cplatform.domain.signer_service import Holder
    from w2cplatform.domain.term import DomainHolder
    from w2cplatform.domain.uplink import publication
    from w2cplatform.domain.carry import HolderDoor, publication_bytes
    from w2cplatform.trust.memberkey import MemberKey, sign_request
    from w2cplatform.trust.signer import Signer
    from tests.domain.conftest import Clock
    from tests.domain.books_fixture import initial_books
    wall, fed, devices = Clock(), Federation(), {}
    for i in range(2):
        d = DeviceCluster(f'BOOT{i}', FakeVariables(), wall=wall)
        d.boot(); MemberKey.load_or_make(d.flash)
        devices[d.name] = d; fed.add(d.cluster(domain=i == 0))
    home = fed.domain_holder
    signer = Signer('acme', home.vars, now=wall)
    DomainPublisher(home.vars).publish_keys(signer.tokens.keyset())
    term = DomainHolder(fed, home.name, signer, 1, wall, objects=devices[home.name].disk)
    term.claim()
    destination = next(n for n in devices if n != home.name)
    def first_grant():
        DomainPublisher(home.vars).publish_grants(destination, [Grant('anna', 'admin', None, wall()+3600)])
    def refused():
        try: first_grant()
        except declared.NamesUnavailable: return
        raise AssertionError('an unknown names index allowed grant expansion')
    refused()                                                   # absent
    where = booknames.path('live', 'stream-accounts')
    home.vars.put(where, {'': '{torn'})
    refused()                                                   # damaged
    objects = devices[home.name].disk
    holder = Holder(home.vars, objects, signer, fed=fed, term=term, wall=wall)
    holder.run_pass()
    refused()                                                   # real admitted members have not reported
    assert set(booknames.decode(home.vars.get(where)[0], where)[1]) == set(devices)
    # One report is still not a complete observation of the admitted roster.
    d = devices[home.name]
    key = MemberKey.load_or_make(d.flash)
    body = publication_bytes(publication(d.name, d.flash, d.local_objects(), wall(), key=key))
    signature = sign_request(key, 'POST', '/api/member/' + d.name, body, wall())
    HolderDoor(home.vars, objects, wall=wall).member(d.name, body, signature)
    holder.run_pass(); refused()
    initial_books(fed, signer, wall, {n: (d.flash, d.local_objects()) for n, d in devices.items()}, objects=objects)
    assert booknames.complete(home.vars, 'live', 'stream-accounts') == {}
    first_grant()
    IdentityStore(signer, home.vars, objects, now=wall).create_local('first-person', 'a long password', [])
