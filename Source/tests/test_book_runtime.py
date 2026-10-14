"""ADR-0074 holder collection and secret transport, only testsub/testsub2 specs."""
import contextlib
import copy
import json
from types import SimpleNamespace
from unittest.mock import patch

from w2cplatform import catalog
from w2cplatform.domain import booknames, bookruntime, booksecrets, declared
from w2cplatform.domain.agent import DomainAgent, DomainPublisher
from w2cplatform.domain.carry import answer, open_row, seal_row, publication_bytes
from w2cplatform.domain.readview import ReadView
from w2cplatform.domain.reports import pinned
from w2cplatform.domain.signer_service import Holder
from w2cplatform.domain.steps import one_pass
from w2cplatform.domain.uplink import publication, report, take
from w2cplatform.sealing import Sealer, Sealed
from w2cplatform.trust.documents import NotTaken, verify
from w2cplatform.trust.memberkey import MemberKey, NotMine, seal_to
from w2cplatform.trust.signer import DomainRoot, Signer
from w2cplatform.trust.tokens import KeySet, ROOT_KID

from tests.test_book_names import raises, spec
from tests.test_domain_platform import site as platform_site

SECRET = "synthetic-book-test-value"


def ring(label):
    return Sealer({label: (label.encode() * 32)[:32]}, label)


@contextlib.contextmanager
def site(two=False):
    fed, wall = platform_site()
    north = fed.clusters["north"]
    holder_ring = ring("holder")
    root = DomainRoot("acme", now=wall)
    signer = Signer("acme", north.vars, root=root, now=wall, sealer=holder_ring)
    specs = [spec(), spec("testsub2")] if two else [spec()]
    with patch.object(catalog, "_loaded", {s.name: s for s in specs}), patch.object(catalog, "_derived", {}):
        keys = root.key_set(signer.tokens.keyset(), 1)
        DomainPublisher(north.vars).publish_keys(keys)
        rings, memberkeys = {}, {}
        for name, c in fed.clusters.items():
            rings[name], memberkeys[name] = ring(name), MemberKey.new()
            c.vars.put("domain/keys", keys)
            c.vars.put("domain/root", {"pub": root.public_bytes.hex()})
        north.vars.put("domain/members", {"doc": json.dumps({"rev": 1, "members": {n: {"key": memberkeys[n].pub, "seal": memberkeys[n].seal_pub} for n in fed.clusters}})})
        holder = Holder(north.vars, north.objects, signer, fed=fed,
                        view=ReadView(fed, wall=wall), wall=wall, sealer=holder_ring)
        yield SimpleNamespace(fed=fed, wall=wall, north=north, holder=holder, root=root, signer=signer,
                              specs=specs, rings=rings, memberkeys=memberkeys)


def input_row(env, member="north", sub="testsub", *, secret=True, **fields):
    source = f"{sub}/counts/w1"
    from w2cplatform.contract import Slot
    env.fed.clusters[member].vars.put(f"{sub}/slots/w1", Slot("w1", "book-test-owner", env.wall() + 1000, False, 1).to_items())
    value = {"name": "badge", "to": "south", "n": 7, **fields}
    if secret:
        value["nested"] = [{"token_secret": SECRET}]
    row = seal_row(env.rings[member], {"i": json.dumps(value)}, source)
    env.fed.clusters[member].vars.put(source, row)
    return source


def publish_all(env):
    for name, c in env.fed.clusters.items():
        report(name, c.vars, c.objects, env.north.objects, env.wall(), key=env.memberkeys[name], sealer=env.rings[name])


def test_released_expired_or_absent_input_slot_is_empty_not_a_missing_member():
    from w2cplatform.contract import Slot
    for sub in ("testsub", "testsub2"):
        with site(two=True) as e:
            s = next(s for s in e.specs if s.name == sub)
            path = input_row(e, sub=sub, secret=False)
            e.north.vars.put("domain/grants/south", {"badge|view|": str(e.wall() + 500)})
            publish_all(e)
            assert "badge" in bookruntime.collect(e.holder, s, "counts").rows["south"]
            for state in (Slot("w1", "owner", e.wall() + 50, True, 1),
                          Slot("w1", "owner", e.wall(), False, 1),
                          Slot("w1", "", e.wall() + 50, False, 1), None):
                if state is None:
                    e.north.vars.delete(f"{sub}/slots/w1")
                else:
                    e.north.vars.put(f"{sub}/slots/w1", state.to_items())
                e.wall.advance(1)
                publish_all(e)
                got = bookruntime.collect(e.holder, s, "counts")
                assert "badge" not in got.rows["south"] and "north" not in got.missing
                assert e.north.vars.get(path)[0] is not None  # omission does not delete another process's row


