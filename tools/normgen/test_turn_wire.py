"""C4: approved form, actual Go comparisons and ordinary Turn, independently judged.

The pinned Architect function is a judge oracle only. The native adapter never
receives expected actions. Build errors, panic and skipped tests are not kills.
"""
import ast
import base64
import copy
import dataclasses
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import wire
import wire_fakes
import wire_vectors
import gen_vectors

GOENV = dict(os.environ, GOFLAGS='-mod=mod', GOPROXY='off', GOWORK='off', GOTOOLCHAIN='local')
ORACLE_SHA = 'ae1e09603b580c8c3c333caf3edbdeb554c6c00895bb7e4aec35eb32c144f737'
OLD_SHA = 'ea768f504ed1f221b7b901ba2e7cef1002b2ad05116801475aeeca28f9156526'
TABLE = ROOT / 'Platform/common/vectors/turn/cases.tsv'


def oracle():
    source = (ROOT / 'skills/lesson-spec/scripts/check_forms.py').read_text()
    node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == 'turn_match')
    if hashlib.sha256(ast.get_source_segment(source, node).encode()).hexdigest() != ORACLE_SHA:
        raise AssertionError('turn_match differs from approved ce38b634; review the oracle pin')
    scope = {'TURN_MARKS': ('@new', '@same')}
    exec(compile(ast.Module(body=[node], type_ignores=[]), 'Architect ce38b634 turn_match', 'exec'), scope)
    return scope['turn_match']


def binding():
    return next(b for b in wire.parse(ROOT, keys={('common/turn', 'cases.tsv')}, surfaces={'vectors'})
                if b.key == wire.TURN_BINDING)


def cases():
    return [(r['case'], r['input'], wire.strict_json(r['expect'], r['case']))
            for _, r in wire.read_rows(ROOT, binding())]


def record(name, value):
    folder = Path(os.environ.get('C4_EVIDENCE_DIR', HERE / '__pycache__/c4-turn-evidence'))
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


