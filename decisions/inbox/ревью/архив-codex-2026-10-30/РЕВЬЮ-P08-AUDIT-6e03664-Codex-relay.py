"""Same relay property as the R1 witness, with runtime/specs supplied explicitly; CT103."""
import json
import os
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(sys.argv[1]) / 'runner'))
import c_targets
import m11stand

specs = Path(sys.argv[2]); out = Path(os.environ['CHECK_OUT'])
rows = c_targets.table(specs / 'Platform/08-domain/acceptance/3/scenarios.tsv')
first = next(cells for _, cells in rows if cells[:2] == ['21-view-relay-refused', '1'])
assert first[2:] == ['@domain m1 relay', 'ok']

class Proxy:
    def __init__(self, *args, **kwargs): self.port = 23456

class Prepared(m11stand.Bench):
    def make_cluster(self, name, env, preparation): self.clusters[name] = SimpleNamespace()
    def _launch_agent(self, *args): return True

cases = {}
with patch.object(m11stand, 'Proxy', Proxy), patch.object(m11stand.standmod, 'free_port', return_value=23456):
    for scenario in ('15-topology', '16-second-road', first[0]):
        bench = Prepared(SimpleNamespace(lesson='P/08.3'), scenario=scenario)
        try:
            failure = None
            try: started = bench.start_agent('relay')
            except KeyError as error: started, failure = False, 'KeyError: ' + str(error)
            cases[scenario] = dict(clusters=list(bench.clusters), started=started, failure=failure)
        finally:
            shutil.rmtree(bench.root)
result = dict(safety_pass=all('relay' in row['clusters'] and row['started'] for row in cases.values()),
              SUT=0, published_first_step=first, cases=cases)
(out / 'relay-evidence.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(result), flush=True)
