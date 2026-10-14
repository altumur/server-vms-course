"""C6 regression: a correlated role reply works without a local wall-clock epoch."""
import os
from pathlib import Path
import sys

os.environ.setdefault('STORE_VOLATILE','1')
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'Source'))

from tests.conftest import Clock
from tests.test_autoask import item, road_fixture
from vms.autoask import Asker

for wall in (0, 10**12):
    e=road_fixture()
    asker=Asker('A',e.box.vars,e.dial,e.tokens,Clock(wall))
    assert asker.ask('B',item()['then'],7)[0] is e.ingest
    assert len(e.calls)==1 and e.dialled
    print(f'Local wall {wall}: fresh correlated role reply accepted; ingest reached.')
