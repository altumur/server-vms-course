"""Full wire 4f0cff2e: closed grammar, exact raw input, active surfaces, and all 3224 P/06 fixture calls."""
import lesson as output_lesson
import base64
import copy
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types
import unittest

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent.parent
sys.path.insert(0,str(HERE))
import wire
import wire_fakes
import wire_vectors as W
from gen_checks import gofmt

GOENV=dict(os.environ,GOFLAGS='-mod=mod',GOPROXY='off',GOWORK='off',GOTOOLCHAIN='local')


class Grammar(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
        cls.bindings=wire.parse(ROOT)
        cls.ex=wire.Expander(ROOT)

    def test_full_registry_and_exclusions(self):
        self.assertEqual(len(self.bindings),97)
        runs,excluded=wire.expand(ROOT,'06-console')
        self.assertEqual(len(runs),3224)
        self.assertEqual(len({r.identity for r in runs}),3224)
        layouts={(e.binding.package,e.binding.table) for e in excluded if e.binding.surface=='layout'}
        self.assertEqual(layouts,{('common/journal','modes.tsv'),('06-console/requests-body','requests_body.tsv'),('common/fault','fault.tsv')})
        self.assertFalse(any(r.binding.package=='06-console/requests-body' for r in runs))
        self.assertFalse(any(r.binding.package=='common/group-of' and r.binding.surface.startswith('stand:') for r in runs))
        self.assertTrue(any(e.binding.package=='common/group-of' and e.binding.surface.startswith('stand:') for e in excluded))

    def test_at_and_decoded_string(self):
        expr={'at':{'value':{'column':'x','decode':'json'},'pointer':'/a~1b/~0'},'decode':'json'}
        wire.check_value(expr,'fixture')
        rows=[(1,{'x':json.dumps({'a/b':{'~':'[1,true,null]'}})})]
        self.assertEqual(self.ex.value(expr,rows,ROOT,'fixture'),[1,True,None])
        for ptr in ('','not/a/pointer','/a~2b','/absent'):
            bad=copy.deepcopy(expr);bad['at']['pointer']=ptr
            with self.subTest(pointer=ptr),self.assertRaises(wire.WireError):
                wire.check_value(bad,'fixture');self.ex.value(bad,rows,ROOT,'fixture')
        bad={'at':{'value':expr,'pointer':'/a'}}
        with self.assertRaises(wire.WireError):wire.check_value(bad,'fixture')
        rows=[(1,{'x':json.dumps({'a/b':{'~':3}})})]
        with self.assertRaises(wire.WireError):self.ex.value(expr,rows,ROOT,'fixture')

    def test_map_is_grouped_and_rejects_duplicate_keys(self):
        expr={'map':{'key':'word','value':{'column':'status','decode':'json'}}}
        with self.assertRaises(wire.WireError):wire.check_value(expr,'fixture')
        wire.check_value(expr,'fixture',group=True)
        rows=[(1,{'word':'one','status':'true'}),(2,{'word':'two','status':'[1,2]'})]
        self.assertEqual(self.ex.value(expr,rows,ROOT,'fixture'),{'one':True,'two':[1,2]})
        for value in ('true','false'):
            with self.subTest(value=value),self.assertRaises(wire.WireError):
                self.ex.value(expr,rows+[(3,{'word':'one','status':value})],ROOT,'fixture')

    def test_raw_json_argument_is_not_normalized(self):
        b=next(b for b in self.bindings if b.surface=='stand:rid')
        raw=' [1.00e+02,9007199254740993,-0] '
        row={'rid':raw,'verdict':'refused'}
        r=self.ex.one(b,'06-console',b.inputs[0],[(42,row)],wire.package_dir(ROOT,b.package),'fixture')
        self.assertEqual(r.arg,('{"rid":'+raw+'}').encode())
        for text in ('NaN','{} trailing','{"x":1,"x":2}','\ufeff{}'):
            with self.subTest(text=text),self.assertRaises(wire.WireError):
                self.ex.one(b,'06-console',b.inputs[0],[(42,{'rid':text,'verdict':'refused'})],ROOT,'fixture')

    def test_argument_vocabulary_is_input_only(self):
        for constructor in ('file','group','groups','map','suffix','omit','at'):
            with self.subTest(constructor=constructor),self.assertRaises(wire.WireError):
                wire.check_arg_json({constructor:{}},'fixture')
        with self.assertRaises(wire.WireError):
            wire.check_value({'column':'raw','decode':'raw-json'},'fixture')
        good={'object':{'input':{'column':'raw','decode':'text'},'x':{'array':[{'literal':True}]}}}
        wire.check_arg_json(good,'fixture')
        self.assertEqual(wire.argument_json(self.ex.argument(good,[(1,{'raw':'{"x":1}'})],'fixture'),'fixture'),
                         '{"input":"{\\"x\\":1}","x":[true]}')

    def test_marker_assert_ignore_is_not_marker_ignore(self):
        b=copy.deepcopy(next(b for b in self.bindings if b.package=='06-console/rid' and b.table=='template.tsv'))
        a={'pointer':'','value':{'literal':{}},'ignore':['/detail']}
        b.markers=[{'variant':'','column':'expect','match':'special','value':{'literal':{}},'assert':[a]}]
        wire.check_binding(ROOT,b,'fixture')
        b.markers[0]['ignore']=['/detail']
        with self.assertRaises(wire.WireError):wire.check_binding(ROOT,b,'fixture')
        del b.markers[0]['ignore']
        a['test']='prefix'
        with self.assertRaises(wire.WireError):wire.check_binding(ROOT,b,'fixture')

    def test_empty_cells_do_not_infer_grouping(self):
        b=copy.deepcopy(next(b for b in self.bindings if b.package=='common/fault' and b.surface=='vectors'))
        grouped,_=self.ex.run(b,'06-console')
        self.assertEqual(len(grouped),1)
        count=len(wire.read_rows(ROOT,b))
        del b.inputs[0]['group_by'];b.inputs[0]['case']={'line':True}
        b.expect=[{'variant':'','code':0,'value':{'literal':{}}}]
        wire.check_binding(ROOT,b,'fixture')
        per_row,_=self.ex.run(b,'06-console')
        self.assertEqual(len(per_row),count)
        self.assertGreater(count,1)


DRIVER='''package main
import("bufio";"encoding/base64";"encoding/json";"fmt";"os";"probe/wirecheck")
func main(){s:=bufio.NewScanner(os.Stdin);s.Buffer(make([]byte,4096),1<<20);for s.Scan(){var x struct{Code int;Out,Spec string};if err:=json.Unmarshal(s.Bytes(),&x);err!=nil{panic(err)};b,err:=base64.StdEncoding.DecodeString(x.Out);if err!=nil{panic(err)};fmt.Println(wirecheck.Check(x.Code,b,x.Spec)==nil)};if err:=s.Err();err!=nil{panic(err)}}
'''


class Native(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
        cls.tmp=tempfile.TemporaryDirectory(prefix='wire-full-native-');cls.mod=Path(cls.tmp.name)
        g=types.SimpleNamespace(HERE=HERE,gofmt=gofmt,GenError=RuntimeError)
        for rel,data in W.runtime_files(g,full=True).items():
            p=cls.mod/rel[3:];p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
        (cls.mod/'main.go').write_text(DRIVER);(cls.mod/'go.mod').write_text('module probe\n\ngo 1.22\n')
        done=subprocess.run(['go','build','-o',str(cls.mod/'probe'),'.'],cwd=cls.mod,env=GOENV,capture_output=True,text=True)
        assert done.returncode==0,done.stderr

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def judge(self,cases,spec):
        lines=[]
        for value,_ in cases:
            output=value.encode() if isinstance(value,str) else value
            lines.append(json.dumps({'Code':spec.get('code',0),'Out':base64.b64encode(output).decode(),'Spec':json.dumps(spec)}))
        done=subprocess.run([str(self.mod/'probe')],input='\n'.join(lines)+'\n',text=True,capture_output=True)
        self.assertEqual(done.returncode,0,done.stderr)
        self.assertEqual(done.stdout.splitlines(),[str(ok).lower() for _,ok in cases])

    def test_schema_is_complete_before_both_kinds_of_ignore(self):
        spec={'code':0,'value':{'fixed':True},'compare':'value','ignored':['/detail'],
              'native':{'type':'object','frame':'json','schema':{'type':'object','required':['fixed','detail'],
                        'properties':{'fixed':{'const':True},'detail':{'type':'string','minLength':1}},'additionalProperties':False}}}
        self.judge([('{"fixed":true,"detail":"reason"}',True),('{"fixed":true}',False),
                    ('{"fixed":true,"detail":7}',False),('{"fixed":false,"detail":"x"}',False)],spec)
        spec={'code':0,'value':{'fixed':True},'compare':'subset','native':{'type':'object','frame':'json'},
              'asserts':[{'pointer':'/row','decode':'json','value':{'x':1},'compare':'value','ignore':['/volatile']}]}
        self.judge([(json.dumps({'fixed':True,'row':json.dumps({'x':1,'volatile':[2]})}),True),
                    (json.dumps({'fixed':True,'row':json.dumps({'x':2,'volatile':[2]})}),False)],spec)

    def test_array_ignores_use_original_indices(self):
        spec={'code':0,'value':{'a':['keep','drop','keep2','drop2']},'compare':'value',
              'ignored':['/a/1','/a/3'],'native':{'type':'object','frame':'json'}}
        self.judge([('{"a":["keep","other","keep2","other2"]}',True),
                    ('{"a":["keep","other","wrong","other2"]}',False)],spec)

    def test_json_lines_are_complete_strict_and_ordered(self):
        spec={'code':0,'raw':base64.b64encode(b'{"x":1}\n{"x":2}\n').decode(),'compare':'lines-subset',
              'native':{'type':'bytes','frame':'raw'}}
        self.judge([('{"x":1,"extra":0}\n{"x":2}\n',True),('{"x":1}\n{"x":2}',False),
                    ('{"x":2}\n{"x":1}\n',False),('{"x":1,"x":1}\n{"x":2}\n',False),
                    ('{"x":1}\n\n{"x":2}\n',False)],spec)
        spec['compare']='lines-value'
        self.judge([('{"x":1}\n{"x":2}\n',True),('{"x":1,"extra":0}\n{"x":2}\n',False)],spec)


def fake_key(table,variant,cells,files):
    parts=[table.encode(),variant.encode()]
    for key,value in sorted(cells.items()): parts.extend((key.encode(),value.encode()))
    parts.append(b"fixtures")
    for key,value in sorted(files.items()): parts.extend((key.encode(),value))
    return base64.b64encode(b"".join(str(len(p)).encode()+b":"+p for p in parts)).decode()


FAKE_HEAD = r'''package vectoradapter
import("encoding/base64";"encoding/json";"fmt";"sort";"strconv";"strings")
func fixtureValue(s string) any { d:=json.NewDecoder(strings.NewReader(s));d.UseNumber();var v any;if err:=d.Decode(&v);err!=nil{panic(err)};return v }
func fixtureBytes(s string) []byte {b,err:=base64.StdEncoding.DecodeString(s);if err!=nil{panic(err)};return b}
func fixtureKey(table,variant string,cells map[string]string,files map[string][]byte) string {
    parts:=[]string{table,variant};ks:=[]string{};for k:=range cells{ks=append(ks,k)};sort.Strings(ks)
    for _,k:=range ks{parts=append(parts,k,cells[k])};parts=append(parts,"fixtures")
    ks=[]string{};for k:=range files{ks=append(ks,k)};sort.Strings(ks);for _,k:=range ks{parts=append(parts,k,string(files[k]))}
    var b strings.Builder;for _,p:=range parts{b.WriteString(strconv.Itoa(len(p)));b.WriteByte(':');b.WriteString(p)}
    return base64.StdEncoding.EncodeToString([]byte(b.String()))
}
func fixtureRead(m map[string]Answer,key string) Answer {if a,ok:=m[key];ok{return a};return NotImplemented("unknown fixture input "+key)}
var _ = fmt.Sprint
'''


class Render(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        output_lesson.ready_outputs(profiles=output_lesson.PROFILES)
        import lesson
        saved,env=lesson.CURRENT,os.environ.get('NORMGEN_LESSON')
        lesson.CURRENT=lesson.get('06-console');os.environ['NORMGEN_LESSON']='06-console'
        import gen_vectors as g
        g=importlib.reload(g)
        cls.tmp=tempfile.TemporaryDirectory(prefix='wire-full-render-');cls.mod=Path(cls.tmp.name)
        try:
            runs,excluded=wire.expand(ROOT,'06-console');cls.runs=runs
            known=g.common_vectors.composition('06-console',ROOT,known_only=True)
            known_keys={(f'common/{n}',t,'vectors') for n,t in known}
            active={r.binding.key:r.binding for r in runs}
            api=[];cls.rows={}
            for i,(key,b) in enumerate(active.items()):
                if key in known_keys:continue
                variants={r.variant for r in runs if r.binding.key==key}
                args='input' if b.surface.startswith('stand:') or b.package=='common/group-of' else 'cells+variant' if variants!={''} else 'cells'
                if b.package=='common/fault':args='none'
                api.append((*key,f'Probe{i}',args))
            cls.api=api
            decls=W.declarations(ROOT,'06-console',api)
            cls.assertNoInactive=not any(d['surface']=='stand:group-of' for d in decls)
            files,inventory=W.build(ROOT,g,decls=decls,lesson='06-console')
            for rel,data in files.items():
                if rel.startswith('go/'):
                    p=cls.mod/rel[3:];p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
            shutil.copytree(output_lesson.output_root() / 'p06/go/families',cls.mod/'families')
            (cls.mod/'go.mod').write_text('module normgen/p06\n\ngo 1.22\n')
            by={}
            for d in decls:
                selected=[r for r in runs if r.binding.key==(d['package'],d['table'],d['surface'])]
                by[d['fn']]=(d,selected)
            code=[FAKE_HEAD]
            def table(name,selected,key_fn):
                vals={}
                for r in selected:
                    value=wire_fakes.native_value(r)
                    raw=value if isinstance(value,bytes) else None
                    body='Answer{Code:'+str(r.code)+',Value:fixtureValue('+g.gstr(json.dumps(None if raw is not None else value,ensure_ascii=False))+')'
                    if raw is not None:body+=',Raw:fixtureBytes('+g.gstr(base64.b64encode(raw).decode())+')'
                    body+='}'
                    key=key_fn(r)
                    if key in vals:assert vals[key]==body,(name,key)
                    vals[key]=body
                code.append('var '+name+' = map[string]Answer{'+','.join(g.gstr(k)+':'+v for k,v in vals.items())+'}\n')
            for fn,(d,selected) in by.items():
                if d['surface'].startswith('stand:'):
                    key_fn=lambda r:r.arg.decode()
                elif d['args']=='input':key_fn=lambda r:next(iter(r.cells.values()))
                elif d['args']=='none':key_fn=lambda r:''
                else:key_fn=lambda r:fake_key(r.binding.table,r.variant,r.cells,r.files)
                if d['args']=='none':key_fn=lambda r:''
                table('fixture'+fn,selected,key_fn)
                if d['args']=='input':sig='input []byte';key='string(input)'
                elif d['args']=='none':sig='';key='""'
                elif d['args']=='cells+variant':sig='table,variant string,cells map[string]string,files map[string][]byte';key='fixtureKey(table,variant,cells,files)'
                else:sig='table string,cells map[string]string,files map[string][]byte';key='fixtureKey(table,"",cells,files)'
                code.append(f'func {fn}({sig}) Answer {{ return fixtureRead(fixture{fn},{key}) }}\n')
                (cls.mod/'vectoradapter'/(fn.lower()+'.go')).unlink()
            for name in ('crl','revoked','log-mask','store-client'):
                selected=[r for r in runs if r.binding.package=='common/'+name]
                fn='C'+g.camel(name)
                table('fixture'+fn,selected,lambda r:fake_key(r.binding.table,r.variant,r.cells,r.files))
                if name=='crl':sig='func CRL(input []byte)(any,error)';cell='"input":string(input)';ret='a.Value'
                elif name=='revoked':sig='func Revoked(input []byte)(any,error)';cell='"file":string(input)';ret='a.Value'
                elif name=='store-client':sig='func StoreClient(input []byte)(string,error)';cell='"input":string(input)';ret='a.Value.(string)'
                else:sig='func LogMask(raw string,fields []byte)(string,error)';cell='"raw":raw';ret='a.Value.(string)'
                filesarg='map[string][]byte{"fields.yaml":fields}' if name=='log-mask' else 'nil'
                code.append(sig+'{a:=fixtureRead(fixture'+fn+',fixtureKey("cases.tsv","",map[string]string{'+cell+'},'+filesarg+'));return '+ret+',nil}\n')
                (cls.mod/'vectoradapter'/g.common_vectors.DECLS[name]['adapter']).unlink()
            (cls.mod/'vectoradapter/fixtures.go').write_text('\n'.join(code))
            # A concrete input-API function exposes native refusals and infrastructure errors independently of goldens.
            group=next(d for d in decls if d['package']=='common/group-of')
            cls.group_fn=group['fn']
            cls.original_fake=(cls.mod/'vectoradapter/fixtures.go').read_text()
        finally:
            lesson.CURRENT=saved
            if env is None:os.environ.pop('NORMGEN_LESSON',None)
            else:os.environ['NORMGEN_LESSON']=env
            importlib.reload(g)

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def test_api_admits_no_expectations_or_duplicate_bindings(self):
        columns=("package","table","surface","fn","args")
        bad=dict(zip(columns,self.api[0]));bad["expect"]={"literal":"injected golden"}
        with self.assertRaises(wire.WireError):W.declarations(ROOT,"06-console",[bad]+self.api[1:])
        with self.assertRaises(wire.WireError):W.declarations(ROOT,"06-console",self.api+[self.api[0]])

    def test_all_calls_and_active_surfaces(self):
        self.assertTrue(self.assertNoInactive)
        done=subprocess.run(['go','test','-count=1','-json','./vectortests'],cwd=self.mod,env=GOENV,capture_output=True,text=True)
        events=[json.loads(s) for s in done.stdout.splitlines() if s.startswith('{')]
        terminals=[e for e in events if e.get('Test') and e['Action'] in ('pass','fail','skip')]
        self.assertEqual(len({e['Test'] for e in terminals}),len(terminals),'duplicate terminal native test')
        self.assertFalse(any(e['Action']=='skip' for e in terminals),'skipped native test')
        results={e['Test']:e['Action'] for e in terminals}
        self.assertEqual(len(results),3224,done.stderr+done.stdout[-2000:])
        self.assertEqual(done.returncode,0,done.stderr+done.stdout[-3000:])
        self.assertTrue(all(a=='pass' for a in results.values()))

    def test_input_bytes_native_refusal_and_execution_failure(self):
        source=self.original_fake
        marker=f'func {self.group_fn}(input []byte) Answer'
        start=source.index(marker);end=source.index('\n',start)
        path=self.mod/'vectoradapter/fixtures.go'
        try:
            path.write_text(source[:start]+marker+' {if string(input)=="panic"{panic("fixture panic")};return Answer{Code:2,Value:string(input)}}'+source[end:])
            binary=self.mod/'vectors'
            done=subprocess.run(['go','build','-o',str(binary),'./cmd/vectors'],cwd=self.mod,env=GOENV,capture_output=True,text=True)
            self.assertEqual(done.returncode,0,done.stderr)
            for raw in ('  1.00e+02  ','"quoted"','panic'):
                frame={'format':1,'package':'common/group-of','table':'cases.tsv','case':'probe','variant':'', 'cells':{'raw':raw},'files':{}}
                f=self.mod/'input.json';f.write_text(json.dumps(frame))
                done=subprocess.run([str(binary),str(f)],capture_output=True,text=True)
                if raw=='panic':
                    self.assertNotEqual(done.returncode,0)
                    continue
                self.assertEqual(done.returncode,0,done.stderr)
                answer=json.loads(done.stdout)
                self.assertEqual(answer['exit_code'],2)
                self.assertEqual(json.loads(base64.b64decode(answer['stdout_b64'])),raw)
            f.write_text('{}')
            done=subprocess.run([str(binary),'stand','group-of',str(f)],capture_output=True,text=True)
            self.assertNotEqual(done.returncode,0)
            self.assertIn('not a stand key',done.stderr)
        finally:path.write_text(source)


if __name__=='__main__':unittest.main()