class Form(unittest.TestCase):
    def test_exact_old_prefix_and_owner_rosters(self):
        self.assertEqual(hashlib.sha256(TABLE.read_bytes()[:12862]).hexdigest(), OLD_SHA)
        b, ex = binding(), wire.Expander(ROOT)
        counts = {'04-controller': (20, 29, 'placement'), '06-console': (16, 33, 'operations'),
                  '08-domain': (13, 36, 'signer'), '09-agent': (13, 36, 'signer')}
        for owner, (count, omitted, kind) in counts.items():
            runs, excluded = ex.run(b, owner)
            self.assertEqual((len(runs), len(excluded)), (count, omitted), owner)
            self.assertTrue(all(json.loads(r.cells['input'])['kind'] == kind for r in runs))
            self.assertEqual({r.case for r in runs}, {c for c, raw, _ in cases() if json.loads(raw)['kind'] == kind})
        self.assertFalse(any(b.key == wire.TURN_BINDING for b in wire.lesson_bindings(ROOT, '02-installer')))

    def test_narrow_binding_and_no_assert_or_marker_alias(self):
        b = binding()
        bad = [dataclasses.replace(b, package='common/pool'), dataclasses.replace(b, surface='stand:turn'),
               dataclasses.replace(b, inputs=[dict(b.inputs[0], when=None)]),
               dataclasses.replace(b, inputs=[{k: v for k, v in b.inputs[0].items() if k != 'when'}])]
        for key in ('ignore', 'assert'):
            bad.append(dataclasses.replace(b, expect=[dict(b.expect[0], **{key: []})]))
        for value in ({'literal': []}, {'column': 'expect', 'decode': 'text'},
                      {'array': [{'literal': '@new'}]}):
            bad.append(dataclasses.replace(b, expect=[dict(b.expect[0], value=value)]))
        marker = {'variant': '', 'column': 'case', 'match': 'operations', 'compare': 'turn'}
        bad.append(dataclasses.replace(b, compare='value', markers=[marker]))
        bad.append(dataclasses.replace(b, markers=[dict(marker, compare='value')]))
        assertion = {'pointer': '', 'value': {'column': 'expect', 'decode': 'json'}, 'compare': 'turn'}
        bad.append(dataclasses.replace(b, compare='value', expect=[dict(b.expect[0], **{'assert': [assertion]})]))
        for i, item in enumerate(bad):
            with self.subTest(i=i), self.assertRaises(wire.WireError):
                wire.check_binding(ROOT, item, 'C4 negative form')

    def test_bad_foreign_rows_are_form_errors_before_selection(self):
        b = binding()
        for input_, expected in [('not JSON', []), ('{"kind":"unknown"}', []),
                                 ('{"kind":"signer"}', [{'write': {'holder': '@same'}, 'cas': ''}]),
                                 ('{"kind":"signer"}', [{'x': '@new'}]),
                                 ('{"kind":"signer"}', [{'write': {'holder': '@alias'}}]),
                                 ('{"kind":"signer"}', {})]:
            with self.subTest(input=input_, expected=expected), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                folder = root / 'Platform/common/vectors/turn'
                folder.mkdir(parents=True)
                shutil.copyfile(TABLE.with_name('README.md'), folder / 'README.md')
                (folder / 'cases.tsv').write_text('case\tinput\texpect\tnote\nforeign\t' + input_ + '\t' +
                                                  json.dumps(expected) + '\tnegative\n')
                with self.assertRaises(wire.WireError):
                    wire.check_binding(root, b, 'C4 foreign negative')

    def test_judge_positive_control_has_real_labels_without_mutating_expect(self):
        match = oracle()
        runs, _ = wire.Expander(ROOT).run(binding(), '06-console')
        for run in runs:
            original = copy.deepcopy(run.value)
            actual = wire_fakes.native_value(run)
            self.assertEqual(match(run.value, actual), [], run.case)
            self.assertEqual(run.value, original)

    def test_api_turn_optional_only_when_legacy_source_did_not_assign_it(self):
        import wire_api_p06
        assigned = copy.deepcopy(wire.consumers(ROOT))
        assigned['common/turn', 'cases.tsv'].remove('06-console')
        with patch.object(wire, 'consumers', return_value=assigned):
            self.assertFalse(any(d['fn'] == 'Turn' for d in wire_api_p06.declarations(ROOT)))
        bindings = wire.parse(ROOT)
        with patch.object(wire, 'parse', return_value=[b for b in bindings if b.key != wire.TURN_BINDING]):
            with self.assertRaisesRegex(wire.WireError, 'binding|consumers'):
                wire_api_p06.declarations(ROOT)


DRIVER = r'''package main
import (
 "bufio"; "encoding/base64"; "encoding/json"; "fmt"; "os"; "sync"
 full "turnprobe/full"
 legacy "turnprobe/legacy"
 "turnprobe/vectoradapter"
)
type request struct { Mode string; Input string; Want json.RawMessage; Actual json.RawMessage; Raw string; N int }
func run(raw string) map[string]any {
 a:=vectoradapter.Turn("cases.tsv",map[string]string{"input":raw},map[string][]byte{})
 return map[string]any{"code":a.Code,"value":a.Value}
}
func handle(r request) (out any) {
 defer func(){if p:=recover();p!=nil {out=map[string]any{"panic":fmt.Sprint(p)}}}()
 switch r.Mode {
 case "run": return run(r.Input)
 case "race":
  out:=make([]map[string]any,r.N);var wg sync.WaitGroup
  for i:=range out {wg.Add(1);go func(i int){defer wg.Done();out[i]=run(r.Input)}(i)}
  wg.Wait();return out
 case "compare":
  actual:=[]byte(r.Actual)
  if r.Raw!="" {var e error;actual,e=base64.StdEncoding.DecodeString(r.Raw);if e!=nil {panic(e)}}
  spec:=fmt.Sprintf("{\"code\":0,\"value\":%s,\"compare\":\"turn\",\"native\":{\"type\":\"array\",\"frame\":\"json\"}}",r.Want)
  return map[string]bool{"full":full.Check(0,actual,spec)==nil,"legacy":legacy.Check(0,actual,spec)==nil}
 }
 panic("unknown probe mode")
}
func main(){
 s:=bufio.NewScanner(os.Stdin);s.Buffer(make([]byte,4096),4<<20);e:=json.NewEncoder(os.Stdout)
 for s.Scan(){var r request;if err:=json.Unmarshal(s.Bytes(),&r);err!=nil {panic(err)};if err:=e.Encode(handle(r));err!=nil {panic(err)}}
 if err:=s.Err();err!=nil {panic(err)}
}
'''


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data.encode() if isinstance(data, str) else data)


