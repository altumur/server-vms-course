"""Go adapter API of canonical P/06; inputs and expectations belong to the published wire form.

The five cells below select only package, table, surface, Go name and Go arguments. The shared expander
supplies the opaque Run objects used by the existing judges; no draft recipes are consulted.
"""
from collections import defaultdict

from wire import WireError
import wire_vectors


API_P06 = [
    ('01-store/jcs', 'canonical_json.tsv', 'vectors', 'JCS', 'cells'),
    ('06-console/contender-projection', 'cases.tsv', 'vectors', 'ContenderProjection', 'cells'),
    ('06-console/key-families', 'cases.tsv', 'vectors', 'KeyFamilies', 'cells'),
    ('06-console/metrics', 'cases.tsv', 'vectors', 'Metrics', 'cells'),
    ('06-console/op-step', 'expected.tsv', 'vectors', 'OpStep', 'cells'),
    ('06-console/op-step', 'key.tsv', 'vectors', 'OpStep', 'cells'),
    ('06-console/reap', 'cases.tsv', 'vectors', 'Reap', 'cells'),
    ('06-console/request-digest', 'digest.tsv', 'stand:request-digest', 'RequestDigest', 'input'),
    ('06-console/request-digest', 'digest.tsv', 'vectors', 'RequestDigestCells', 'cells'),
    ('06-console/resolve', 'cases.tsv', 'vectors', 'Resolve', 'cells'),
    ('06-console/rid', 'rid.tsv', 'stand:rid', 'Rid', 'input'),
    ('06-console/rid', 'rid.tsv', 'vectors', 'RidCells', 'cells'),
    ('06-console/rid', 'template.tsv', 'vectors', 'RidCells', 'cells'),
    ('common/agent-sig', 'cases.tsv', 'vectors', 'AgentSig', 'cells'),
    ('common/ask-sig', 'cases.tsv', 'vectors', 'AskSig', 'cells'),
    ('common/contender-fresh', 'fresh.tsv', 'vectors', 'ContenderFresh', 'cells'),
    ('common/deadline', 'cases.tsv', 'vectors', 'Deadline', 'cells'),
    ('common/domain-token', 'cases.tsv', 'vectors', 'DomainToken', 'cells'),
    ('common/door-token', 'issue.tsv', 'stand:door-token-issue', 'DoorTokenIssueStand', 'input'),
    ('common/door-token', 'issue.tsv', 'vectors', 'DoorTokenIssue', 'cells'),
    ('common/events-merge', 'cases.tsv', 'vectors', 'EventsMerge', 'cells'),
    ('common/fault', 'fault.tsv', 'stand:fault', 'FaultStand', 'input'),
    ('common/fault', 'fault.tsv', 'vectors', 'Fault', 'cells'),
    ('common/fresh-age', 'fresh.tsv', 'stand:fresh-age', 'FreshAgeStand', 'input'),
    ('common/fresh-age', 'fresh.tsv', 'vectors', 'FreshAge', 'cells'),
    ('common/group-of', 'cases.tsv', 'vectors', 'GroupOf', 'input'),
    ('common/heartbeat-read', 'cases.tsv', 'vectors', 'HeartbeatRead', 'cells'),
    ('common/heartbeat-read', 'worker.tsv', 'vectors', 'HeartbeatRead', 'cells'),
    ('common/hold-state', 'cases.tsv', 'vectors', 'HoldState', 'cells'),
    ('common/instance', 'box.tsv', 'vectors', 'Instance', 'cells'),
    ('common/instance', 'cases.tsv', 'vectors', 'Instance', 'cells'),
    ('common/journal', 'append.tsv', 'vectors', 'Journal', 'cells'),
    ('common/journal', 'names.tsv', 'vectors', 'Journal', 'cells'),
    ('common/journal', 'years.tsv', 'vectors', 'Journal', 'cells'),
    ('common/keys', 'cases.tsv', 'vectors', 'Keys', 'cells'),
    ('common/labels', 'cases.tsv', 'vectors', 'Labels', 'cells'),
    ('common/log-mask', 'mask_in.tsv', 'vectors', 'LogMaskIn', 'cells'),
    ('common/loopback', 'cases.tsv', 'vectors', 'Loopback', 'cells'),
    ('common/may', 'cases.tsv', 'vectors', 'May', 'cells'),
    ('common/may', 'covers.tsv', 'vectors', 'May', 'cells'),
    ('common/object-client', 'address.tsv', 'vectors', 'ObjectClient', 'cells'),
    ('common/object-client', 'read.tsv', 'vectors', 'ObjectClient', 'cells'),
    ('common/password-hash', 'cases.tsv', 'stand:password-hash', 'PasswordHash', 'input'),
    ('common/peer', 'cases.tsv', 'vectors', 'Peer', 'cells'),
    ('common/pool', 'cases.tsv', 'vectors', 'Pool', 'cells'),
    ('common/record', 'shared.tsv', 'vectors', 'Record', 'cells'),
    ('common/resource-state', 'cases.tsv', 'vectors', 'ResourceState', 'cells'),
    ('common/row-check', 'cases.tsv', 'vectors', 'RowCheck', 'cells'),
    ('common/row-check', 'state.tsv', 'vectors', 'RowCheck', 'cells'),
    ('common/said-id', 'read.tsv', 'stand:said-read', 'SaidRead', 'input'),
    ('common/said-id', 'said.tsv', 'stand:said-id', 'SaidID', 'input'),
    ('common/schema', 'cases.tsv', 'vectors', 'Schema', 'cells'),
    ('common/sealing', 'aad.tsv', 'vectors', 'Sealing', 'cells'),
    ('common/sealing', 'envelope.tsv', 'vectors', 'Sealing', 'cells'),
    ('common/sealing', 'open.tsv', 'vectors', 'Sealing', 'cells'),
    ('common/sealing', 'reseal.tsv', 'vectors', 'Sealing', 'cells'),
    ('common/sealing', 'ring.tsv', 'vectors', 'Sealing', 'cells'),
    ('common/secret-in', 'cases.tsv', 'vectors', 'SecretIn', 'cells'),
    ('common/slot-name', 'cases.tsv', 'vectors', 'SlotName', 'cells'),
    ('common/tombstone', 'cases.tsv', 'vectors', 'Tombstone', 'cells'),
    ('common/turn', 'cases.tsv', 'vectors', 'Turn', 'cells'),
    ('common/values-by-type', 'cases.tsv', 'vectors', 'ValuesByType', 'cells+variant'),
]


def declarations(root):
    """Select active API surfaces and forward shared expansion results to the lesson judges."""
    # Pre-C4 exports have no console assignment of turn. Once assigned, the
    # mapping remains mandatory: a missing binding must still fail closed.
    assigned = wire_vectors.wire.consumers(root).get(('common/turn', 'cases.tsv'), ())
    api = API_P06 if '06-console' in assigned else [row for row in API_P06 if row[:3] != ('common/turn', 'cases.tsv', 'vectors')]
    decls = wire_vectors.declarations(root, lesson='06-console', api=api)
    runs, excluded = wire_vectors.wire.expand(root, '06-console')
    selected, omitted = defaultdict(list), defaultdict(list)
    for run in runs:
        selected[run.binding.key].append(run)
    for item in excluded:
        omitted[item.binding.key].append(item)
    for d in decls:
        key = tuple(d[k] for k in ('package', 'table', 'surface'))
        d.update(_form=True, _runs=selected[key], _excluded=omitted[key])
    return decls