def test_report_omits_input_when_slot_is_released_during_its_read():
    from .test_book_names import raises
    with site() as e:
        path = input_row(e, secret=False)
        e.north.vars.put("domain/grants/south", {"badge|view|": str(e.wall() + 500)})
        original = e.north.vars.get
        def released(key):
            got = original(key)
            if key == path:
                slot = original("testsub/slots/w1")[0]
                slot["released"] = "true"
                e.north.vars.put("testsub/slots/w1", slot)
            return got
        with patch.object(e.north.vars, "get", side_effect=released):
            pub = publication("north", e.north.vars, e.north.objects, e.wall(), key=e.memberkeys["north"])
        assert path not in pub["rows"]
        # An unreadable slot does not become an empty complete report.
        with patch.object(e.north.vars, "get", side_effect=OSError("slot store unavailable")):
            raises(OSError, lambda: publication("north", e.north.vars, e.north.objects, e.wall()))


def test_new_slot_owner_clears_all_its_input_families_but_not_other_writers():
    from w2cplatform.worker import Worker
    from w2cplatform.spec import BookMerge
    from w2cplatform.variables import GuardFailed
    for sub in ("testsub", "testsub2"):
        with site(two=True) as e:
            s = next(s for s in e.specs if s.name == sub)
            s.domain.merged["other"] = BookMerge(f"{sub}/other/", "name", "unique", "to")
            def worker():
                return Worker(s.sub, None, e.north.vars, e.north.objects, wall=e.wall, clock=e.wall, spec=s)
            old = worker(); old.claim_slot("w-9")
            for prefix in ("counts", "other"):
                old.put_under_slot(f"{sub}/{prefix}/w-9", {"i": "old"})
                e.north.vars.put(f"{sub}/{prefix}/w-8", {"i": "neighbour"})
            new = worker(); new.claim_slot("w-9")
            for prefix in ("counts", "other"):
                assert e.north.vars.get(f"{sub}/{prefix}/w-9")[0] is None
                assert e.north.vars.get(f"{sub}/{prefix}/w-8")[0] == {"i": "neighbour"}
            raises(GuardFailed, lambda: old.put_under_slot(f"{sub}/counts/w-9", {"i": "late"}))
            new.put_under_slot(f"{sub}/counts/w-9", {"i": "new"})
            assert e.north.vars.get(f"{sub}/counts/w-9")[0] == {"i": "new"}


def test_slot_cleanup_cannot_erase_the_next_owner_after_a_takeover_race():
    from w2cplatform.worker import Worker
    from w2cplatform.variables import GuardFailed
    with site() as e:
        s = e.specs[0]
        first = Worker(s.sub, None, e.north.vars, e.north.objects, wall=e.wall, clock=e.wall, spec=s)
        original = e.north.vars.delete
        def takeover(path, cas=None, *, guard=None):
            next_owner = Worker(s.sub, None, e.north.vars, e.north.objects, wall=e.wall, clock=e.wall, spec=s)
            with patch.object(e.north.vars, "delete", side_effect=original):
                next_owner.claim_slot("w-9")
            next_owner.put_under_slot(path, {"i": "next"})
            return original(path, cas=cas, guard=guard)
        with patch.object(e.north.vars, "delete", side_effect=takeover):
            raises(GuardFailed, lambda: first.claim_slot("w-9"))
        assert e.north.vars.get("testsub/counts/w-9")[0] == {"i": "next"}


def test_agent_cannot_publish_predecessor_input_between_slot_claim_and_cleanup():
    from w2cplatform.worker import Worker
    with site() as e:
        s = e.specs[0]
        old = Worker(s.sub, None, e.north.vars, e.north.objects, wall=e.wall, clock=e.wall, spec=s)
        old.claim_slot("w-9")
        path = "testsub/counts/w-9"
        old.put_under_slot(path, {"i": "old"})
        original = e.north.vars.delete
        seen = []
        def during_claim(key, cas=None, *, guard=None):
            if key == path:
                assert e.north.vars.get("testsub/slots/w-9")[0]["released"] == "true"
                pub = publication("north", e.north.vars, e.north.objects, e.wall(), key=e.memberkeys["north"])
                seen.append(path not in pub["rows"])
            return original(key, cas=cas, guard=guard)
        new = Worker(s.sub, None, e.north.vars, e.north.objects, wall=e.wall, clock=e.wall, spec=s)
        with patch.object(e.north.vars, "delete", side_effect=during_claim):
            new.claim_slot("w-9")
        assert seen == [True] and e.north.vars.get(path)[0] is None
        assert e.north.vars.get("testsub/slots/w-9")[0]["released"] == "false"