class Probe:
    def __init__(self, root):
        self.root = root
        write(root / 'go.mod', 'module turnprobe\n\ngo 1.22\n')
        write(root / 'main.go', DRIVER)
        write(root / 'contracts/turn.go', (HERE / 'contracts/go/turn.go').read_bytes())
        write(root / 'vectoradapter/types.go', gen_vectors.TYPES_GO)
        adapter = (HERE / 'contracts/adapters/turn.go').read_text().replace('kitmodule/internal/contracts', 'turnprobe/contracts')
        write(root / 'vectoradapter/turn.go', adapter)
        env = type('Generator', (), {'HERE': HERE, 'gofmt': staticmethod(lambda text: text), 'GenError': RuntimeError})
        for full, name in [(False, 'legacy'), (True, 'full')]:
            for rel, content in wire_vectors.runtime_files(env, full=full).items():
                write(root / name / Path(rel).name, content)
        # Compile the actual legacy comparator, with its real normalizers. The
        # unused vectorcmd stub is only an import for other comparison helpers.
        write(root / 'vectorcmd/stub.go', 'package vectorcmd\nfunc Run([]byte)(int,[]byte,[]byte,error){panic("not used by comparator probe")}\n')
        write(root / 'draft/helpers_test.go', (gen_vectors.HELPERS % {'module': 'turnprobe'}).replace('package vectortests', 'package draft'))
        write(root / 'draft/compare_test.go', gen_vectors.COMPARE_GO.replace('package vectortests', 'package draft')
              .replace('normgen/vectoradapter', 'turnprobe/vectoradapter'))

    def compile(self, name='probe', race=False):
        args = ['go', 'build'] + (['-race'] if race else []) + ['-o', str(self.root / name), '.']
        done = subprocess.run(args, cwd=self.root, env=GOENV, capture_output=True, text=True)
        if done.returncode:
            raise AssertionError('compile failure, not a mutant kill:\n' + done.stdout + done.stderr)
        return self.root / name

    def call(self, requests, binary=None):
        data = ''.join(json.dumps(r, ensure_ascii=True) + '\n' for r in requests)
        done = subprocess.run([str(binary or self.root / 'probe')], input=data, cwd=self.root, env=GOENV,
                              capture_output=True, text=True)
        if done.returncode or 'panic:' in done.stderr or 'DATA RACE' in done.stderr:
            raise AssertionError('probe execution failure, not a kill:\n' + done.stdout + done.stderr)
        rows = [json.loads(line) for line in done.stdout.splitlines()]
        if len(rows) != len(requests) or any(isinstance(r, dict) and 'panic' in r for r in rows):
            raise AssertionError('probe did not execute every call without panic: ' + done.stdout)
        return rows

    def draft(self, corpus, raw=None):
        source = ['package draft\nimport("testing";"encoding/json";"strings";"turnprobe/vectoradapter")\n']
        for i, (want, actual) in enumerate(corpus):
            w, a = json.dumps(want), (raw or {}).get(i, json.dumps(actual))
            source.append('func TestTurnCase%04d(t *testing.T){var value any;dec:=json.NewDecoder(strings.NewReader(%s));'
                          'dec.UseNumber();if err:=dec.Decode(&value);err!=nil{t.Fatal(err)};'
                          'checkBy(t,"C4",func()vectoradapter.Answer{return vectoradapter.Answer{Value:value}},'
                          '0,%s,nil,"turn")}\n' % (i, json.dumps(a), json.dumps(w)))
        write(self.root / 'draft/corpus_test.go', ''.join(source))
        compile_ = subprocess.run(['go', 'test', '-run', '^$', './draft'], cwd=self.root, env=GOENV,
                                  capture_output=True, text=True)
        if compile_.returncode:
            raise AssertionError('legacy baseline compile failure:\n' + compile_.stdout + compile_.stderr)
        done = subprocess.run(['go', 'test', '-count=1', '-json', '-run', '^TestTurnCase', './draft'],
                              cwd=self.root, env=GOENV, capture_output=True, text=True)
        if 'panic:' in done.stdout + done.stderr:
            raise AssertionError('legacy panic, not a semantic result: ' + done.stdout + done.stderr)
        results = {}
        for line in done.stdout.splitlines():
            event = json.loads(line)
            if event.get('Test') and event.get('Action') in ('pass', 'fail', 'skip'):
                results[event['Test']] = event['Action']
        if len(results) != len(corpus) or 'skip' in results.values():
            raise AssertionError('legacy checks not all executed: ' + done.stdout + done.stderr)
        return [results['TestTurnCase%04d' % i] == 'pass' for i in range(len(corpus))]


