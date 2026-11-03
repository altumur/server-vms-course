"""Unexpected step error must preserve chapter output and reach c_execute as runner; CT103."""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
sys.path.insert(0, str(Path(sys.argv[1]) / 'runner'))
import c_execute
import m11stand
import diagnostic_secrets

identity = {'16-plain': [{'ok': True}], '17-token-wait': [{'ok': True}], '01-token-and-audience': [{'ok': True}]}
raw = diagnostic_secrets.Secrets().clean(identity)
wrapped = diagnostic_secrets.Secrets().clean({'scenarios': identity})['scenarios']
(Path(os.environ['CHECK_OUT']) / 'identity.json').write_text(json.dumps(dict(raw_keys=list(raw), wrapped_keys=list(wrapped),
    safety_pass=set(raw) == set(identity)), indent=2) + '\n')

class Run:
    def __init__(self, args, name, **kwargs): self.name, self.last_transport = name, None
    def step(self, step, req, expect):
        if self.name == '01-error': raise KeyError('relay')
        return [], None
    def close(self): pass

args = []
for role in ('store', 'console', 'controller', 'resource', 'spec-put', 'rights', 'ring', *m11stand.ROLES):
    args += ['--' + role, 'fixture']
args += ['--worker', 'AGENT_TOKEN_DIR={agent_tokens} fixture']
args[args.index('--agent') + 1] = 'AGENT_TOKEN_DIR={agent_tokens} fixture'
args[args.index('--token-door') + 1] = 'unix:{agent_tokens}/{role}.sock'
with tempfile.TemporaryDirectory() as folder:
    root = Path(folder); output = root / 'report.json'
    (root / 'scenarios.tsv').write_text('scenario\tstep\trequest\texpect\n01-error\t1\t@domain m1 relay\tok\n'
        '01-error\t2\tholder GET /domain\t200 {}\n02-good\t1\tholder GET /domain\t200 {}\n')
    error, code, report = None, None, None
    with patch.object(m11stand, 'Run', Run), patch.object(m11stand.specs, 'acceptance', return_value=folder), contextlib.redirect_stdout(io.StringIO()):
        try: code = m11stand.main(args + ['--lesson', 'P/08.3', '--json', str(output)])
        except KeyError as caught: error = repr(caught)
    if output.exists(): report = json.loads(output.read_text())
    result = dict(error=error, code=code, report_exists=output.exists(), report=report,
                  safety_pass=report is not None and code == 1 and c_execute.classification(report, code, False) == 'runner'
                  and len(report['scenarios']['01-error']) == 2 and report['scenarios']['02-good'][0]['ok'])
(Path(os.environ['CHECK_OUT']) / 'exceptions.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result), flush=True)
