"""Diagnostic probes for the next ADR-0074 stage, against b85c47ae.

Run with the course Python. These demonstrate missing contracts, not acceptance tests
for the proposed implementation. No product imports, real credentials or network access.
"""
import copy
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import yaml

from w2cplatform import catalog
from w2cplatform.domain.bookmerge import collect
from w2cplatform.domain.carry import open_row, seal_row
from w2cplatform.domain.uplink import publication
from w2cplatform.objects import FsObjectStore
from w2cplatform.sealing import Sealed, Sealer
from w2cplatform.spec import SubsystemSpec
from w2cplatform.variables import FileVariables


def refused(fn):
    try:
        fn()
    except (ValueError, Sealed):
        return
    raise AssertionError("the expected refusal did not occur")


def main():
    raw = yaml.safe_load((Path(__file__).parents[1] / "testdata/testsub.subsystem.yaml").read_text())
    raw["domain"]["books"] = {"counts": {
        "from": "testsub/counts/", "key": "name", "pick": "unique", "to": "to"}}
    spec = SubsystemSpec.from_dict(raw)
    catalog.register(spec)
    source = "testsub/counts/w1"
    member_ring = Sealer({"member": bytes(range(32))}, "member")
    holder_ring = Sealer({"holder": bytes(reversed(range(32)))}, "holder")
    value = {"name": "badge-one", "to": "south", "token_secret": "synthetic-probe-value"}
    sealed = seal_row(member_ring, {"item": json.dumps(value)}, source)
    with tempfile.TemporaryDirectory(prefix="adr0074-delivery-") as root:
        variables = FileVariables(str(Path(root) / "vars"), volatile=True)
        objects = FsObjectStore(str(Path(root) / "objects"))
        variables.put(source, sealed)
        objects.put("testsub/snapshot/unplaced", b'{"units":[],"ts":100}')
        pub = publication("north", variables, objects, 100)
        assert source not in pub["rows"]
        print("CONFIRMED: publication does not yet include declared book inputs")

    # Merely adding the source to publication cannot give the holder a member's ring.
    refused(lambda: open_row(holder_ring, sealed, source))
    got = collect(spec.domain.merged["counts"], {"north": {source: sealed}, "south": {}},
                  ["north", "south"])
    row = got.rows["south"]
    assert json.loads(row["badge-one"])["entries"][0]["value"]["token_secret"] == \
        json.loads(sealed["item"])["token_secret"]
    refused(lambda: open_row(holder_ring, row, "domain/testsub/counts/south"))
    refused(lambda: open_row(member_ring, row, "domain/testsub/counts/south"))
    print("CONFIRMED: collected ciphertext needs both a transport key and a new row/item binding")

    # The accepted names contract now loads; declaring the same book as kept remains refused.
    proposed = copy.deepcopy(raw)
    proposed["domain"]["names"]["counts/"] = {"exclusive_with": "domain/users", "grant": "view"}
    assert "counts/" in SubsystemSpec.from_dict(proposed).domain.names
    proposed["domain"]["kept"].append("counts/")
    refused(lambda: SubsystemSpec.from_dict(proposed))
    print("IMPLEMENTED: collected book names load without a kept family; the kept overlap is refused")


if __name__ == "__main__":
    main()
