"""ADR-0074: ordinary workers publish/read books through spec-generated grants."""
import tempfile
from unittest.mock import patch

from w2cplatform import catalog
from w2cplatform.cluster.rights import roles
from w2cplatform.rights import allowed
from w2cplatform.spec import BookMerge, _worker
from w2cplatform.variables import FileVariables, Forbidden, GuardFailed
from w2cplatform.worker import Worker

from tests.conftest import Clock
from tests.test_book_names import raises, spec


def test_worker_reads_accept_exact_rows_and_families_but_reject_unsafe_paths():
    for sub in ("testsub", "testsub2"):
        reads = [f"domain/{sub}/counts", f"domain/placed/{sub}/", f"domain/{sub}/items/*"]
        assert _worker(sub, {"reads": reads})[1] == tuple(reads)
        for path in ("domain", "domain//counts", "/domain/counts", "domain/counts//",
                     "domain/../counts", "domain/./counts", "domain/*/counts",
                     "domain/counts/*/", "domain/counts/\n", 1, None, {}):
            raises(ValueError, lambda: _worker(sub, {"reads": [path]}))


def test_generated_reads_reach_family_children_without_granting_siblings_or_writes():
    specs = [spec(), spec("testsub2")]
    for s in specs:
        s.worker_reads = (f"domain/{s.name}/counts", f"domain/placed/{s.name}/")
    grants = roles(specs, "tests")
    for s in specs:
        own = grants[f"{s.name}worker"]
        for key in (f"domain/{s.name}/counts", f"domain/placed/{s.name}/badge"):
            assert allowed(own["read"], key)
            assert not allowed(own["write"], key)
        for key in (f"domain/{s.name}/counts/badge", f"domain/placed/{s.name}-other/badge",
                    f"domain/placed/{s.name}", "domain/placed/foreign/badge"):
            assert not allowed(own["read"], key)


def test_worker_book_inputs_publish_with_generated_acl_and_atomic_slot_guard():
    specs = [spec(), spec("testsub2")]
    for s in specs:
        s.domain.merged["exact"] = BookMerge(f"{s.name}/exact/w-1", "name", "all", "to")
    grants = roles(specs, "tests")
    with patch.object(catalog, "_loaded", {s.name: s for s in specs}), patch.object(catalog, "_derived", {}):
        with tempfile.TemporaryDirectory(prefix="book-access-") as root:
            store, wall = FileVariables(root), Clock(1000)
            for s in specs:
                acl = grants[f"{s.name}worker"]
                # The in-process grant and configstore role derive the same input rights.
                writer = store.as_writer(f"{s.name}worker", s.acl_worker_role())
                w = Worker(s.sub, None, writer, None, wall=wall, clock=wall, spec=s)
                w.claim_slot("w-1")
                paths = (f"{s.name}/counts/w-1", f"{s.name}/exact/w-1")
                for key in paths:
                    assert allowed(acl["write"], key) and allowed(acl["delete"], key)
                    w.put_under_slot(key, {"i": "current"})
                    assert store.get(key)[0] == {"i": "current"}
                for key in (f"{s.name}/exact/w-2", f"{s.name}/counts-other/w-1",
                            "foreign/counts/w-1", f"domain/{s.name}/counts"):
                    assert not allowed(acl["write"], key)
                    raises(Forbidden, lambda: w.put_under_slot(key, {"i": "forbidden"}))
                # Takeover cleanup is itself authorized, and cannot be bypassed by the old writer.
                next_owner = Worker(s.sub, None, writer, None, wall=wall, clock=wall, spec=s)
                next_owner.claim_slot("w-1")
                assert all(store.get(key)[0] is None for key in paths)
                raises(GuardFailed, lambda: w.put_under_slot(paths[0], {"i": "late"}))
                next_owner.put_under_slot(paths[0], {"i": "next"})
                wall.advance(next_owner.slot_ttl)
                raises(GuardFailed, lambda: next_owner.put_under_slot(paths[0], {"i": "expired"}))


def test_configstore_enforces_generated_reads_and_guarded_book_writes_at_its_door():
    from w2cplatform.configstorevars import ConfigstoreVariables
    from w2cplatform.storemachine import Rights, StoreMachine, local_transport

    specs = [spec(), spec("testsub2")]
    for s in specs:
        s.worker_reads = (f"domain/{s.name}/counts", f"domain/placed/{s.name}/")
    grants, machine, wall = roles(specs, "tests"), StoreMachine(), Clock(1000)

    def door(role):
        return ConfigstoreVariables("/book-test", transport=local_transport(machine.apply, Rights(grants), role))

    seed = door("admin")
    with patch.object(catalog, "_loaded", {s.name: s for s in specs}), patch.object(catalog, "_derived", {}):
        for s in specs:
            wrk = door(f"{s.name}worker")
            family, exact = f"domain/placed/{s.name}/badge", f"domain/{s.name}/counts"
            for key in (family, exact):
                seed.put(key, {"fact": "confirmed"})
                assert wrk.get(key)[0] == {"fact": "confirmed"}
                raises(Forbidden, lambda: wrk.put(key, {"fact": "invented"}))
            for key in (f"domain/placed/{s.name}-other/badge", exact + "/badge"):
                seed.put(key, {"fact": "private"})
                raises(Forbidden, lambda: wrk.get(key))
            worker = Worker(s.sub, None, wrk, None, wall=wall, clock=wall, spec=s)
            worker.claim_slot("w-1")
            path = f"{s.name}/counts/w-1"
            worker.put_under_slot(path, {"i": "current"})
            assert wrk.get(path)[0] == {"i": "current"}
            successor = Worker(s.sub, None, wrk, None, wall=wall, clock=wall, spec=s)
            successor.claim_slot("w-1")
            assert wrk.get(path)[0] is None
            raises(GuardFailed, lambda: worker.put_under_slot(path, {"i": "late"}))