def W(holder, cas):
    return {'write': {'holder': holder}, 'cas': cas}


def corpus():
    want = [W('@new', ''), 'held', W('@same', 1), 'held', W('', 2), 'done',
            W('@new', 3), 'held', W('@same', 4), 'stop']
    actual = [W('a1', ''), 'held', W('a1', 1), 'held', W('', 2), 'done',
              W('a2', 3), 'held', W('a2', 4), 'stop']
    rows = [(want, actual)]
    for label in ['', None, True, 7, '@new', '@same', '@literal']:
        bad = copy.deepcopy(actual); bad[0]['write']['holder'] = label; rows.append((want, bad))
    for i, label in [(6, 'a1'), (8, 'a1'), (2, 'renewed'), (4, 'a1')]:
        bad = copy.deepcopy(actual);bad[i]['write']['holder'] = label;rows.append((want, bad))
    for index, key, value in [(0, 'cas', 0), (2, 'cas', True), (6, 'extra', 1)]:
        bad = copy.deepcopy(actual);bad[index][key] = value;rows.append((want, bad))
    rows += [(want, actual[:-1]), (want, actual + ['extra']), (want, actual[::-1]),
             ([W('@new', '')], [W('@literal', '')]),
             ([W('@same', 1)], [W('unbound', 1)]),
             ([W('signer-instance', 2)], [W('signer-instance', 2.0)]),
             ([W('signer-instance', 2)], [W('other-instance', 2)]),
             ([W('@new', ''), 'not_held', W('@new', '')], [W('a1', ''), 'not_held', W('a1', '')]),
             ([W('@new', ''), W('@new', ''), W('@new', '')], [W('a1', ''), W('a2', ''), W('a1', '')]),
             ([{'guard': {'key': 'turn', 'index': 1}, 'nested': [True, {'x': 2}]}],
              [{'guard': {'key': 'turn', 'index': 1.0}, 'nested': [True, {'x': 2.0}]}]),
             ([{'guard': {'key': 'turn', 'index': 1}}], [{'guard': {'key': 'turn', 'index': True}}]),
             ([W('signer-instance', -0.0)], [W('signer-instance', 0)]),
             ([W('signer-instance', '1')], [W('signer-instance', 1)]),
             ([W('signer-instance', 9007199254740993)], [W('signer-instance', 9007199254740992)])]
    reused = copy.deepcopy(actual)
    reused[6]['write']['holder'] = reused[8]['write']['holder'] = 'a1'
    rows.append((want, reused))
    return rows


