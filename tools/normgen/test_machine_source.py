import ast
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import tokenize
import unittest

import machine_source as machine


GO_SCAN = r'''package main
import("encoding/json";"fmt";"go/parser";"go/scanner";"go/token";"os")
func scan(text string) ([][2]string,error) {
    if _,err:=parser.ParseFile(token.NewFileSet(),"input.go",text,parser.AllErrors);err!=nil{return nil,err}
    var s scanner.Scanner;fs:=token.NewFileSet();f:=fs.AddFile("input.go",fs.Base(),len(text))
    var failure error;s.Init(f,[]byte(text),func(_ token.Position,msg string){failure=fmt.Errorf("%s",msg)},0)
    var out [][2]string
    for {_,tok,lit:=s.Scan();if tok==token.EOF{break};out=append(out,[2]string{tok.String(),lit})}
    return out,failure
}
func comments(text string) []string {var s scanner.Scanner;fs:=token.NewFileSet();f:=fs.AddFile("input.go",fs.Base(),len(text))
    s.Init(f,[]byte(text),nil,scanner.ScanComments);out:=[]string{}
    for {_,tok,lit:=s.Scan();if tok==token.EOF{break};if tok==token.COMMENT{out=append(out,lit)}};return out}
func main(){var v struct{Before,After string};if err:=json.NewDecoder(os.Stdin).Decode(&v);err!=nil{panic(err)}
    before,err:=scan(v.Before);if err!=nil{panic(err)};after,err:=scan(v.After);if err!=nil{panic(err)}
    if err=json.NewEncoder(os.Stdout).Encode(struct{Before,After [][2]string;AfterComments []string}{before,after,comments(v.After)});err!=nil{panic(err)}}
'''


