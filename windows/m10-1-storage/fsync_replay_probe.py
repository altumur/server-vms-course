"""Read-only fault injection into private temporary stores; exit 0 is NOT conformance.

Reproduce at Source3569935c; production source is never modified.
"""
from pathlib import Path
import json
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'Source'))
from w2cplatform.variables import FileVariables

for operation in ('put', 'delete'):
    with tempfile.TemporaryDirectory() as root:
        store = FileVariables(root, volatile=False)
        cmd = {'op': operation, 'key': 'acc/row', 'id': 'e1'}
        if operation == 'delete':
            cmd['cas'] = store.put('acc/row', {'v': 'one'})
        else:
            cmd['items'] = {'v': 'one'}
        original = store._durable_dirs
        first = [True]
        def late_barrier():
            if first[0]:
                first[0] = False
                raise OSError('injected directory fsync failure after row publication')
            original()
        store._durable_dirs = late_barrier
        try:
            store.write(cmd)
        except Exception as error:
            print(json.dumps({'op': operation, 'first_error': type(error).__name__,
                              'visible_after_error': store.get('acc/row')}))
        try:
            receipt = store.write(cmd)
            print(json.dumps({'op': operation, 'same_id_retry': receipt,
                              'visible_after_retry': store.get('acc/row')}))
        except Exception as error:
            print(json.dumps({'op': operation, 'same_id_retry_error': type(error).__name__,
                              'index': getattr(error, 'index', None),
                              'visible_after_retry': store.get('acc/row')}))