def test_keyset_requires_public_receive_key_and_root_signature_covers_it():
    with site() as e:
        items = e.north.vars.get("domain/keys")[0]
        public = KeySet.from_items(items).book_seal
        assert public == e.signer.book_key.seal_pub
        doc = json.loads(items["doc"])
        rootkeys = KeySet(current="", keys={ROOT_KID: e.root.public_bytes})
        assert verify(doc, rootkeys, e.wall())["keys"]["book_seal"] == public
        for value in (None, "", "abc", "A" * 64, 7):
            bad = copy.deepcopy(doc)
            if value is None:
                del bad["keys"]["book_seal"]
            else:
                bad["keys"]["book_seal"] = value
            raises(ValueError, lambda: KeySet.from_items({"doc": json.dumps(bad)}))
        bad = copy.deepcopy(doc)
        bad["keys"]["book_seal"] = MemberKey.new().seal_pub
        raises(NotTaken, lambda: verify(bad, rootkeys, e.wall()))
        assert DomainAgent("south", e.north.vars, e.fed.clusters["south"].vars, now=e.wall)._carry_keys(
            {"doc": json.dumps(bad)}).startswith("refused:")


def test_receive_seed_is_sealed_and_missing_or_corrupt_seed_never_regenerates():
    with site() as e:
        row = e.north.vars.get(booksecrets.ROW)[0]
        assert set(row) == {"seed_secret"} and row["seed_secret"].startswith("enc:v1:")
        assert Signer("acme", e.north.vars, now=e.wall, sealer=e.holder.sealer).book_key.seal_pub == e.signer.book_key.seal_pub
        raises(Sealed, lambda: Signer("acme", e.north.vars, now=e.wall))
        for bad in ({}, {"seed_secret": "not-a-seed"}, {"seed_secret": "00" * 32, "other": "x"}):
            e.north.vars.put(booksecrets.ROW, bad)
            raises(booksecrets.Unavailable, lambda: Signer("acme", e.north.vars, now=e.wall, sealer=e.holder.sealer))
            assert e.north.vars.get(booksecrets.ROW)[0] == bad


def test_publication_includes_declared_inputs_and_seals_before_signing_for_both_subsystems():
    with site(two=True) as e:
        for s in e.specs:
            path = input_row(e, sub=s.name)
            pub = publication("north", e.north.vars, e.north.objects, e.wall(), key=e.memberkeys["north"],
                              sealer=e.rings["north"])
            raw = pub["rows"][path]["items"]["i"]
            cipher = json.loads(raw)["nested"][0]["token_secret"]
            assert SECRET not in publication_bytes(pub).decode() and cipher.startswith("x25519:v1:")
            ctx = booksecrets.context("north", path, "i")
            assert e.signer.book_key.open("token_secret", cipher, ctx) == SECRET
            for wrong in (("south", path, "i"), ("north", path + "x", "i"), ("north", path, "other")):
                raises(NotMine, lambda: e.signer.book_key.open("token_secret", cipher, booksecrets.context(*wrong)))
        e.north.vars.put("testsub/undeclared", {"secret": "unpublished"})
        assert "testsub/undeclared" not in pub["rows"]


def test_agent_uses_only_a_verified_signed_receive_key_and_requires_the_member_ring():
    with site() as e:
        path = input_row(e)
        stored = e.north.vars.get(path)[0]
        raises(booksecrets.Unavailable, lambda: publication("north", e.north.vars, e.north.objects, e.wall()))
        e.north.vars.put("domain/keys", e.signer.tokens.keyset().to_items())
        raises(booksecrets.Unavailable, lambda: booksecrets.outgoing("north", path, stored, e.north.vars,
                                                                   e.rings["north"], e.wall()))
        assert e.north.vars.get(path)[0] == stored


def test_holder_pass_delivers_only_addressed_granted_entries_and_reseals_each_boundary():
    with site(two=True) as e:
        for s in e.specs:
            input_row(e, sub=s.name)
        e.north.vars.put("domain/grants/south", {"badge|view|unit:testsub/c1": str(e.wall() + 100)})
        publish_all(e)
        raw = pinned("north", e.north.objects).raw
        results = e.holder.run_pass()
        assert not e.holder.loop.failing
        for s in e.specs:
            assert f"collecting {s.name}/counts" in results
            dest = f"domain/{s.name}/counts/south"
            row = e.north.vars.get(dest)[0]
            assert SECRET not in json.dumps(row) and "badge" in row
            cipher = json.loads(row["badge"])["entries"][0]["value"]["nested"][0]["token_secret"]
            assert cipher.startswith("enc:v1:")
            assert e.holder.sealer.open("token_secret", cipher, dest + "#badge") == SECRET
            carried = answer(e.north.vars, e.north.objects, "south", e.memberkeys["south"].seal_pub,
                             e.holder.sealer, now=e.wall())
            memberpath = f"domain/{s.name}/counts"
            cipher = json.loads(carried["rows"][dest]["badge"])["entries"][0]["value"]["nested"][0]["token_secret"]
            assert e.memberkeys["south"].open("token_secret", cipher, memberpath + "#badge") == SECRET
            assert set(e.north.vars.get(f"domain/{s.name}/counts/north")[0]) == {""}
        assert pinned("north", e.north.objects).raw == raw  # collection never rewrites accepted ciphertext
        e.north.vars.put("domain/grants/south", {})
        carried = answer(e.north.vars, e.north.objects, "south", e.memberkeys["south"].seal_pub,
                         e.holder.sealer, now=e.wall())
        assert all("badge" not in row for path, row in carried["rows"].items() if "/counts" in path)