AST_AUDIT = r'''package main
import("bytes";"crypto/sha256";"encoding/hex";"encoding/json";"fmt";"go/ast";"go/parser";"go/printer";"go/scanner";"go/token";"os";"sort";"strconv")
func text(n ast.Node)string{var b bytes.Buffer;if e:=printer.Fprint(&b,token.NewFileSet(),n);e!=nil{panic(e)};return b.String()}
func digest(s string)string{fs:=token.NewFileSet();f:=fs.AddFile("body",-1,len(s));var scan scanner.Scanner;scan.Init(f,[]byte(s),nil,0);h:=sha256.New();for{_,t,l:=scan.Scan();if t==token.EOF{break};fmt.Fprintf(h,"%d\x00%s\x00",t,l)};return hex.EncodeToString(h.Sum(nil))}
func read(path string,wire bool)(map[string]string,map[string]bool){
 f,e:=parser.ParseFile(token.NewFileSet(),path,nil,0);if e!=nil{panic(e)};out:=map[string]string{};imports:=map[string]bool{}
 for _,i:=range f.Imports{s,e:=strconv.Unquote(i.Path.Value);if e!=nil{panic(e)};imports[s]=true}
 for _,d:=range f.Decls {fn,ok:=d.(*ast.FuncDecl);if !ok{continue};if fn.Name.Name=="checkBy"{ast.Inspect(fn,func(n ast.Node)bool{c,ok:=n.(*ast.CaseClause);if ok&&len(c.List)==1&&text(c.List[0])=="compare == \"turn\""{c.Body=nil};return true})};if wire&&fn.Name.Name=="compare"{ast.Inspect(fn,func(n ast.Node)bool{s,ok:=n.(*ast.SwitchStmt);if ok{kept:=[]ast.Stmt{};for _,node:=range s.Body.List{c:=node.(*ast.CaseClause);if len(c.List)!=1||text(c.List[0])!="\"turn\""{kept=append(kept,node)}};s.Body.List=kept};return true})};out[fn.Name.Name]=text(fn)}
 return out,imports
}
func main(){
 wire:=len(os.Args)>3&&os.Args[3]=="wire";before,bi:=read(os.Args[1],wire);after,ai:=read(os.Args[2],wire);unchanged:=[]string{};hashes:=map[string]string{}
 for name,body:=range before{if name=="turn"{continue};if body!=after[name]||digest(body)!=digest(after[name]){panic("unrelated AST/tokens changed: "+name)};unchanged=append(unchanged,name);hashes[name]=digest(body)}
 added:=[]string{};for i:=range ai{if !bi[i]{added=append(added,i)}};for i:=range bi{if !ai[i]{panic("removed import: "+i)}};sort.Strings(added)
 wantImports:="[io math/big]";if wire{wantImports="[]"};if fmt.Sprint(added)!=wantImports{panic("unexpected added imports: "+fmt.Sprint(added))}
 addedFns:=[]string{};for name:=range after{if _,has:=before[name];!has{addedFns=append(addedFns,name)}};sort.Strings(addedFns)
 wantFns:="[turnJSON turnSame]";if wire{wantFns="[turnEqual]"};if fmt.Sprint(addedFns)!=wantFns{panic("unexpected helper functions: "+fmt.Sprint(addedFns))};sort.Strings(unchanged)
 json.NewEncoder(os.Stdout).Encode(map[string]any{"unchanged_functions_and_nonturn_checkBy":unchanged,"token_sha256":hashes,"added_imports":added,"new_turn_helpers":addedFns})
}
'''


