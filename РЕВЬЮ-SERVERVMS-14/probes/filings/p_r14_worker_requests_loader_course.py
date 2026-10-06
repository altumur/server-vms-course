# r14 probe (COURSE; argv[1] = course tree root or Source/): the loader of `worker: {requests: [...]}` (spec.py `_worker`)
# takes a name of no subsystem in the catalogue, the spec's own name, and a subsystem that declares no `requests:` family.
# Expected on e7443379 (defect, ADR-0012): all three load; a worker of such a spec files `<typo>/requests/<id>` (True) —
# a row no holder serves and no reaper clears (requests.turn skips specs without `requests`).
import os
import sys

root = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
src = root if os.path.isdir(os.path.join(root, "w2cplatform")) else os.path.join(root, "Source")
sys.path.insert(0, src)
os.chdir(src)

import yaml  # noqa: E402
from w2cplatform.spec import SubsystemSpec  # noqa: E402

with open(os.path.join(src, "tests", "testdata", "testsub2.subsystem.yaml"), encoding="utf-8") as f:
    base = yaml.safe_load(f)
for names in (["recc"], ["testsub2"], ["live"]):
    try:
        s = SubsystemSpec.from_dict({**base, "worker": {"requests": names}})
        print(f"worker.requests {names}: LOADED, worker_requests={s.worker_requests}, grant={s.acl_worker_role()[-1:]}")
    except Exception as e:  # noqa: BLE001
        print(f"worker.requests {names}: refused: {e}")