def test_bad_incoming_secret_is_missing_never_delivered_and_diagnostics_hold_no_values():
    with site() as e:
        path = input_row(e)
        e.north.vars.put("domain/grants/south", {"badge|view|": str(e.wall() + 100)})
        publish_all(e)
        doc = pinned("north", e.north.objects).document()
        cipher = json.loads(doc["rows"][path]["items"]["i"])["nested"][0]["token_secret"]
        for invalid in (SECRET, "x25519:v1:garbage", 12,
                        seal_to(MemberKey.new().seal_pub, "token_secret", SECRET, booksecrets.context("north", path, "i")),
                        seal_to(e.signer.book_key.seal_pub, "token_secret", SECRET, booksecrets.context("south", path, "i"))):
            e.wall.advance(1)
            bad = copy.deepcopy(doc)
            bad["sent_at"] = e.wall()
            value = json.loads(bad["rows"][path]["items"]["i"])
            value["nested"][0]["token_secret"] = invalid
            bad["rows"][path]["items"]["i"] = json.dumps(value)
            take("north", publication_bytes(bad), e.north.objects, received_at=e.wall(), signature="authenticated-at-door")
            got = bookruntime.collect(e.holder, e.specs[0], "counts")
            assert got.missing == ("north",) and SECRET not in repr(got.diagnostics)
            assert set(e.north.vars.get("domain/testsub/counts/south")[0]) == {""}
        assert e.signer.book_key.open("token_secret", cipher, booksecrets.context("north", path, "i")) == SECRET


def test_withdrawal_lost_report_and_holder_restart_release_names_without_reusing_old_values():
    with site() as e:
        path = input_row(e, secret=False)
        e.north.vars.put("domain/grants/south", {"badge|view|": str(e.wall() + 500)})
        publish_all(e)
        bookruntime.collect(e.holder, e.specs[0], "counts")
        assert "badge" in e.north.vars.get(booknames.path("testsub", "counts"))[0]
        e.wall.advance(46)
        restarted = Holder(e.north.vars, e.north.objects, e.signer, fed=e.fed, wall=e.wall)
        got = bookruntime.collect(restarted, e.specs[0], "counts")
        assert got.missing == () and set(e.north.vars.get("domain/testsub/counts/south")[0]) == {""}
        assert "badge" not in e.north.vars.get(booknames.path("testsub", "counts"))[0]
        e.north.vars.delete(path)
        publish_all(e)
        assert not bookruntime.collect(e.holder, e.specs[0], "counts").subjects


def test_all_books_in_a_pass_pin_one_generation_and_publish_names_only_if_declared():
    with site(two=True) as e:
        for s in e.specs:
            input_row(e, sub=s.name, secret=False)
        e.north.vars.put("domain/grants/south", {"badge|view|": str(e.wall() + 500)})
        publish_all(e)
        with one_pass():
            first = bookruntime.collect(e.holder, e.specs[0], "counts")
            e.wall.advance(1)
            input_row(e, sub="testsub2", secret=False, name="new")
            publish_all(e)
            second = bookruntime.collect(e.holder, e.specs[1], "counts")
            assert first.subjects == second.subjects == {"badge": ("north",)}
        assert bookruntime.collect(e.holder, e.specs[1], "counts").subjects == {"new": ("north",)}
        e.specs[1].domain.names.clear()
        e.north.vars.put(booknames.path("testsub2", "counts"), {"sentinel": "unchanged"})
        bookruntime.collect(e.holder, e.specs[1], "counts")
        assert e.north.vars.get(booknames.path("testsub2", "counts"))[0] == {"sentinel": "unchanged"}


def test_receive_seed_is_only_read_and_written_by_the_domain_role():
    from w2cplatform.domain.rights import roles
    from w2cplatform.rights import allowed
    with site(two=True) as e:
        for name, grants in roles(specs=e.specs).items():
            assert allowed(grants["read"], booksecrets.ROW) == (name == "domain")
            assert allowed(grants["write"], booksecrets.ROW) == (name == "domain")


