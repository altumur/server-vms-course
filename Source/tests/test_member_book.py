"""A collected book follows the holder role, never the presence of an old copy."""
import json
from w2cplatform.cluster.variables import FakeVariables
from w2cplatform.domain.memberbook import read


def test_holder_reads_its_result_even_with_an_old_copy_and_does_not_fall_back():
    for sub in ("testsub", "testsub2"):
        v = FakeVariables()
        key = f"domain/{sub}/counts"
        v.put(key, {"i": "old copy"})
        v.put(key + "/north", {"i": "current result"})
        v.put("domain/holder", {"doc": json.dumps({"term": 2, "holder": "north"})})
        assert read(v, key, "north") == {"i": "current result"}
        v.put(key + "/north", {})
        assert read(v, key, "north") == {}
        v.put("domain/holder", {"doc": json.dumps({"term": 3, "holder": "south"})})
        assert read(v, key, "north") == {"i": "old copy"}


def test_corrupt_holder_record_cannot_select_a_stale_copy():
    v = FakeVariables()
    v.put("domain/testsub/counts", {"i": "stale"})
    for raw in ("{", "null", '{"holder":"north","term":0}', '{"holder":"north","term":true}'):
        v.put("domain/holder", {"doc": raw})
        try:
            read(v, "domain/testsub/counts", "north")
        except ValueError:
            pass
        else:
            raise AssertionError("invalid holder record selected a copy")
