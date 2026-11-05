"""Positive controls for generated wire tests: complete fixture answers, never an implementation algorithm.

Used only by judges. Expected fields, required schema fields and output assertions are combined; the resulting
complete answer is independently checked by jsonschema. Mutants are applied by the caller after this step.
"""
import copy
import json

import wire


def sample(schema):
    if not isinstance(schema, dict):
        return None
    if 'const' in schema:
        return copy.deepcopy(schema['const'])
    if schema.get('enum'):
        return copy.deepcopy(schema['enum'][0])
    kind = schema.get('type', 'object' if 'properties' in schema else 'null')
    if isinstance(kind, list):
        kind = kind[0]
    if kind == 'object':
        return {k: sample(schema.get('properties', {}).get(k, {})) for k in schema.get('required', [])}
    if kind == 'array':
        return [sample(schema.get('items', {})) for _ in range(schema.get('minItems', 0))]
    if kind == 'string':
        return 'fixture' * max(1, schema.get('minLength', 0))
    if kind in ('number', 'integer'):
        return schema.get('minimum', 0)
    if kind == 'boolean':
        return False
    return None


def complete(value, schema):
    value = copy.deepcopy(value)
    if isinstance(schema, dict) and isinstance(value, dict):
        for k in schema.get('required', []):
            if k not in value:
                value[k] = sample(schema.get('properties', {}).get(k, {}))
        for k, sub in schema.get('properties', {}).items():
            if k in value:
                value[k] = complete(value[k], sub)
    return value


def put(value, pointer, replacement=None, remove=False):
    parts = wire.pointer_tokens(pointer, 'fake', root=True)
    if not parts:
        return copy.deepcopy(replacement)
    here = value
    for i, k in enumerate(parts):
        last = i == len(parts)-1
        if isinstance(here, dict):
            if last:
                if remove:
                    here.pop(k, None)
                else:
                    here[k] = copy.deepcopy(replacement)
                return value
            if k not in here:
                if remove:
                    return value
                here[k] = [] if parts[i+1].isdigit() else {}
            here = here[k]
        elif isinstance(here, list) and k.isdigit():
            index = int(k)
            if remove and index >= len(here):
                return value
            while len(here) <= index:
                here.append({})
            if last:
                if remove:
                    here.pop(index)
                else:
                    here[index] = copy.deepcopy(replacement)
                return value
            here = here[index]
        else:
            if remove:
                return value
            raise AssertionError(f'cannot construct fake path {pointer}')
    return value


def native_value(run):
    if run.ignore_stdout or isinstance(run.value, bytes):
        return copy.deepcopy(run.value)
    schema = run.native.get('schema', {})
    alternatives = schema.get('oneOf', [schema]) if isinstance(schema, dict) else [schema]
    failures = []
    for choice in alternatives:
        value = complete(run.value, choice)
        for a in run.asserts:
            if a.test == 'absent':
                value = put(value, a.pointer, remove=True)
            elif a.test == 'prefix':
                value = put(value, a.pointer, a.value+'fixture')
            elif a.test == 'no-leak':
                try:
                    text = wire.at_pointer(value, a.pointer, 'fake') if a.pointer else value
                except wire.WireError:
                    text = None
                if not isinstance(text, str) or wire.leaks(text, a.value, a.min_bytes, a.whole):
                    value = put(value, a.pointer, '')
            else:
                expected = json.dumps(a.value, ensure_ascii=False) if a.decode == 'json' else a.value
                value = put(value, a.pointer, expected)
        try:
            wire.check_type(value, run.native, f'fake {run.identity}')
            return value
        except wire.WireError as exc:
            failures.append(str(exc))
    raise AssertionError('\n'.join(failures))