def test_rotation_changes_signed_revision_and_old_reports_stay_missing_until_republication():
    with site() as e:
        input_row(e)
        e.north.vars.put("domain/grants/south", {"badge|view|": str(e.wall() + 500)})
        publish_all(e)
        before = pinned("north", e.north.objects).raw
        old = e.signer.book_key.seal_pub
        assert "badge" in bookruntime.collect(e.holder, e.specs[0], "counts").rows["south"]
        assert e.signer.rotate_book_seal(e.root) == 2
        assert e.signer.book_key.seal_pub != old
        assert KeySet.from_items(e.north.vars.get("domain/keys")[0]).book_seal == e.signer.book_key.seal_pub
        got = bookruntime.collect(e.holder, e.specs[0], "counts")
        assert got.missing == ("north",) and set(got.rows["south"]) == {""}
        assert pinned("north", e.north.objects).raw == before
        e.wall.advance(1)
        publish_all(e)
        assert "badge" in bookruntime.collect(e.holder, e.specs[0], "counts").rows["south"]


def test_rotation_by_another_root_is_refused_without_changing_seed_or_keyset():
    with site() as e:
        before = [e.north.vars.get(p) for p in (booksecrets.ROW, "domain/keys")]
        raises(NotTaken, lambda: e.signer.rotate_book_seal(DomainRoot("another", now=e.wall)))
        assert before == [e.north.vars.get(p) for p in (booksecrets.ROW, "domain/keys")]


def test_actual_backup_and_move_preserve_receive_seed_and_stolen_move_rotates_it():
    from w2cplatform.domain.term import DomainHolder, move_domain
    from w2cplatform.trust.documents import sign
    for stolen in (False, True):
        with site() as e:
            input_row(e, member="south")
            e.north.vars.put("domain/grants/south", {"badge|view|": str(e.wall() + 500)})
            publish_all(e)
            old = e.signer.book_key.seal_pub
            accepted = pinned("south", e.north.objects).raw
            record = sign({"term": 1, "holder": "north", "at": e.wall()}, e.root)
            term = DomainHolder(e.fed, "north", e.signer, 1, e.wall, objects=e.north.objects, record=record)
            term.claim()
            term.backup(["south"], e.north.objects)
            south = e.fed.clusters["south"]
            agent = DomainAgent("south", e.north.vars, south.vars, now=e.wall, domain_objects=e.north.objects,
                                cluster_objects=south.objects, sealer=e.rings["south"], key=e.memberkeys["south"])
            assert agent.sync()
            moved, _ = move_domain(e.fed, "south", e.root.recovery(), "acme", lambda n: e.fed.clusters[n].objects,
                                   e.wall, stolen=stolen, sealer=e.rings["south"])
            ks = KeySet.from_items(south.vars.get("domain/keys")[0])
            assert (ks.book_seal == old) == (not stolen)
            assert ks.book_seal == moved.signer.book_key.seal_pub
            assert ks.rev > 1, ks.rev
            assert pinned("south", south.objects).raw == accepted, "restored report bytes changed"
            assert south.vars.get(booksecrets.ROW)[0]["seed_secret"].startswith("enc:v1:south:")
            current = Holder(south.vars, south.objects, moved.signer, fed=e.fed, wall=e.wall)
            got = bookruntime.collect(current, e.specs[0], "counts")
            assert ("badge" in got.rows["south"]) == (not stolen)
            if stolen:
                assert "south" in got.missing
                e.wall.advance(1)
                report("south", south.vars, south.objects, south.objects, e.wall(),
                       key=e.memberkeys["south"], sealer=e.rings["south"])
                assert "badge" in bookruntime.collect(current, e.specs[0], "counts").rows["south"]


def test_holder_without_ring_refuses_secrets_and_can_deliver_a_nonsecret_book():
    with site(two=True) as e:
        input_row(e)
        input_row(e, sub="testsub2", secret=False)
        e.north.vars.put("domain/grants/south", {"badge|view|": str(e.wall() + 500)})
        publish_all(e)
        e.holder.sealer = None
        secret = bookruntime.collect(e.holder, e.specs[0], "counts")
        ordinary = bookruntime.collect(e.holder, e.specs[1], "counts")
        assert secret.missing == ("north",) and set(secret.rows["south"]) == {""}
        assert "badge" in ordinary.rows["south"]


