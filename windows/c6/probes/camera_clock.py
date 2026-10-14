"""Reproduce C6's extra wall-clock refusal after a fresh authenticated role reply."""
import os
from pathlib import Path
import sys

os.environ.setdefault('STORE_VOLATILE','1')
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'Source'))

from tests.conftest import Clock
from tests.test_autoask import item, road_fixture
from vms.autoask import Asker
from vms.recording_books import Unconfirmed
from w2cplatform.trust.tokens import verify

e=road_fixture()
asker=Asker('A',e.box.vars,e.dial,e.tokens,Clock(0))
try:
    asker.ask('B',item()['then'],7)
except Unconfirmed as error:
    print(type(error).__name__+': '+str(error))
else:
    raise AssertionError('the baseline no longer demonstrates the wall-clock refusal')
assert len(e.calls)==1 and not e.dialled
token=next(iter(e.tokens.cached.values()))[1]
assert verify(token,e.issuer.keyset(),now=e.box.wall(),kind='ask')['kind']=='ask'
print('Fresh role reply: 1; ingest dials: 0; signature valid at signer time: yes.')
print('Signer wall: '+str(e.box.wall())+'; embedded wall: 0.')
