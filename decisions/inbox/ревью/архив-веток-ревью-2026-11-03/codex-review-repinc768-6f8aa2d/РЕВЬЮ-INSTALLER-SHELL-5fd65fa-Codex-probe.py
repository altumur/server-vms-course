"""Public shell fixture, quoted HTML boundaries and published console scenario IDs."""
import contextlib
from html.parser import HTMLParser
import io
import json
import os
from pathlib import Path
import shlex
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(sys.argv[1]) / 'runner'))
import c_installer as ci
import c_installer_data as data
import console
import harness

specs = Path(sys.argv[2])
new_specs = Path(sys.argv[3])
out = Path(os.environ['CHECK_OUT'])
results = {}
published = next(case for case in data.puts(specs, '3') if case['case'] == 'shell_onclick')
shell = (specs / data.ROOT / 'acceptance/3/puts/paged.shell.html').read_bytes()

with tempfile.TemporaryDirectory(prefix="rv-shell '") as directory:
    root = Path(directory)
    helper = root / 'cli.py'
    helper.write_text('''import json,pathlib,sys
p=pathlib.Path(sys.argv[1]);s=p.with_name("paged.shell.html")
with pathlib.Path(sys.argv[3]).open("a") as f:
 f.write(json.dumps(dict(path=str(p),yaml=p.read_text(),shell=s.read_text() if s.exists() else None))+"\\n")
if not s.exists():raise SystemExit(0)
named={"shell":s.name,"manifest":p.name,"missing":"unrelated.yaml"}[sys.argv[2]]
print(named+" refused onmouseover",file=sys.stderr)
raise SystemExit(2)
''')
    cases = [
        ('published-shell', shell, 'shell'),
        ('published-wrong-manifest', shell, 'manifest'),
        ('published-missing-name', shell, 'missing'),
        ('plain-value', b'<p title="onclick=">page</p>\n', 'manifest'),
        ('quoted-space', b'<p title="look onload=literal">page</p>\n', 'manifest'),
        ('comment', b'<!-- onload=literal -->\n<p>page</p>\n', 'manifest'),
        ('quoted-gt-handler', b'<p title=">" onload="hint()">page</p>\n', 'shell'),
    ]
    for label, body, named in cases:
        neutral = label in ('plain-value', 'quoted-space', 'comment')
        class Attributes(HTMLParser):
            def __init__(self):
                super().__init__()
                self.handlers = []
            def handle_starttag(self, tag, attrs):
                self.handlers.extend(key for key, value in attrs if key.startswith('on'))
        parsed = Attributes()
        parsed.feed(body.decode())
        assert bool(parsed.handlers) == (not neutral), (label, parsed.handlers)
        own_specs = root / label / 'specs'
        folder = own_specs / data.ROOT / 'acceptance/3/puts'
        folder.mkdir(parents=True)
        (folder / 'paged.subsystem.yaml').write_bytes(
            (specs / data.ROOT / 'acceptance/3/puts/paged.subsystem.yaml').read_bytes())
        (folder / 'paged.shell.html').write_bytes(body)
        # Give neutral HTML a separate valid reason to refuse: the final YAML
        # has a list instead of the required unit mapping. The shell stays valid.
        # This uses the same public puts grammar and the actual put_case path.
        if neutral:
            (folder / 'pagedbad.subsystem.yaml').write_bytes(b'name: paged\nunit: []\n')
        case = dict(published, tokens=['paged', '@shell-put', 'paged', 'pagedbad']) if neutral else published
        evidence = root / label / 'evidence'
        evidence.mkdir()
        log = root / label / 'native-input.jsonl'
        part = dict(cwd=str(root), keys={}, stand={
            'manifest-put': shlex.join([sys.executable, '-I', '-B', str(helper)])
                            + ' {file} ' + shlex.quote(named) + ' ' + shlex.quote(str(log))})
        row = SimpleNamespace(status=200, body=b'{"items":{"rev":"1"},"index":"9"}')
        instance = SimpleNamespace(socket='/unused/admin.sock',
                                   door=SimpleNamespace(admin=SimpleNamespace(request=lambda *args: row)),
                                   close=lambda: None)
        store = dict(cwd=str(root), stand={'store1': 'not-launched {data} {socket} {rights}'})
        with patch.object(harness, 'Instance', return_value=instance):
            errors = ci.put_case(case, part, store, own_specs, evidence)
        native = [json.loads(line) for line in log.read_text().splitlines()]
        assert len(native) == 2 and native[0]['shell'] is None and native[1]['shell'].encode() == body
        assert native[0]['yaml'].encode() == (folder / 'paged.subsystem.yaml').read_bytes()
        final = 'pagedbad' if neutral else 'paged'
        assert native[1]['yaml'].encode() == (folder / (final + '.subsystem.yaml')).read_bytes()
        expected_accepted = label not in ('published-wrong-manifest', 'published-missing-name')
        results[label] = dict(safety_pass=(not errors) == expected_accepted,
                              errors=errors, expected_accepted=expected_accepted,
                              html=body.decode(), stderr_name=named, native_launches=len(native),
                              parsed_handler_attributes=parsed.handlers, invalid_manifest=neutral)

    console_controls = {}
    allowed = {1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12, 18, 19, 20, 21, 22, 23}
    for label, pin in [('pinned', specs), ('bd32826', new_specs)]:
        folder = pin / 'Platform/06-console/acceptance/5'
        real = console.scenarios(folder)
        # Drive the real main/constructor boundary with the published identities;
        # processes and HTTP are outside this selection control.
        steps = {name: [(1, '1', '@control', 'ok')] for name in real}
        made = []
        def factory(args, subsystems, **kwargs):
            st = SimpleNamespace(directive=lambda *args: [], close=lambda: None)
            made.append(tuple(subsystems))
            return st
        with patch.object(console, 'scenarios', return_value=steps), \
                patch.object(console.stand, 'Stand', side_effect=factory), contextlib.redirect_stdout(io.StringIO()):
            code = console.main(['--store', 'unused', '--console', 'unused', '--lesson', 'P/06.5',
                                 '--acceptance', str(folder)])
        expected = tuple(str(p) for p in sorted(folder.glob('*.subsystem.yaml')))
        mismatch = []
        for name, subsystems in zip(real, made):
            want = ('testsub', 'testsub2') + (expected if int(name.split('-')[0]) in allowed else ())
            if subsystems != want:
                mismatch.append(dict(scenario=name, actual=subsystems, expected=want))
        console_controls[label] = dict(safety_pass=code == 0 and len(made) == len(real) and not mismatch,
                                        scenarios=len(real), mismatches=mismatch)

result = dict(shell=results, console=console_controls)
(out / 'controls.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(dict(shell={k: v['safety_pass'] for k, v in results.items()},
                      console={k: v['safety_pass'] for k, v in console_controls.items()})))