def test_direct_and_relay_doors_preserve_ciphertext_and_require_authenticated_origin():
    from w2cplatform.domain.carry import HolderDoor, CarryClient, Refused
    from w2cplatform.domain.members import Members
    from w2cplatform.domain.relay import RelayDoor, relayed
    from w2cplatform.trust.memberkey import sign_request
    with site() as e:
        members = Members(e.north.vars, e.wall)
        for name, key in e.memberkeys.items():
            members.add(name, "test", key=key.pub, seal=key.seal_pub)
        input_row(e, member="south")
        e.north.vars.put("domain/grants/south", {"badge|view|": str(e.wall() + 500)})
        door = HolderDoor(e.north.vars, e.north.objects, sealer=e.holder.sealer, wall=e.wall)
        south = e.fed.clusters["south"]
        pub = publication("south", south.vars, south.objects, e.wall(), key=e.memberkeys["south"],
                          sealer=e.rings["south"])
        body = publication_bytes(pub)
        signature = sign_request(e.memberkeys["south"], "POST", "/api/member/south", body, e.wall())
        assert SECRET.encode() not in body
        raises(Refused, lambda: door.member("south", body, sign_request(
            MemberKey.new(), "POST", "/api/member/south", body, e.wall())))
        assert door.member("south", body, signature)["cluster"] == "south"
        assert pinned("south", e.north.objects).raw == body
        report("north", e.north.vars, e.north.objects, e.north.objects, e.wall(),
               key=e.memberkeys["north"], sealer=e.rings["north"])
        bookruntime.collect(e.holder, e.specs[0], "counts")
        client = CarryClient(door, "south", e.memberkeys["south"], wall=e.wall)
        agent = DomainAgent("south", client, south.vars, now=e.wall, sealer=e.rings["south"], key=e.memberkeys["south"])
        assert agent.sync()
        value = json.loads(open_row(e.rings["south"], south.vars.get("domain/testsub/counts")[0],
                                   "domain/testsub/counts")["badge"])
        assert value["entries"][0]["value"]["nested"][0]["token_secret"] == SECRET
        relay = SimpleNamespace(now=e.wall, relayed={"south": {"key": e.memberkeys["south"].pub}},
                                relay_members=["south"])
        relaydoor = RelayDoor(relay, relay_objects=south.objects)
        relaydoor.member("south", body, signature)
        assert relayed(["south"], south.objects)["south"] == body
        assert pinned("south", south.objects).raw == body
        raises(NotMine, lambda: e.memberkeys["north"].open("token_secret",
            json.loads(pub["rows"]["testsub/counts/w1"]["items"]["i"])["nested"][0]["token_secret"],
            booksecrets.context("south", "testsub/counts/w1", "i")))


def test_authenticated_plaintext_resembling_ciphertext_and_empty_secrets_are_resealed():
    with site() as e:
        e.north.vars.put("domain/grants/south", {"badge|view|": str(e.wall() + 500)})
        publish_all(e)
        for text in ("", "enc:v1:literal-value"):
            e.wall.advance(1)
            doc = pinned("north", e.north.objects).document()
            doc["sent_at"] = e.wall()
            secret = seal_to(e.signer.book_key.seal_pub, "token_secret", text,
                             booksecrets.context("north", "testsub/counts/w1", "i"))
            doc["rows"]["testsub/counts/w1"] = {"idx": 1, "items": {"i": json.dumps({
                "name": "badge", "to": "south", "token_secret": secret})}}
            take("north", publication_bytes(doc), e.north.objects, received_at=e.wall(), signature="authenticated")
            got = bookruntime.collect(e.holder, e.specs[0], "counts")
            dest = "domain/testsub/counts/south"
            cipher = json.loads(got.rows["south"]["badge"])["entries"][0]["value"]["token_secret"]
            assert cipher != text and e.holder.sealer.open("token_secret", cipher, dest + "#badge") == text
            carried = answer(e.north.vars, e.north.objects, "south", e.memberkeys["south"].seal_pub,
                             e.holder.sealer, now=e.wall())
            cipher = json.loads(carried["rows"][dest]["badge"])["entries"][0]["value"]["token_secret"]
            assert e.memberkeys["south"].open("token_secret", cipher, "domain/testsub/counts#badge") == text


def test_unchanged_secret_book_does_not_rewrite_results_or_names():
    with site() as e:
        input_row(e)
        e.north.vars.put("domain/grants/south", {"badge|view|": str(e.wall() + 500)})
        publish_all(e)
        bookruntime.collect(e.holder, e.specs[0], "counts")
        paths = ["domain/testsub/counts/north", "domain/testsub/counts/south", booknames.path("testsub", "counts")]
        before = [e.north.vars.get(p) for p in paths]
        bookruntime.collect(e.holder, e.specs[0], "counts")
        assert before == [e.north.vars.get(p) for p in paths]


