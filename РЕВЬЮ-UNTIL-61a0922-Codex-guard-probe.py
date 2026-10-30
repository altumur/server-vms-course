"""Independent schema-name and serialized-pointer controls; CT103 only, no SUT."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(sys.argv[1]) / 'runner'))
import diagnostic_secrets as ds
import judge_diagnostics as jd
import openapi
import prepare
import specs

controls = {}
placeholder = lambda s: '<key len=%d sha256=%s>' % (len(s.encode()), hashlib.sha256(s.encode()).hexdigest())

# A received key is never promoted merely because its bytes match a public enum.
for key in ('unavailable', 'é\n/~private'):
    registry = ds.Secrets()
    jd.configure(registry, specs.root(), specs.acceptance('P/09.1'))
    schema = {'properties': {'outer': {'propertyNames': {'pattern': '^accepted$'}, 'additionalProperties': False}}}
    raw = {'outer': {key: False}}
    original = copy.deepcopy(raw)
    safe = registry.clean({'why': openapi.validate(schema, raw, {}, 'body'), 'got': raw})
    assert raw == original
    assert len(safe['why']) == 2
    expected_path = '/outer/' + placeholder(key)
    assert all(error['path'] == expected_path for error in safe['why'])
    assert 'value' not in safe['why'][0]['received']  # propertyNames receives the raw key.
    assert safe['why'][1]['nearby_keys'] == [placeholder(key)]
    assert key not in json.dumps(safe, ensure_ascii=False)
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / 'report.json'
        prepare.write(path, safe); registry.written(path)
        initial = path.read_bytes()
        registry.finalize([path]); once = path.read_bytes()
        registry.finalize([path]); twice = path.read_bytes()
        assert initial == once == twice
controls['dynamic_public_and_unicode_keys_are_opaque_immediately'] = True
controls['propertyNames_received_never_exports_the_key'] = True
controls['placeholder_bytes_stable_across_two_finalizes'] = True

# Declared names preserve exact pointer segments and indices without becoming received values.
for key in ('a.b/c~d', 'é/零~.field'):
    registry = ds.Secrets()
    schema = {'properties': {key: {'type': 'array', 'items': {'properties': {'child': {'type': 'integer'}}}}}}
    raw = {key: [{'child': key}]}
    errors = openapi.validate(schema, raw, {}, 'body')
    safe = registry.clean({'why': errors})
    pointer = '/' + key.replace('~', '~0').replace('/', '~1') + '/0/child'
    assert safe['why'][0]['path'] == pointer
    assert key in registry.public_names and key not in registry.public_words
    assert 'value' not in jd.scalar(key, registry)
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / 'report.json'
        prepare.write(path, safe); registry.written(path)
        registry.finalize([path])
        assert json.loads(path.read_text())['why'][0]['path'] == pointer
        registry.learn({'token': key})
        for _ in range(2):
            registry.finalize([path]); final = json.loads(path.read_text())
            error = final['why'][0]
            assert error['path'] == '/' + placeholder(key) + '/0/child'
            assert key not in error['field']
            assert jd.valid(error)
controls['declared_unicode_dot_slash_tilde_names_and_indices_preserved'] = True
controls['declared_names_do_not_widen_received_values'] = True
controls['late_declared_name_rechecked_after_pointer_decode'] = True

# A stored alternative contains nested mismatch projections which must receive the same refresh.
registry = ds.Secrets()
key = 'a.b/c~d'
schema = {'anyOf': [{'properties': {key: {'type': 'integer'}}, 'required': [key]},
                    {'properties': {key: {'type': 'boolean'}}, 'required': [key]}]}
safe = registry.clean({'why': openapi.validate(schema, {key: 'private-value'}, {}, 'body')})
with tempfile.TemporaryDirectory() as td:
    path = Path(td) / 'report.json'
    prepare.write(path, safe); registry.written(path)
    registry.learn({'token': key})
    for _ in range(2):
        registry.finalize([path]); final = json.loads(path.read_text())
        children = [error for branch in final['why'][0]['branches'] for error in branch]
        assert len(children) == 2
        assert all(error['path'] == '/' + placeholder(key) and key not in error['field'] for error in children)
        assert all(jd.valid(error) for error in children)
controls['nested_alternative_paths_refresh_on_both_finalizes'] = True
print(json.dumps(controls))
