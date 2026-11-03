"""Public runner boundaries: actual main/finalize/coverage and bridge/object command; CT103, no SUT."""
import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import sys
import tempfile
from types import MethodType, SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(sys.argv[1]) / 'runner'))
import assembly
import c_execute
import c_store
import c_targets
import diagnostic_secrets
import m11stand
import stand
import tls_stage

SPEC = Path(sys.argv[2]); OUT = Path(os.environ['CHECK_OUT'])
PIN = (Path(sys.argv[1]) / 'SPEC_VERSION').read_text().strip()
REAL_DIRECTIVE = m11stand.Run.directive
result = {}

with tempfile.TemporaryDirectory(prefix='rv-r4-boundary-') as directory:
    root = Path(directory)
    marker = root / 'marker.py'
    marker.write_text('import json,sys\nfrom pathlib import Path\n'
        'r=dict(kind=sys.argv[2],key=sys.argv[3])\n'
        'if len(sys.argv)>4:r.update(file=sys.argv[4],exists=Path(sys.argv[4]).is_file())\n'
        'with Path(sys.argv[1]).open("a") as f:f.write(json.dumps(r)+"\\n")\n')
    marked = root / 'marker.jsonl'
    profiles = {owner: dict(cwd=str(root), keys={'role': 'acc'}, stand={}, adapters={}, vectors={}) for owner in assembly.MODULES}
    for target in c_targets.CONNECTED_TARGETS:
        for owner, group, key in (*target.requires, *target.requires_any):
            if group: profiles[owner][group][key] = 'NEVER-EXECUTE'
    profiles['03-worker']['stand']['worker'] = 'AGENT_TOKEN_DIR={agent_tokens} NEVER-EXECUTE'
    profiles['09-agent']['stand']['agent'] = 'AGENT_TOKEN_DIR={agent_tokens} NEVER-EXECUTE'
    profiles['09-agent']['stand']['token-door'] = 'unix:{agent_tokens}/{role}.sock'
    for key in ('object-put', 'object-spoil'):
        profiles['05-resource']['stand'][key] = ' '.join(map(shlex.quote, (sys.executable, '-I', '-B', str(marker), str(marked), key))) + ' {key}' + (' {file}' if key == 'object-put' else '')
    composition = SimpleNamespace(parts={owner: SimpleNamespace(doc=doc) for owner,doc in profiles.items()}, specs=SPEC, spec_version=PIN)

    class PassRun:
        def __init__(self, a, name, **kw): self.name, self.last_transport = name, None
        def step(self, *args): return [], None
        def close(self): pass

    names = {}
    for target_id, required in [('P/09.1/stand', '17-token-wait'), ('P/08.7/stand', '01-token-and-audience')]:
        target = next(t for t in c_targets.DOMAIN_TARGETS if t.id == target_id)
        plan = c_targets.plan(composition, [target_id])[0]
        output = root / (target.driver + '.json')
        _, args = c_store.chapter_arguments(target.driver, profiles, SPEC, output)
        with patch.object(m11stand, 'Run', PassRun), contextlib.redirect_stdout(io.StringIO()):
            code = m11stand.main(args)
        report = json.loads(output.read_text())
        coverage = c_execute.coverage(plan, report)
        names[target_id] = dict(safety_pass=code == 0 and required in report['scenarios'] and not coverage['errors'],
            code=code, required=required, actual_names=list(report['scenarios']), coverage_errors=coverage['errors'],
            total=report['total_steps'], reported=sum(len(rows) for rows in report['scenarios'].values()))
    result['names_main_finalize_coverage'] = names

    # Execute every actual published object directive through chapter_arguments -> main -> Run.directive -> Stand.object_directive.
    objects = {}
    for target in c_targets.DOMAIN_TARGETS:
        source = SPEC / target.sources[0]; used = []
        for line in source.read_text().splitlines():
            if not line.strip() or line.startswith(('#', 'scenario\t')): continue
            cells = line.split('\t'); req = cells[2]
            if re.search(r'(?:^|\s)@(put|spoil) object(?:\s|$)', req): used.append(cells)
        expected = {('object-put' if '@put object' in row[2] else 'object-spoil') for row in used}
        declared = {key for owner, group, key in target.requires if owner == '05-resource' and key.startswith('object-')}
        if not used:
            assert not declared
            continue
        fixture = root / ('fixture-' + target.driver); fixture.mkdir()
        if (source.parent / 'inputs').exists(): shutil.copytree(source.parent / 'inputs', fixture / 'inputs')
        (fixture / 'scenarios.tsv').write_text('scenario\tstep\trequest\texpect\n' + ''.join('\t'.join(row) + '\n' for row in used))
        output = fixture / 'report.json'
        _, args = c_store.chapter_arguments(target.driver, profiles, SPEC, output)
        seen = []
        class ObjectRun(PassRun):
            def __init__(self, a, name, **kw):
                super().__init__(a, name, **kw)
                self.a, self.env = a, {}
                def make():
                    st = SimpleNamespace(a=a, fmt=lambda template, **extra: template.format(**extra))
                    st.object_directive = MethodType(stand.Stand.object_directive, st)
                    return st
                self.b = SimpleNamespace(clusters={name: make() for name in ('hold','m1','m2','relay')})
                seen.append({key: getattr(a, key.replace('-', '_'), None) is not None for key in ('object-put','object-spoil')})
            def bench(self): return self.b
            def step(self, step, request, expect): return REAL_DIRECTIVE(self, request, expect), None
        before = len(marked.read_text().splitlines()) if marked.exists() else 0
        with patch.object(m11stand, 'Run', ObjectRun), patch.object(m11stand.specs, 'acceptance', return_value=str(fixture)), contextlib.redirect_stdout(io.StringIO()):
            code = m11stand.main(args)
        rows = [json.loads(line) for line in marked.read_text().splitlines()[before:]] if marked.exists() else []
        report = json.loads(output.read_text())
        objects[target.id] = dict(safety_pass=declared == expected and code == 0 and len(rows) == len(used)
            and all(row.get('exists',True) for row in rows), expected=sorted(expected), declared=sorted(declared),
            passed=report['passed_steps'], total=len(used), actual_commands=rows, bridge_arguments=seen)
    result['object_commands'] = objects

    # Independent faults outside the inner step try. Every bad scenario must survive with runner class; next one must run.
    faults = {}
    for mode in ('constructor', 'bind', 'transport_evidence', 'close', 'clean'):
        fixture = root / ('fault-' + mode); fixture.mkdir()
        (fixture / 'scenarios.tsv').write_text('scenario\tstep\trequest\texpect\nbad\t1\tholder GET /domain\t200 {}\n'
            'bad\t2\tholder GET /domain\t200 {}\ngood\t1\tholder GET /domain\t200 {}\n')
        class FaultRun(PassRun):
            def __init__(self, a, name, **kw):
                if mode == 'constructor' and name == 'bad': raise RuntimeError('owned constructor fault')
                super().__init__(a,name,**kw)
            def step(self, *args):
                if mode == 'transport_evidence' and self.name == 'bad': self.last_transport = RuntimeError('owned transport')
                return [], {'owned_clean_fault':True} if mode == 'clean' and self.name == 'bad' else None
            def transport_failure(self,*args): raise OSError('owned evidence fault')
            def close(self):
                if mode == 'close' and self.name == 'bad': raise OSError('owned close fault')
        real_bind, real_clean = m11stand.bind_control, diagnostic_secrets.Secrets.clean
        def binding(run,*args):
            if mode == 'bind' and run.name == 'bad': raise RuntimeError('owned bind fault')
            return real_bind(run,*args)
        def cleaning(registry,value,*args,**kwargs):
            if mode == 'clean' and isinstance(value,list) and any(isinstance(x,dict) and x.get('got') == {'owned_clean_fault':True} for x in value):
                raise TypeError('owned clean fault')
            return real_clean(registry,value,*args,**kwargs)
        output = fixture / 'report.json'; target = next(t for t in c_targets.DOMAIN_TARGETS if t.id == 'P/08.3/stand')
        _, args = c_store.chapter_arguments(target.driver, profiles, SPEC, output)
        error, code = None, None
        with patch.object(m11stand, 'Run', FaultRun), patch.object(m11stand.specs, 'acceptance', return_value=str(fixture)), \
             patch.object(m11stand, 'bind_control', binding), patch.object(diagnostic_secrets.Secrets, 'clean', cleaning), contextlib.redirect_stdout(io.StringIO()):
            try: code = m11stand.main(args)
            except Exception as caught: error = type(caught).__name__
        report = json.loads(output.read_text()) if output.exists() else None
        faults[mode] = dict(safety_pass=report is not None and code == 1 and c_execute.classification(report,code,False) == 'runner'
            and len(report['scenarios']['bad']) == 2 and report['scenarios']['good'][0]['ok'], code=code, error=error,
            report=report)
    result['outside_faults'] = faults

    # Explicit TLS reporting, real finalize; also retain the pre-existing ancillary aborted-name limitation as observation.
    cases = [('01-token-good',lambda c:c.value('check',True,True)), ('02-broken-token',lambda c:c.value('check',False,True)),
             ('03-plain',lambda c:c.value('check',True,True))]
    output = root / 'tls.json'
    with patch.object(tls_stage, 'cases', return_value=cases), contextlib.redirect_stdout(io.StringIO()):
        code = tls_stage.main(argparse.Namespace(tls_suite='TLS',only=[],json=str(output)), lambda a,name,**kw: PassRun(a,name))
    report = json.loads(output.read_text())
    result['tls_names'] = dict(safety_pass=list(report['scenarios']) == [name for name,_ in cases], code=code,
        names=list(report['scenarios']), aborted=report['aborted_scenarios'],
        ancillary_aborted_names_preserved=report['aborted_scenarios'] == ['02-broken-token'])

(OUT / 'boundary-controls.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({name: value for name,value in result.items() if name == 'tls_names'},ensure_ascii=False),flush=True)