def test_planned_move_refuses_a_backup_with_a_receive_key_retired_by_rotation():
    from w2cplatform.domain.term import DomainHolder, move_domain
    from w2cplatform.trust.documents import sign
    with site() as e:
        record = sign({"term": 1, "holder": "north", "at": e.wall()}, e.root)
        term = DomainHolder(e.fed, "north", e.signer, 1, e.wall, objects=e.north.objects, record=record)
        term.claim()
        term.backup(["south"], e.north.objects)
        south = e.fed.clusters["south"]
        assert DomainAgent("south", e.north.vars, south.vars, now=e.wall, domain_objects=e.north.objects,
                           cluster_objects=south.objects, key=e.memberkeys["south"], sealer=e.rings["south"]).sync()
        e.signer.rotate_book_seal(e.root)
        err = raises(ValueError, lambda: move_domain(e.fed, "south", e.root.recovery(), "acme",
                       lambda n: e.fed.clusters[n].objects, e.wall, sealer=e.rings["south"]))
        assert "retired book receive key" in str(err) and e.fed.domain_holder.name == "north"


def test_interrupted_rotation_does_not_retain_old_seed_or_rewrite_reports_and_can_be_recovered():
    with site() as e:
        input_row(e)
        e.north.vars.put("domain/grants/south", {"badge|view|": str(e.wall() + 500)})
        publish_all(e)
        before = pinned("north", e.north.objects).raw
        old = e.signer.book_key.seal_pub
        original = e.north.vars.put
        def put(path, items, **kw):
            if path == "domain/keys":
                raise OSError("simulated key set write failure")
            return original(path, items, **kw)
        with patch.object(e.north.vars, "put", put):
            raises(OSError, lambda: e.signer.rotate_book_seal(e.root))
        assert e.signer.book_key.seal_pub != old
        restarted = Signer("acme", e.north.vars, now=e.wall, sealer=e.holder.sealer)
        assert restarted.book_key.seal_pub == e.signer.book_key.seal_pub
        e.holder.signer = restarted
        assert bookruntime.collect(e.holder, e.specs[0], "counts").missing == ("north",)
        assert pinned("north", e.north.objects).raw == before
        assert restarted.rotate_book_seal(e.root) == 2
        e.wall.advance(1)
        publish_all(e)
        assert "badge" in bookruntime.collect(e.holder, e.specs[0], "counts").rows["south"]


def test_book_show_projects_value_fields_preserves_origin_and_never_shows_hidden_or_secret_data():
    from w2cplatform.console import SpecConsole
    from w2cplatform.domain.carry import open_for
    with site() as e:
        input_row(e, hidden="hidden-nonsecret-value")
        e.north.vars.put("domain/grants/south", {"badge|view|": str(e.wall() + 500)})
        publish_all(e)
        bookruntime.collect(e.holder, e.specs[0], "counts")
        carried = answer(e.north.vars, e.north.objects, "south", e.memberkeys["south"].seal_pub,
                         e.holder.sealer, now=e.wall())
        clear = open_for(e.memberkeys["south"], carried, "south")["rows"]["domain/testsub/counts/south"]
        south = e.fed.clusters["south"]
        south.vars.put("domain/testsub/counts", seal_row(e.rings["south"], clear, "domain/testsub/counts", force=True))
        console = SpecConsole.__new__(SpecConsole)
        console.ctl = SimpleNamespace(vars=south.vars)
        console._visible = lambda h: None
        status, shown = console.book_route(None, "GET", spec(show=("n", "nested")), "counts")
        assert status == 200 and shown[""] == {"missing": []}
        assert shown["badge"] == {"entries": [{"member": "north", "item": "w1/i", "n": 7, "nested": [{}]}],
                                  "missing": []}
        assert SECRET not in json.dumps(shown) and "token_secret" not in json.dumps(shown)
        assert "hidden-nonsecret-value" not in json.dumps(shown) and "enc:v1:" not in json.dumps(shown)
        south.vars.put("domain/testsub/counts", {"bad": '{"entries":[{"value":{"token_secret":"hidden"}}],"missing":[]}'})
        assert console.book_route(None, "GET", spec(show=("n",)), "counts") == (200, {})


def test_knocking_member_report_is_not_a_contribution_or_missing():
    with site() as e:
        input_row(e, secret=False)
        input_row(e, member="south", secret=False, name="unadmitted", to="north")
        publish_all(e)
        e.north.vars.put("domain/members", {"doc": json.dumps({"rev": 2, "members": {"north": {}}})})
        got = bookruntime.collect(e.holder, e.specs[0], "counts")
        assert got.subjects == {"badge": ("north",)}
        assert got.missing == () and set(got.rows) == {"north"}
        e.wall.advance(1)
        e.north.vars.put("testsub/counts/w1", {})
        report("north", e.north.vars, e.north.objects, e.north.objects, e.wall(), key=e.memberkeys["north"],
               sealer=e.rings["north"])
        got = bookruntime.collect(e.holder, e.specs[0], "counts")
        assert not got.subjects and got.missing == ()
        e.north.vars.put("domain/members", {"doc": "damaged"})
        got = bookruntime.collect(e.holder, e.specs[0], "counts")
        assert not got.subjects and not got.rows and got.missing == ()


