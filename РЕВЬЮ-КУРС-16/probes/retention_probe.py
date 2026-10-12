#!/usr/bin/env python3
"""Independent retention probe. Source is a pinned git-archive snapshot; output is evidence, not author tests."""
import argparse, json, os, sys, tempfile
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('source', help='snapshot Source directory')
args = parser.parse_args()
sys.path.insert(0, str(Path(args.source).resolve()))
os.environ.setdefault('STORE_VOLATILE', '1')
os.environ.setdefault('WATERMARK_DEFAULT', 'off')
from w2cplatform.events import EventLog, ALARM
from w2cplatform.objects import FsObjectStore
from w2cplatform.variables import FileVariables
from w2cplatform.resource import Resource, RETENTION, MIRROR_DIR
from w2cplatform.rows import forget

DAY = 86400.0
NOW = 1757500000.0

def scenario(name, days, age, mirror=False, stale=False):
    forget()
    with tempfile.TemporaryDirectory(prefix='review16-retention-') as temp:
        root = Path(temp)
        variables = FileVariables(str(root/'variables'))
        objects = FsObjectStore(str(root/'objects'))
        variables.put('other/retention', {'days': str(days)})
        variables.put('other/alarms_retention', {'days': str(days)})
        if stale:
            variables.put('other/retention/7', {'days': '0'})
            variables.put('other/alarms_retention/7', {'days': '0'})
        tree = root/'events'
        event_tree = tree/MIRROR_DIR/'peer-1' if mirror else tree
        log = EventLog(str(event_tree), 'other', '7', 1)
        event = Path(log.append(NOW-age*DAY, 'observation', 'observation'))
        alarm = Path(log.append(NOW-age*DAY, 'alarm', ALARM))
        mark = Path(EventLog(str(tree), 'console', 'operator-1', 1).append(
            NOW-age*DAY, 'mark', 'observation', of='other/7', user='anna', note='Проверено оператором'))
        resource = Resource(str(tree), 'srv-a', 'http://srv-a', variables, objects,
                            wall=lambda: NOW, clock=lambda: 1000.0)
        removed = resource.retain()
        out = {'scenario':name, 'removed':removed, 'events_left':event.exists(),
               'alarms_left':alarm.exists(), 'operator_record_left':mark.exists(),
               'garbled':resource.retention_garbled, 'bad_policy_keys':sorted(RETENTION.bad)}
        print(json.dumps(out, sort_keys=True), flush=True)

for name,days,age,mirror,stale in [
    ('valid-common', 2200, 1500, False, False),
    ('invalid-common', 'broken', 1500, False, False),
    ('zero-common', 0, 1500, False, False),
    ('mirror-only-valid', 2200, 1500, True, False),
    ('stale-unit-rows', 2200, 1500, False, True),
    ('expired-common', 1, 5, False, False),
]:
    scenario(name,days,age,mirror,stale)
