#!/usr/bin/env python3
"""Independent positive checks of camera lifecycle, removed YAML, and held events."""
import argparse
import copy
import json
import os
import sys
import tempfile
from pathlib import Path

import yaml

parser = argparse.ArgumentParser()
parser.add_argument('source')
source = Path(parser.parse_args().source).resolve()
sys.path.insert(0, str(source))
os.environ.setdefault('STORE_VOLATILE', '1')
from vms.controller import VmsController
from w2cplatform.events import EventLog, ALARM
from w2cplatform.memvariables import MemVariables
from w2cplatform.objects import FsObjectStore
from w2cplatform.resource import Resource
from w2cplatform.spec import SubsystemSpec, Refused

NOW = 1757500000.0
with tempfile.TemporaryDirectory(prefix='review16-contract-') as temp:
    root = Path(temp)
    variables = MemVariables()
    objects = FsObjectStore(str(root / 'objects'))
    variables.put('vms/retention', {'days': '120'})
    variables.put('vms/alarms_retention', {'days': '180'})
    before = {key: variables.get(key) for key in ('vms/retention', 'vms/alarms_retention')}
    ctl = VmsController(variables, objects, wall=lambda: NOW)
    row = ctl.create_camera({'name': 'gate', 'source': 'driverpack://file/gate.mp4'})
    rejected = []
    for field in ('events_retention_days', 'alarms_retention_days'):
        try:
            ctl.update_camera(row['id'], {field: 7})
        except Refused:
            rejected.append(field)
    ctl.delete_camera(row['id'])
    ctl.delete_camera(row['id'])
    after = {key: variables.get(key) for key in before}
    print(json.dumps({'scenario': 'camera-lifecycle', 'common_rows_and_versions_unchanged': before == after,
                      'removed_fields_refused': rejected,
                      'individual_rows': variables.list('vms/retention/') + variables.list('vms/alarms_retention/')}, sort_keys=True))

    raw = yaml.safe_load((source / 'tests/testdata/testsub.subsystem.yaml').read_text())
    raw['placement'].pop('unplaced', None)
    raw['unit']['derived'] = [{'row': 'retention/{id}', 'items': {'days': 'step'}, 'on_delete': {'days': 0}}]
    try:
        SubsystemSpec.from_dict(copy.deepcopy(raw))
        refusal = None
    except ValueError as exc:
        refusal = str(exc)
    print(json.dumps({'scenario': 'old-derived-yaml', 'refused': refusal is not None, 'reason': refusal}, sort_keys=True))

    holding = SubsystemSpec.from_dict({
        'name': 'other', 'unit': {'rows': 'units', 'id': 'numeric', 'fields': {}},
        'placement': {'capacity': {'from': 'capacity', 'default': 4}},
        'tables': {'pins': {'key': 'name', 'fields': {
            'name': {'type': 'string', 'required': True}, 'unit': {'type': 'string'},
            'a': {'type': 'float'}, 'b': {'type': 'float'}, 'released_at': {'type': 'string'}}}},
        'holds': {'table': 'pins', 'unit': 'unit', 'since': 'a', 'until': 'b', 'released': 'released_at'},
    })
    for family in ('retention', 'alarms_retention'):
        variables.put('other/' + family, {'days': '1'})
    pin = {'name': 'pin-1', 'unit': '7', 'a': str(NOW - 6 * 86400), 'b': str(NOW - 4 * 86400)}
    variables.put('other/pins/pin-1', pin)
    tree = root / 'events'
    log = EventLog(str(tree), 'other', '7', 1)
    paths = [Path(log.append(NOW - 5 * 86400, 'observation', 'observation')),
             Path(log.append(NOW - 5 * 86400, 'alarm', ALARM))]
    res = Resource(str(tree), 'srv-a', 'http://srv-a', variables, objects, wall=lambda: NOW, specs=[holding])
    res.retain()
    held = all(path.exists() for path in paths)
    variables.put('other/pins/pin-1', {**pin, 'released_at': str(NOW)})
    res.retain()
    print(json.dumps({'scenario': 'holds-and-release', 'held_events_and_alarms_survive': held,
                      'released_events_and_alarms_removed': all(not path.exists() for path in paths)}, sort_keys=True))