def test_collected_book_is_visible_by_ref_of_another_spec_without_global_view():
    from w2cplatform.console import SpecConsole
    with site(two=True) as e:
        owner, publisher = e.specs
        publisher.domain.ref = ""
        publisher.domain.show["counts"] = ("n", "member", "item")
        con = SpecConsole.__new__(SpecConsole)
        con.ctl = SimpleNamespace(vars=e.north.vars)
        con.units = {owner.name: SimpleNamespace(spec=owner, ctl=SimpleNamespace(units=lambda: [
            {"id": "counter", "name": "badge"}, {"id": "other", "name": "hidden"}]))}
        con._visible = lambda _: lambda unit, labels, of=None: unit == owner.ref("counter")
        marker = json.dumps({"missing": []})
        entry = {"member": "north", "item": "w1/i", "value": {"name": "badge", "n": 7,
                 "member": "forged", "item": "forged", "token_secret": SECRET}}
        e.north.vars.put("domain/testsub2/counts", {"": marker,
            "badge": json.dumps({"entries": [entry], "missing": []}),
            "hidden": json.dumps({"entries": [entry], "missing": []})})
        status, shown = con.book_route(None, "GET", publisher, "counts")
        assert status == 200 and set(shown) == {"", "badge"}
        assert shown["badge"] == {"entries": [{"member": "north", "item": "w1/i", "n": 7}], "missing": []}
        assert SECRET not in json.dumps(shown) and "forged" not in json.dumps(shown)


def test_holder_book_show_unions_recipients_deduplicates_origins_and_projects_only_declared_fields():
    from w2cplatform.domain.console import Console
    with site() as e:
        key = "domain/testsub/counts/"
        def row(entries, missing=()):
            return {"": json.dumps({"missing": list(missing)}),
                    "badge": json.dumps({"entries": entries, "missing": list(missing)})}
        a = {"member": "north", "item": "w1/a", "value": {"n": 7, "hidden": "private-url",
             "nested": [{"token_secret": SECRET, "public": "kept"}]}}
        b = {"member": "south", "item": "w2/b", "value": {"n": 9}}
        e.north.vars.put(key + "north", row([a]))
        e.north.vars.put(key + "south", row([a, b], missing=["absent"]))
        console = Console.__new__(Console)
        console.holder_vars = e.north.vars
        code, shown = console.book_doc(spec(show=("n", "nested")), "counts")
        assert code == 200
        assert shown["badge"] == {"entries": [
            {"member": "north", "item": "w1/a", "n": 7, "nested": [{"public": "kept"}]},
            {"member": "south", "item": "w2/b", "n": 9}], "missing": ["absent"]}
        assert shown[""] == {"missing": ["absent"]}
        assert SECRET not in json.dumps(shown) and "private-url" not in json.dumps(shown)
        for malformed in (row([a, a]), row([{**a, "value": {"n": 8}}]),
                          {"badge": json.dumps({"entries": [a], "missing": []})},
                          {"": '{"missing":[]}', "badge": '{"entries":[],"missing":["other"]}'}):
            e.north.vars.put(key + "south", malformed)
            status, body = console.book_doc(spec(show=("n",)), "counts")
            assert status == 503
            assert SECRET not in json.dumps(body) and "private-url" not in json.dumps(body)
        assert console.book_doc(spec(), "undeclared")[0] == 404


def test_holder_book_http_door_keeps_domain_view_gate_and_never_leaks_unshown_values():
    from w2cplatform.domain.console import Console
    from w2cplatform.domain.federation import DomainDirectory
    from w2cplatform.trust.tokens import TokenError
    from tests.conftest import Served
    with site() as e:
        shown_spec = spec(show=("n",))
        def subject(token):
            if not token:
                raise TokenError("person required")
            return token
        directory = DomainDirectory(e.fed)
        con = Console(directory, ReadView(e.fed, wall=e.wall), SimpleNamespace(_subject=subject),
                      holder_vars=e.north.vars, viewer=lambda name: name == "boss")
        e.north.vars.put("domain/testsub/counts/south", {
            "": '{"missing":[]}', "badge": json.dumps({"missing": [], "entries": [
                {"member": "north", "item": "w1/a", "value": {"n": 7, "hidden": SECRET}}]})})
        with patch.object(catalog, "_loaded", {"testsub": shown_spec}), Served(con) as call:
            path = "/domain/testsub/books/counts"
            assert call("GET", path)[0] == 401
            assert call("GET", path, headers={"Authorization": "Bearer visitor"})[0] == 403
            status, reply = call("GET", path, headers={"Authorization": "Bearer boss"})
            assert status == 200 and reply["badge"]["entries"] == [
                {"member": "north", "item": "w1/a", "n": 7}]
            assert SECRET not in json.dumps(reply)