class Native(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='c4-turn-')
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.probe = Probe(Path(cls.tmp.name))
        cls.binary = cls.probe.compile()
        cls.match = staticmethod(oracle())

    def test_both_actual_matchers_follow_architect_oracle_and_reset(self):
        rows = corpus()
        wanted = [not self.match(w, a) for w, a in rows]
        requests = [{'Mode': 'compare', 'Want': w, 'Actual': a} for w, a in rows]
        got = self.probe.call(requests + requests)
        for name in ('full', 'legacy'):
            self.assertEqual([r[name] for r in got], wanted + wanted, name)
        record('matcher-parity.json', {'oracle_sha256': ORACLE_SHA, 'cases': len(rows), 'repeat': 2,
                                       'expected': wanted, 'actual': got})

    def test_actual_legacy_consumer_not_only_the_new_checker(self):
        rows = corpus()
        expected = [not self.match(w, a) for w, a in rows]
        actual = self.probe.draft(rows)
        record('draft-parity.json', {'expected': expected, 'actual': actual})
        self.assertEqual(actual, expected)

    def test_ast_and_tokens_of_other_comparisons_unchanged(self):
        old = subprocess.check_output(['git', 'show', '01c2ef53920042ff4313807b3d2ef48ed05baf27:tools/normgen/gen_vectors.py'], cwd=ROOT).decode()
        new = (HERE / 'gen_vectors.py').read_text()
        def unchanged(source):
            nodes = []
            for node in ast.parse(source).body:
                if isinstance(node, ast.FunctionDef) and node.name in ('provenance', 'lesson_kit_md'):
                    continue
                if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'COMPARE_GO' for t in node.targets):
                    continue
                nodes.append(node)
            return ast.dump(ast.Module(body=nodes, type_ignores=[]), include_attributes=False)
        self.assertEqual(unchanged(old), unchanged(new), 'Python outside the approved blocks changed')
        old_values = {n.targets[0].id: ast.literal_eval(n.value) for n in ast.parse(old).body
                      if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
                      and n.targets[0].id in ('COMPARE_GO', 'HELPERS')}
        self.assertEqual(old_values['HELPERS'], gen_vectors.HELPERS)
        before, after = self.probe.root / 'before.go.txt', self.probe.root / 'after.go.txt'
        write(before, old_values['COMPARE_GO']); write(after, gen_vectors.COMPARE_GO)
        write(self.probe.root / 'audit/main.go', AST_AUDIT)
        done = subprocess.run(['go', 'run', './audit', str(before), str(after)], cwd=self.probe.root,
                              env=GOENV, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        proof = json.loads(done.stdout)
        proof['python_other_ast_equal'] = True
        proof['helpers_raw_sha256'] = hashlib.sha256(gen_vectors.HELPERS.encode()).hexdigest()
        proof['wire_runtimes'] = {}
        for side, source in [('legacy', 'wirert/go/check.go'), ('full', 'wirert/full/go/check.go')]:
            original = subprocess.check_output(['git', 'show', '01c2ef53920042ff4313807b3d2ef48ed05baf27:tools/normgen/' + source], cwd=ROOT)
            write(before, original); write(after, (HERE / source).read_bytes())
            done = subprocess.run(['go', 'run', './audit', str(before), str(after), 'wire'], cwd=self.probe.root,
                                  env=GOENV, capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            proof['wire_runtimes'][side] = json.loads(done.stdout)
        record('other-comparators-ast-token-audit.json', proof)

    def test_exact_numeric_lexemes_in_all_three_consumers(self):
        raws = ['[{"write":{"holder":"fixed"},"cas":1e0}]',
                '[{"write":{"holder":"fixed"},"cas":1.0}]',
                '[{"write":{"holder":"fixed"},"cas":-0}]']
        rows = [([W('fixed', 1)], json.loads(raws[0])), ([W('fixed', 1)], json.loads(raws[1])),
                ([W('fixed', 0)], json.loads(raws[2]))]
        requests = [{'Mode': 'compare', 'Want': w, 'Raw': base64.b64encode(raw.encode()).decode()}
                    for (w, _), raw in zip(rows, raws)]
        self.assertEqual(self.probe.call(requests), [{'full': True, 'legacy': True}] * 3)
        self.assertEqual(self.probe.draft(rows, dict(enumerate(raws))), [True] * 3)

    def test_real_turn_adapter_all49_cases_and_owner_controls(self):
        by_kind = {k: [] for k in ('placement', 'operations', 'signer')}
        for case, raw, expected in cases():
            by_kind[json.loads(raw)['kind']].append((case, raw, expected))
        selected = by_kind['placement'] + by_kind['operations'] + by_kind['signer'] + by_kind['signer']
        replies = self.probe.call([{'Mode': 'run', 'Input': raw} for _, raw, _ in selected])
        self.assertEqual(len(replies), 62)
        for (case, _, expected), reply in zip(selected, replies):
            self.assertEqual(reply['code'], 0, case)
            self.assertEqual(self.match(expected, reply['value']), [], case)
        record('ordinary-turn-62.json', [{'case': c[0], 'actual': r} for c, r in zip(selected, replies)])

    def test_native_framing_is_checked_before_turn_match(self):
        want = [W('@new', '')]
        malformed = [b'[{"write":{"holder":"a","holder":"b"},"cas":""}]',
                     b'[{"write":{"holder":"a"},"cas":""}] true', b'\xef\xbb\xbf[]',
                     b'[NaN]', b'["\xff"]', b'{}']
        actual = self.probe.call([{'Mode': 'compare', 'Want': want, 'Raw': base64.b64encode(raw).decode()}
                                  for raw in malformed])
        self.assertEqual(actual, [{'full': False, 'legacy': False}] * len(malformed))

    def test_two_attempts_parallel_with_real_adapter_under_race(self):
        case, raw, expected = next(c for c in cases() if c[0] == 'operations-two-attempts-after-release')
        binary = self.probe.compile('race-probe', race=True)
        results, = self.probe.call([{'Mode': 'race', 'Input': raw, 'N': 32}], binary)
        labels = set()
        for actual in results:
            self.assertEqual(actual['code'], 0)
            self.assertEqual(self.match(expected, actual['value']), [])
            marks = [actual['value'][i]['write']['holder'] for i in (0, 6)]
            self.assertFalse(labels.intersection(marks))
            labels.update(marks)
        self.assertEqual(len(labels), 64)
        record('ordinary-turn-race.json', {'case': case, 'runs': 32, 'labels': 64, 'actual': results})

    def test_z_compiled_ordinary_mutants_reach_real_oracle(self):
        source = cases()
        requests = [{'Mode': 'run', 'Input': raw} for _, raw, _ in source]
        baseline = self.probe.call(requests)
        self.assertTrue(all(r['code'] == 0 and not self.match(c[2], r['value'])
                            for c, r in zip(source, baseline)))
        changes = [
            ('constant-process-holder', 'contracts/turn.go', 'func (t *Turn) newMark() {',
             'func (t *Turn) newMark() { if t.Kind=="operations" { t.mark="process-instance"; return }'),
            ('literal-prefix', 'contracts/turn.go', 'func (t *Turn) newMark() {',
             'func (t *Turn) newMark() { if t.Kind=="operations" { t.mark="@attempt"; return }'),
            ('reuse-after-release', 'contracts/turn.go', 'func (t *Turn) newMark() {',
             'func (t *Turn) newMark() { if t.Kind=="operations" && t.mark!="" { return }'),
            ('renew-changes-mark', 'contracts/turn.go',
             'func (t *Turn) Renew() TurnAction { return',
             'func (t *Turn) Renew() TurnAction { if t.Kind=="operations" {t.newMark()}; return'),
            ('reread-changes-attempt', 'contracts/turn.go', 'if t.reread {',
             'if t.reread { if t.Kind=="operations" {t.newMark()}'),
            ('unresolved-input-mark', 'vectoradapter/turn.go', 'r.Row["holder"] = t.Mark()',
             'r.Row["holder"] = "@same"'),
            ('wrong-cas', 'vectoradapter/turn.go', '"cas": version(a.Cas)', '"cas": version("999")'),
            ('extra-field', 'vectoradapter/turn.go',
             'return map[string]any{"write": w, "cas":',
             'w["unexpected"]=true; return map[string]any{"write": w, "cas":'),
            ('wrong-order', 'vectoradapter/turn.go', 'out = append(out, turnAction(in.Turn, a))',
             'out = append([]any{turnAction(in.Turn, a)}, out...)'),
            ('wrong-guard-key', 'vectoradapter/turn.go', '"key": key, "index":',
             '"key": key+"/wrong", "index":'),
        ]
        results = []
        for name, rel, old, new in changes:
            path = self.probe.root / rel
            original = path.read_text()
            self.assertEqual(original.count(old), 1, name)
            try:
                path.write_text(original.replace(old, new, 1))
                binary = self.probe.compile('mutant-' + name)
                replies = self.probe.call(requests, binary)
                self.assertTrue(all(r['code'] == 0 for r in replies), 'execution error is not a kill: ' + name)
                killed = [c[0] for c, r in zip(source, replies) if self.match(c[2], r['value'])]
                self.assertTrue(killed, name)
                if name in ('constant-process-holder', 'reuse-after-release'):
                    self.assertIn('operations-two-attempts-after-release', killed)
                results.append({'name': name, 'compiled': True, 'executed': len(replies), 'killed_by': killed})
            finally:
                path.write_text(original)
        record('ordinary-compiled-mutants.json', {'baseline_compile': True, 'baseline_matches': len(source),
                                                 'mutants': results})

    def test_z_compiled_matcher_mutants_have_semantic_witnesses(self):
        rows = corpus()
        expected = [not self.match(w, a) for w, a in rows]
        requests = [{'Mode': 'compare', 'Want': w, 'Actual': a} for w, a in rows]
        baseline = self.probe.call(requests)
        for side in ('full', 'legacy'):
            self.assertEqual([r[side] for r in baseline], expected)
        changes = [
            ('ignore-seen', 'if seen[label] {', 'if false {'),
            ('only-last-new', 'if seen[label] {', 'if label==current {'),
            ('allow-prefix', 'strings.HasPrefix(label, "@")', 'false'),
            ('ignore-current', 'current == "" || label != current', 'current=="unreachable" && false'),
            ('loose-keyset', '!ok || len(w) != len(g)', '!ok'),
            ('reverse-order', '!walk(v, g[i])', '!walk(v, g[len(g)-1-i])'),
            ('forget-after-done', 'return equalJSONValue(want, got)',
             'if want=="done" {clear(seen)}; return equalJSONValue(want, got)'),
            ('bool-is-number', 'return equalJSONValue(want, got)',
             'if _,ok:=got.(bool);ok {return true}; return equalJSONValue(want, got)'),
        ]
        results = []
        for side in ('full', 'legacy'):
            path = self.probe.root / side / 'check.go'
            original = path.read_text()
            start, end = original.index('func turnEqual('), original.index('\nfunc raw(')
            for name, old, new in changes:
                body = original[start:end]
                self.assertIn(old, body, name)
                try:
                    path.write_text(original[:start] + body.replace(old, new, 1) + original[end:])
                    binary = self.probe.compile('mutant-' + side + '-' + name)
                    actual = self.probe.call(requests, binary)
                    witnesses = [i for i, (r, want) in enumerate(zip(actual, expected)) if r[side] != want]
                    self.assertTrue(witnesses, side + '/' + name)
                    results.append({'side': side, 'name': name, 'compiled': True,
                                    'executed': len(rows), 'oracle_mismatches': witnesses})
                finally:
                    path.write_text(original)
        record('matcher-compiled-mutants.json', {'baseline_compile': True, 'oracle_sha256': ORACLE_SHA,
                                                'mutants': results})


if __name__ == '__main__':
    unittest.main()
