"""Independent schema-path/late-credential regression, executed only through CT103."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(sys.argv[1]) / 'runner'))
import diagnostic_secrets as ds
import judge_diagnostics as jd
import openapi
import prepare
import specs

results = []
for schema in ({'additionalProperties': False},
               {'unevaluatedProperties': False},
               {'propertyNames': {'pattern': '^accepted$'}},
               {'additionalProperties': {'type': 'integer'}}):
    registry = ds.Secrets()
    jd.configure(registry, specs.root(), specs.acceptance('P/09.1'))
    # A real published enum, without injecting anything into the dictionary.
    credential = 'unavailable'
    assert credential in registry.public_words
    raw = {credential: 'private-not-an-integer'}
    unchanged = copy.deepcopy(raw)
    errors = openapi.validate(schema, raw, {}, 'body')
    assert errors and raw == unchanged
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        path = root / 'report.json'
        safe = registry.clean({'why': errors, 'got': raw})
        prepare.write(path, safe)
        registry.written(path)
        early = json.loads(path.read_text())
        # Simulate a later successful login/where response teaching the same run a credential.
        registry.learn({'token': credential})
        controls = []
        for _ in range(2):
            registry.finalize([root])
            final = json.loads(path.read_text())
            controls.append({
                'raw_credential_in_path': any(credential in e.get('path', '') for e in final['why'] if isinstance(e, dict)),
                'raw_credential_in_field': any(credential in e.get('field', '') for e in final['why'] if isinstance(e, dict)),
                'got_key_redacted': credential not in json.dumps(final['got']),
                'nearby_keys_redacted': all(credential not in json.dumps(e.get('nearby_keys', [])) for e in final['why'] if isinstance(e, dict)),
                'file_trusted': path.resolve() in registry.own_files,
            })
        results.append(dict(schema=schema, initial_typed=isinstance(errors[0], jd.Mismatch),
                            raw_unchanged=raw == unchanged, finalizes=controls))

# Unknown and already-known dynamic keys must still be hidden at first render.
first_render = []
for key, known in [('private-unpublished-key', False), ('unavailable', True)]:
    registry = ds.Secrets()
    jd.configure(registry, specs.root(), specs.acceptance('P/09.1'))
    if known:
        registry.remember(key)
    safe = registry.clean({'why': openapi.validate({'additionalProperties': False}, {key: 0}, {}, 'body')})
    encoded = json.dumps(safe)
    first_render.append(key not in encoded)

audit = dict(cases=results, initial_unknown_and_known_hidden=all(first_render), SUT=0)
Path(sys.argv[2]).write_text(json.dumps(audit, indent=2) + '\n')
print(json.dumps(audit))
assert all(first_render)
assert all(not c['raw_credential_in_path'] and not c['raw_credential_in_field']
           for row in results for c in row['finalizes']), 'late credential remains in structured response-key path'