class MachineSource(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.home = Path(tempfile.mkdtemp(prefix="machine-source-control-"))
        cls.helper = cls.home / "scan.go"
        cls.helper.write_text(GO_SCAN, encoding="utf-8")
        cls.go = "/opt/go1.22.10/bin/go"
        if not Path(cls.go).is_file():
            raise RuntimeError("pinned Go1.22.10 unavailable for independent lexical control")
        cls.env = dict(os.environ, GO111MODULE="off", GOWORK="off", GOENV="off", GOPROXY="off", GOSUMDB="off",
                       GOTOOLCHAIN="local", CGO_ENABLED="0", GOCACHE=str(cls.home / "cache"))

    def tokens_equal(self, before, after):
        done = subprocess.run([self.go, "run", str(self.helper)], input=json.dumps(dict(Before=before, After=after)),
                              capture_output=True, text=True, env=self.env, timeout=120)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        report = json.loads(done.stdout)
        self.assertEqual(report["Before"], report["After"])
        return report

    def test_go_literals_comments_and_token_boundaries(self):
        text = ('// descriptive\npackage sample\n'
                'const URL = "https://example.invalid/a//b/*data*/"\n'
                'const Raw = `// literal\n/* literal */`\n'
                "const Rune = '/'\n"
                'func f() int { a := 1; return a/* explanatory */+2 }\n')
        after = machine.go_source(text)
        self.assertNotIn("descriptive", after)
        self.assertNotIn("explanatory", after)
        self.assertIn('"https://example.invalid/a//b/*data*/"', after)
        self.assertIn('`// literal\n/* literal */`', after)
        self.tokens_equal(text, after)

    def test_go_multiline_comments_keep_semicolons_and_directives(self):
        text = ('//go:build linux\n\npackage sample\nimport _ "embed"\n'
                '//go:embed forms/schema.json\nvar Schema string\n'
                'func f() int {\na:=1 /* first\n second */\nreturn a\n}\n')
        after = machine.go_source(text)
        self.assertIn('//go:build linux\n', after)
        self.assertIn('//go:embed forms/schema.json\nvar Schema string', after)
        self.assertNotIn('first', after)
        self.tokens_equal(text, after)

    def test_go_invalid_lexical_input_is_not_repaired(self):
        for text in ('package x\n/* unfinished', 'package x\nconst X = `unfinished',
                     'package x\nconst X = "unterminated\n'):
            with self.subTest(text=text), self.assertRaises(machine.SourceError):
                machine.go_source(text)

    def test_python_docstrings_only_and_unicode_physical_lines(self):
        text = ('"""module prose"""\n'
                'URL = "https://example.invalid/a//b#data"\n'
                'TEXT = "a\u2028b"\n'
                'class C:\n    """class prose"""\n    def f(self):\n'
                '        """function\n        prose"""\n'
                '        "not a docstring"\n'
                '        return URL, TEXT, 7 // 2 # explanatory\n')
        before = ast.parse(text)
        for node in ast.walk(before):
            if (isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body
                    and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)):
                node.body[0] = ast.Expr(value=ast.Constant(value=None))
        after = machine.python_source(text)
        self.assertNotIn('module prose', after)
        self.assertNotIn('function\n', after)
        self.assertIn('"not a docstring"', after)
        self.assertIn('"a\u2028b"', after)
        self.assertEqual(ast.dump(before, include_attributes=False), ast.dump(ast.parse(after), include_attributes=False))
        self.assertEqual([t for t in tokenize.generate_tokens(io.StringIO(after).readline)
                          if t.type == tokenize.COMMENT], [])

    def test_python_directives_inline_and_docstring_only_suites(self):
        text = ('#!/usr/bin/env python3\n# coding: utf-8\n'
                'class Empty: "doc"\n'
                'def f(): """first\nsecond"""; return "# string" # prose\n'
                'answer = 1 # type: ignore[assignment]\n')
        header = machine.identity_header('tools/normgen/example.py', [('form.tsv', 'a' * 64)], language='python')
        after = machine.python_source(text, header=header)
        self.assertTrue(after.startswith('#!/usr/bin/env python3\n# coding: utf-8\n# Code generated'))
        self.assertIn('# type: ignore[assignment]', after)
        self.assertNotIn('# prose', after)
        ns = {}
        exec(compile(after, '<generated>', 'exec'), ns)
        self.assertIsNone(ns['Empty'].__doc__)
        self.assertIsNone(ns['f'].__doc__)
        self.assertEqual(ns['f'](), '# string')

    def test_identity_headers_preserve_editable_ownership_and_reject_conflicts(self):
        sources = [('Platform/form.tsv', 'a' * 64), ('Platform/form.tsv', 'a' * 64)]
        closed = machine.identity_header('tools/normgen/gen_example.py', sources)
        owned = machine.identity_header('tools/normgen/gen_example.py', sources, editable=True)
        self.assertIn('Code generated', closed)
        self.assertNotIn('DO NOT EDIT', owned)
        self.assertEqual(owned.count('// Source:'), 1)
        self.assertIn('sha256: ' + 'a' * 64, owned)
        with self.assertRaises(machine.SourceError):
            machine.identity_header('tools/normgen/gen_example.py', [('x', 'a' * 64), ('x', 'b' * 64)])
        with self.assertRaises(machine.SourceError):
            machine.identity_header('tools/normgen/gen_example.py', [('x\npackage injected', 'a' * 64)])
        with self.assertRaises(machine.SourceError):
            machine.go_source('package x\n', header='// explanatory header\n')
        with self.assertRaises(machine.SourceError):
            machine.python_source('answer = 1\n', header='# Source: x\n')


class FirstTwoOutputs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        MachineSource.setUpClass.__func__(cls)

    tokens_equal = MachineSource.tokens_equal

    def assert_machine_comments(self, text):
        report = self.tokens_equal(text, text)
        for comment in report['AfterComments']:
            self.assertRegex(comment, r'^// (?:Code generated by .+; DO NOT EDIT\.|Source: .+|'
                                     r'sha256: [0-9a-f]{64}|Table sha256 [0-9a-f]{64}\.|'
                                     r'\S+\.(?:tsv|json|yaml|md|py|go) sha256 [0-9a-f]{64})$')

    def test_refusals_actual_source_has_only_machine_comments(self):
        import gen_refusals
        files = gen_refusals.render()
        self.assertEqual(set(files), {'refusals.go'})
        text = files['refusals.go']
        self.assertIn('var All = []*Spec{', text)
        self.assert_machine_comments(text)

    def test_families_actual_source_and_runtime_have_only_machine_comments(self):
        import gen_families
        files = gen_families.render()
        self.assertEqual(set(files), {'families.go', 'runtime.go'})
        self.assertIn('var All = []*Family{', files['families.go'])
        for text in files.values():
            self.assert_machine_comments(text)


if __name__ == '__main__':
    unittest.main()
