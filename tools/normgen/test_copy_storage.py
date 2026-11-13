"""Judge of the copy-to-store port: real files, controlled failures, no implementation-line source."""
import lesson as output_lesson
import csv
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = output_lesson.output_root() / 'p01-1/go'
ENV = dict(os.environ, GOFLAGS="-mod=mod", GOPROXY="off", GOWORK="off", GOTOOLCHAIN="local")

def z21_copy_contract(root):
    """Read the actual copy header at its source owner, not generated constants."""
    text = (Path(root) / "Platform/01-store/spec/01.3-store.norms.md").read_text(encoding="utf-8")
    anchor = "<!-- req: P/01.3-R006 -->"
    if text.count(anchor) != 1 or text.count("<!-- req: P/01.3-R034 -->") != 1:
        raise ValueError("missing/ambiguous Source21 copy owner")
    section = text.split(anchor, 1)[1].split("<!-- req:", 1)[0]
    candidates = [s for s in re.findall(r"\{[^{}\n]*\}", section) if '"format"' in s and "<version>" in s]
    if len(candidates) != 1:
        raise ValueError("copy header requires one actual declaration")
    header = json.loads(candidates[0].replace("<version>", '"source-version-slot"'))
    if (set(header) != {"format", "version", "index"} or type(header["format"]) is not str or
            not header["format"] or type(header["version"]) is not int or header["version"] <= 0 or
            header["index"] != "source-version-slot"):
        raise ValueError("malformed copy header source")
    return header["format"], header["version"]


Z21_BACKUP_TEST = r'''package box
import("bytes";"encoding/json";"errors";"os";"path/filepath";"sync";"testing")
// A unit host behind the existing port; it is not a qualified backend/provider.
type z21Host struct{mu sync.Mutex;state CopyState;calls,snapshots int;guard func()error;after func();exit error}
func(h *z21Host)WithCopyLock(fn func(CopyTxn)error)error{
 h.mu.Lock();h.calls++;err:=fn(h);if err==nil&&h.guard!=nil{err=h.guard()};h.mu.Unlock()
 if h.after!=nil{h.after()};if err!=nil{return err};return h.exit
}
func(h *z21Host)Snapshot()(CopyState,error){h.snapshots++;return h.state,nil}
func(h *z21Host)BeginImport(ImportProgress)error{return errors.New("not an import fixture")}
func(h *z21Host)WriteImport(Row)error{return errors.New("not an import fixture")}
func(h *z21Host)FinishImport()error{return errors.New("not an import fixture")}
func z21HostState()CopyState{return CopyState{Index:9,Rows:[]Row{{Key:"unit/a",Index:7,Items:map[string]string{"v":"before"}}}}}
func z21Copy(t *testing.T,file string){
 t.Helper();raw,err:=os.ReadFile(file);if err!=nil{t.Fatal(err)}
 lines:=bytes.Split(raw,[]byte("\n"));if len(lines)!=3||len(lines[2])!=0{t.Fatal("incomplete/extra rows or missing LF")}
 var head,row map[string]any
 d:=json.NewDecoder(bytes.NewReader(lines[0]));d.UseNumber();if err=d.Decode(&head);err!=nil{t.Fatal(err)}
 d=json.NewDecoder(bytes.NewReader(lines[1]));d.UseNumber();if err=d.Decode(&row);err!=nil{t.Fatal(err)}
 if len(head)!=3||head["format"]!=@@FORMAT@@||head["version"]!=json.Number(@@VERSION@@)||head["index"]!="9"{t.Fatal("wrong header",head)}
 items,ok:=row["items"].(map[string]any)
 if len(row)!=3||row["key"]!="unit/a"||row["index"]!="7"||!ok||len(items)!=1||items["v"]!="before"{t.Fatal("snapshot alias/version changed",row)}
 info,err:=os.Stat(file);if err!=nil||info.Mode().Perm()!=0600{t.Fatal("wrong copy mode",err)}
}
func TestZ21BackupSnapshotBaseline(t *testing.T){
 h:=&z21Host{state:z21HostState()};file:=filepath.Join(t.TempDir(),"copy")
 if err:=BackupCopy(h,file,t.TempDir());err!=nil{t.Fatal(err)};z21Copy(t,file)
 if h.calls!=1||h.snapshots!=1{t.Fatal("not exactly one snapshot")}
}
func TestZ21BackupPublicationOutsideMutationLock(t *testing.T){
 h:=&z21Host{state:z21HostState()};file:=filepath.Join(t.TempDir(),"copy");old:=[]byte("previous destination")
 if err:=os.WriteFile(file,old,0600);err!=nil{t.Fatal(err)}
 h.guard=func()error{raw,e:=os.ReadFile(file);if e!=nil{return e};if !bytes.Equal(raw,old){return errors.New("publication inside mutation lock")};return nil}
 if err:=BackupCopy(h,file,t.TempDir());err!=nil{t.Fatal(err)};z21Copy(t,file)
}
func TestZ21BackupSnapshotDetachedBeforeRelease(t *testing.T){
 h:=&z21Host{state:z21HostState()};file:=filepath.Join(t.TempDir(),"copy")
 h.after=func(){h.mu.Lock();defer h.mu.Unlock();h.state.Index=99;h.state.Rows[0].Items["v"]="later"}
 if err:=BackupCopy(h,file,t.TempDir());err!=nil{t.Fatal(err)};z21Copy(t,file)
 if h.state.Rows[0].Items["v"]!="later"{t.Fatal("inactive host mutation")}
}
func TestZ21BackupLockExitFailureKeepsPublishedFile(t *testing.T){
 failure:=errors.New("controlled lock-exit failure before output");h:=&z21Host{state:z21HostState(),exit:failure}
 file:=filepath.Join(t.TempDir(),"copy");old:=[]byte("previous destination");if err:=os.WriteFile(file,old,0600);err!=nil{t.Fatal(err)}
 if err:=BackupCopy(h,file,t.TempDir());!errors.Is(err,failure){t.Fatal("lost lock outcome",err)}
 raw,err:=os.ReadFile(file);if err!=nil||!bytes.Equal(raw,old){t.Fatal("failed snapshot replaced destination",err)}
}
'''


def z21_go_tests(module, names):
    """Use only the existing accounting helper; its machine/routing oracle is not involved."""
    from test_gen_machine import CheckingError, complete_go_tests
    try:
        done = subprocess.run(["go", "test", "-count=1", "-json", "-run", "^(" + "|".join(names) + ")$", "./box"],
                              cwd=module, env=ENV, capture_output=True, timeout=120)
        observed = SimpleNamespace(returncode=done.returncode, stdout=done.stdout.decode("utf-8", "strict"),
                                   stderr=done.stderr.decode("utf-8", "strict"))
    except (OSError, subprocess.SubprocessError, UnicodeError) as exc:
        raise CheckingError(f"cannot obtain complete copy-library observations: {exc}") from exc
    return complete_go_tests(observed, names, "normgen/p01-1/box"), observed


SCENARIO_TEST = r'''package box
import (
    "bytes"
    "crypto/sha256"
    "encoding/json"
    "errors"
    "fmt"
    "math/big"
    "net/url"
    "os"
    "path/filepath"
    "reflect"
    "strconv"
    "strings"
    "testing"
    "time"
    "normgen/p01-1/admin"
    "normgen/p01-1/apidoor"
    "normgen/p01-1/coreadapter"
    "normgen/p01-1/flags"
    "normgen/p01-1/launch"
)

type publicStep struct {Scenario,Step,Request,Expect string}
type publicFixture struct {Steps []publicStep; InputDir string; Manifests map[string]string; SeamRequest,SeamExpect string}
type copyStand struct {
    t *testing.T
    inputDir string
    source,restored *diskFixture
    backups map[string]string
    output string
}
var standMark=launch.Mark{Format:"normgen-copy-judge",Version:1,Impl:"judge"}
func newStandDisk(t *testing.T)*diskFixture {
    t.Helper()
    d:=&diskFixture{dir:t.TempDir()}
    if err:=launch.CheckFormat(d.dir,standMark);err!=nil{t.Fatal(err)}
    return d
}
func ordinaryGet(d *diskFixture,key string)(map[string]any,error) {
    if err:=launch.CheckFormat(d.dir,standMark);err!=nil{return nil,err}
    s,err:=d.Snapshot();if err!=nil{return nil,err}
    if err=CopyStartAllowed(s.Import);err!=nil{return nil,err}
    for _,row:=range s.Rows {if row.Key==key{return map[string]any{"items":row.Items,"index":strconv.FormatUint(row.Index,10)},nil}}
    return map[string]any{"items":nil,"index":""},nil
}

// The ordinary command parser and admin dispatcher call CopyControl. Only its
// persistence/transport port is supplied by this reference host; expected output
// is never a parameter of a native command, Get or Put.
func nativeCommand(command string,d *diskFixture,file string,base uint64,force bool)(int,string) {
    argv:=[]string{command}
    if command=="backup" {argv=append(argv,file)} else {
        argv=append(argv,"-dir",d.dir,"--from",file)
        if command=="import" {argv=append(argv,"-index-base",strconv.FormatUint(base,10))}
        if force {argv=append(argv,"-force")}
    }
    f,ref:=flags.ParseArgs(argv,func(string)string{return ""})
    if ref!=nil{return ref.Code,ref.Error()}
    now:=d.now
    if now==nil {now=func()time.Time{return copyOpts(base).Now}}
    control:=CopyControl{Dir:d.dir,Ceiling:RowCeiling,Now:now,
        Open:func(name string)(CopyStorage,func(),error){
            if name!="backup" {if err:=launch.CheckFormat(d.dir,standMark);err!=nil{return nil,nil,err}}
            return d,func(){},nil
        }}
    var log bytes.Buffer
    code:=admin.Run(f,admin.Env{Stdout:&log,Stderr:&log,Copy:control})
    return code,log.String()
}

func (s *copyStand) perform(request string)(int,map[string]any,error) {
    words:=strings.Fields(request)
    switch {
    case strings.HasPrefix(request,"@foreign store "):
        d:=s.t.TempDir()
        if err:=os.WriteFile(filepath.Join(d,"opaque"),[]byte("do not alter"),0600);err!=nil{return 0,nil,err}
        if words[2]=="otherlabel" {
            raw,_:=json.Marshal(launch.Mark{Format:"foreign",Version:99,Impl:"other"})
            if err:=os.WriteFile(filepath.Join(d,"FORMAT"),raw,0600);err!=nil{return 0,nil,err}
        }
        before,err:=treeBytes(d);if err!=nil{return 0,nil,err}
        refusal:=launch.CheckFormat(d,standMark)
        after,err:=treeBytes(d);if err!=nil{return 0,nil,err}
        var startRefusal *launch.Refusal
        if !errors.As(refusal,&startRefusal) || !reflect.DeepEqual(before,after){return 1,nil,nil}
        return 0,map[string]any{"startup_exit":2,"unchanged":true},nil
    case strings.HasPrefix(request,"@import store "):
        file:=filepath.Join(s.inputDir,strings.TrimPrefix(words[2],"inputs/"))
        if words[2]=="backup" {file=s.backups[words[3]]}
        raw,err:=os.ReadFile(file);if err!=nil{return 0,nil,err}
        base,_,parseErr:=DecodeCopy(raw,RowCeiling)
        if parseErr!=nil {base=0}
        s.restored=&diskFixture{dir:s.t.TempDir()}
        code,log:=nativeCommand("import",s.restored,file,base,false)
        // The real stand starts this stopped target even after a refused input.
        // This ordinary startup mark/gate sees the durable state, not the result.
        if err=launch.CheckFormat(s.restored.dir,standMark);err!=nil{return 0,nil,err}
        state,err:=s.restored.Snapshot();if err!=nil{return 0,nil,err}
        if err=CopyStartAllowed(state.Import);err!=nil{return 0,nil,err}
        return code,map[string]any{"log":log},nil
    case strings.HasPrefix(request,"@backup store "):
        file:=filepath.Join(s.output,words[2]+".copy")
        if len(words)>3 && words[3]=="in-data" {file=filepath.Join(s.source.dir,words[2]+".copy")}
        code,log:=nativeCommand("backup",s.source,file,0,false)
        if code==0 {s.backups[words[2]]=file}
        return code,map[string]any{"log":log},nil
    }
    fields:=strings.SplitN(request," ",4)
    if len(fields)<3{return 0,nil,fmt.Errorf("unsupported public request %s",request)}
    d:=s.source
    if fields[0]=="restored" {d=s.restored}
    if d==nil{return 0,nil,errors.New("no restored target executed")}
    if fields[1]=="GET" {
        u,err:=url.ParseRequestURI(fields[2]);if err!=nil{return 0,nil,err}
        if u.Path!="/v1/get" {return 0,nil,fmt.Errorf("unsupported Get path %s",u.Path)}
        body,err:=ordinaryGet(d,u.Query().Get("key"));return 200,body,err
    }
    if fields[1]=="POST" && fields[2]=="/v1/write" && len(fields)==4 {
        var cmd struct {ID,Op,Key string;Items map[string]string}
        if err:=json.Unmarshal([]byte(fields[3]),&cmd);err!=nil{return 0,nil,err}
        if cmd.Op!="put" {return 0,nil,fmt.Errorf("unsupported fixture write op %s",cmd.Op)}
        index,again,err:=d.ordinaryPut(cmd.ID,cmd.Key,cmd.Items)
        if err!=nil{return 0,nil,err}
        body:=map[string]any{"index":strconv.FormatUint(index,10)}
        if again {body["again"]=true}
        return 200,body,nil
    }
    return 0,nil,fmt.Errorf("unexecuted public request %s",request)
}

func treeBytes(dir string)(map[string]string,error) {
    out:=map[string]string{}
    err:=filepath.WalkDir(dir,func(path string,e os.DirEntry,err error)error{
        if err!=nil{return err};if e.IsDir(){return nil}
        b,err:=os.ReadFile(path);if err!=nil{return err}
        out[strings.TrimPrefix(path,dir+string(os.PathSeparator))]=string(b);return nil
    })
    return out,err
}

func matchObservation(want,got any,vars map[string]string)bool {
    switch w:=want.(type) {
    case map[string]any:
        g,ok:=got.(map[string]any);if !ok || len(w)==0 && len(g)!=0{return false}
        for k,v:=range w {
            a,has:=g[k]
            if v=="@absent" {if has{return false};continue}
            if !has || !matchObservation(v,a,vars){return false}
        };return true
    case []any:
        g,ok:=got.([]any);if !ok || len(w)!=len(g){return false}
        for i:=range w {if !matchObservation(w[i],g[i],vars){return false}};return true
    case string:
        if w=="@any" {return true}
        if w=="@time" {g,ok:=got.(string);if !ok{return false};_,ok=readCopyTime(g);return ok}
        if strings.HasPrefix(w,"$") {g,ok:=got.(string);if !ok{return false};if old,has:=vars[w];has{return g==old};vars[w]=g;return true}
        return reflect.DeepEqual(w,got)
    case json.Number:
        g,ok:=got.(json.Number);if !ok{return false}
        a,aok:=new(big.Rat).SetString(string(w));b,bok:=new(big.Rat).SetString(string(g));return aok && bok && a.Cmp(b)==0
    default:return reflect.DeepEqual(want,got)
    }
}

func TestDaemonCopyExisting51Steps(t *testing.T) {
    raw,err:=os.ReadFile(os.Getenv("COPY_JUDGE_SCENARIOS"));if err!=nil{t.Fatal(err)}
    var fixture publicFixture;if err=json.Unmarshal(raw,&fixture);err!=nil{t.Fatal(err)}
    if len(fixture.Steps)!=51 {t.Fatalf("not the published 51 ordinary steps: %d",len(fixture.Steps))}
    previous:="";var stand *copyStand;vars:=map[string]string{}
    for _,st:=range fixture.Steps {
        if st.Scenario!=previous {
            previous=st.Scenario;vars=map[string]string{}
            stand=&copyStand{t:t,inputDir:fixture.InputDir,source:newStandDisk(t),backups:map[string]string{},output:t.TempDir()}
            if st.Scenario=="11-copy" {
                file:=filepath.Join(fixture.InputDir,"copy-ok.jsonl")
                if code,log:=nativeCommand("restore",stand.source,file,0,false);code!=0{t.Fatalf("prepare source through native restore: %d %s",code,log)}
            }
            // P01.3 README Stand: the original stand store has the two public
            // manifest rows even though copy-ok.jsonl deliberately has none.
            // Write actual fixture bytes through the ordinary store operation.
            for _,name:=range []string{"testsub","testsub2"} {
                raw,err:=os.ReadFile(fixture.Manifests[name]);if err!=nil{t.Fatal(err)}
                items:=map[string]string{"yaml":string(raw),"sha256":fmt.Sprintf("%x",sha256.Sum256(raw)),"rev":"1"}
                if _,_,err=stand.source.ordinaryPut("prepare-"+name,"platform/manifest/"+name,items);err!=nil{t.Fatal(err)}
            }
        }
        t.Run(st.Scenario+"/"+st.Step,func(t *testing.T){
            code,body,err:=stand.perform(st.Request)
            if err!=nil {t.Fatal("unexecuted/failed native path",err)}
            switch st.Expect {
            case "ok":if code!=0{t.Fatalf("want ok, native code %d body %v",code,body)}
            case "refused":if code==0{t.Fatal("expected refusal was accepted",body)}
            default:
                status,text,_:=strings.Cut(st.Expect," ")
                expectedCode,err:=strconv.Atoi(status);if err!=nil || code!=expectedCode {t.Fatalf("status want %s got %d",status,code)}
                dec:=json.NewDecoder(strings.NewReader(text));dec.UseNumber();var expected any
                if err=dec.Decode(&expected);err!=nil{t.Fatal(err)}
                // Normalize only JSON types, never the result from the expectation.
                encoded,err:=json.Marshal(body);if err!=nil{t.Fatal(err)}
                actualDecoder:=json.NewDecoder(bytes.NewReader(encoded));actualDecoder.UseNumber();var actual any
                if err=actualDecoder.Decode(&actual);err!=nil{t.Fatal(err)}
                if !matchObservation(expected,actual,vars){t.Fatalf("want %s, actual %s",text,encoded)}
            }
        })
    }
}

type referenceCore struct {coreadapter.NotInStage; t *testing.T; fixture publicFixture}
func (*referenceCore)Get(coreadapter.Ctx,apidoor.GetQuery)apidoor.Answer{return apidoor.Answer{}}
func (*referenceCore)List(coreadapter.Ctx,apidoor.ListQuery)apidoor.Answer{return apidoor.Answer{}}
func (*referenceCore)Write(coreadapter.Ctx,[]byte)apidoor.Answer{return apidoor.Answer{}}
func (*referenceCore)QueryRefused(coreadapter.Ctx,apidoor.Op,*apidoor.QueryError)apidoor.Answer{return apidoor.Answer{}}
func (*referenceCore)Context(coreadapter.Call,map[string]string)coreadapter.Ctx{return nil}
func (*referenceCore)Close(){}

// This is a YOURS adapter over the very same native command/storage functions
// used by the 51-step host. It receives no expectation and observes actual I/O.
func(c *referenceCore)NativeSeam(cfg coreadapter.Config,name string,args json.RawMessage)(json.RawMessage,error) {
    if name!="store-copy-floor" {return nil,errors.New("reference host implements copy seam only")}
    var input struct {Input string;InterruptAfter int `json:"interrupt_after_target_rows"`}
    if err:=json.Unmarshal(args,&input);err!=nil{return nil,err}
    if input.Input!="backup_of_restored_store" || input.InterruptAfter!=1{return nil,errors.New("unknown copy seam input")}
    if cfg.Now==nil{return nil,errors.New("no fixture clock")}
    source:=newStandDisk(c.t)
    source.now=cfg.Now
    seed:=filepath.Join(c.fixture.InputDir,"copy-ok.jsonl")
    if code,log:=nativeCommand("restore",source,seed,0,false);code!=0{return nil,fmt.Errorf("restore failed %d: %s",code,log)}
    backup:=filepath.Join(c.t.TempDir(),"restored.copy")
    if code,log:=nativeCommand("backup",source,backup,0,false);code!=0{return nil,fmt.Errorf("backup failed %d: %s",code,log)}
    raw,err:=os.ReadFile(backup);if err!=nil{return nil,err}
    base,rows,copyErr:=DecodeCopy(raw,RowCeiling);if copyErr!=nil{return nil,copyErr}
    var old Row
    for _,row:=range rows {if row.Key==FloorKey{old=row}}
    if old.Items==nil || len(rows)<3{return nil,errors.New("source backup was not of a restored store")}
    target:=newStandDisk(c.t);target.failAfter=input.InterruptAfter;target.now=cfg.Now
    code,log:=nativeCommand("import",target,backup,base,false)
    if code==0 || !strings.Contains(log,"injected I/O error after durable target row") {
        return nil,fmt.Errorf("expected controlled I/O interruption, got %d: %s",code,log)
    }
    first,err:=target.Snapshot();if err!=nil{return nil,err}
    if first.Import==nil{return nil,errors.New("interruption had no durable first floor")}
    f1:=cloneCopyRow(first.Import.Floor)
    reopened:=&diskFixture{dir:target.dir,now:cfg.Now}
    if code,log=nativeCommand("import",reopened,backup,base,false);code!=0{return nil,fmt.Errorf("resume failed %d: %s",code,log)}
    final,err:=reopened.Snapshot();if err!=nil{return nil,err}
    actual,err:=copyRowsByKey(final.Rows);if err!=nil{return nil,err}
    kept:=true
    for _,row:=range rows {if row.Key!=FloorKey && !reflect.DeepEqual(actual[row.Key],row){kept=false}}
    oldFloor,err:=strconv.ParseUint(old.Items["floor"],10,64);if err!=nil{return nil,err}
    newFloor,err:=strconv.ParseUint(f1.Items["floor"],10,64);if err!=nil{return nil,err}
    oldTransferred:=false
    for _,row:=range append(target.writeLog,reopened.writeLog...) {if row.Key==FloorKey && reflect.DeepEqual(row,old){oldTransferred=true}}
    observation:=map[string]any{
        "first_write_is_new_floor":len(target.writeLog)>0 && reflect.DeepEqual(target.writeLog[0],f1),
        "new_floor_greater_than_input":newFloor>oldFloor,
        "old_floor_transferred":oldTransferred,
        "same_floor_row_after_resume":reflect.DeepEqual(actual[FloorKey],f1),
        "other_rows_and_versions_equal":kept,
        "complete":final.Import!=nil && final.Import.Phase=="Done" && len(actual)==len(rows) && kept,
        "first_generation_at":f1.Items["generation_at"],
    }
    return json.Marshal(observation)
}

func TestPublishedCopyCALLThroughYOURSAndNativeIO(t *testing.T) {
    raw,err:=os.ReadFile(os.Getenv("COPY_JUDGE_SCENARIOS"));if err!=nil{t.Fatal(err)}
    var fixture publicFixture;if err=json.Unmarshal(raw,&fixture);err!=nil{t.Fatal(err)}
    cfg:=coreadapter.Config{DataDir:t.TempDir(),RowCeiling:RowCeiling,Now:func()time.Time{return time.Date(2027,2,3,4,5,6,123456789,time.UTC)}}
    // The live fixture directory is a sentinel, never an import destination.
    if err=os.WriteFile(filepath.Join(cfg.DataDir,"live"),[]byte("untouched"),0600);err!=nil{t.Fatal(err)}
    before,err:=treeBytes(cfg.DataDir);if err!=nil{t.Fatal(err)}
    c:=&referenceCore{t:t,fixture:fixture}
    name,input,ok:=strings.Cut(strings.TrimPrefix(fixture.SeamRequest,"CALL ")," ");if !ok{t.Fatal("no public CALL")}
    actual,err:=coreadapter.CallSeam(c,cfg,name,json.RawMessage(input));if err!=nil{t.Fatal(err)}
    var want,got any
    if err=json.Unmarshal([]byte(fixture.SeamExpect),&want);err!=nil{t.Fatal(err)}
    if err=json.Unmarshal(actual,&got);err!=nil{t.Fatal(err)}
    if !matchObservation(want,got,map[string]string{}){t.Fatalf("want %s, actual %s",fixture.SeamExpect,actual)}
    at,_:=copyNowText(cfg.Now())
    if got.(map[string]any)["first_generation_at"]!=at{t.Fatal("native copy ignored the fixture wall clock")}
    after,err:=treeBytes(cfg.DataDir);if err!=nil || !reflect.DeepEqual(before,after){t.Fatal("CALL imported over the live fixture directory",err)}
}
'''

SEAM_BRIDGE = '''package coreadapter
import "encoding/json"
// YOURS connection for the reference host: ordinary paths live on the core, no expected input.
func CallSeam(c Core,cfg Config,name string,args json.RawMessage)(json.RawMessage,error) {
    native,ok:=c.(interface{NativeSeam(Config,string,json.RawMessage)(json.RawMessage,error)})
    if !ok {return nil,ErrNotImplemented}
    return native.NativeSeam(cfg,name,args)
}
'''

BACKUP_TEST = r'''package box

import (
    "bytes"
    "encoding/json"
    "errors"
    "math"
    "os"
    "path/filepath"
    "reflect"
    "strconv"
    "strings"
    "sync"
    "testing"
    "time"
)

type diskFixture struct {
    mu sync.Mutex
    dir string
    snapshots int
    writeLog []Row
    failAfter int
    targetWrites int
    loseFloorReply bool
    dropWrites bool
    now func()time.Time
}

type diskRecord struct {
    CopyState
    IDs map[string]uint64
    Admission string
}

// The fixture persists each accepted operation in a real file. Tests always
// close/reopen its data through Snapshot; no prepared observation is returned.
func (d *diskFixture) WithCopyLock(fn func(CopyTxn) error) error {
    d.mu.Lock()
    defer d.mu.Unlock()
    return fn(d)
}
func (d *diskFixture) save(s CopyState) error {
    rec,err:=d.record()
    if err!=nil {return err}
    rec.CopyState=s
    return d.saveRecord(rec)
}
func (d *diskFixture) saveRecord(rec diskRecord) error {
    b, err := json.Marshal(rec)
    if err != nil { return err }
    return WriteCopyFile(filepath.Join(d.dir, "state.json"), b)
}
func (d *diskFixture) record() (diskRecord,error) {
    var rec diskRecord
    b,err:=os.ReadFile(filepath.Join(d.dir,"state.json"))
    if os.IsNotExist(err) {return rec,nil}
    if err!=nil {return rec,err}
    err=json.Unmarshal(b,&rec)
    return rec,err
}
func (d *diskFixture) Snapshot() (CopyState, error) {
    d.snapshots++
    var s CopyState
    b, err := os.ReadFile(filepath.Join(d.dir, "state.json"))
    if os.IsNotExist(err) { return s, nil }
    if err != nil { return s, err }
    err = json.Unmarshal(b, &s)
    return s, err
}
func (d *diskFixture) BeginImport(p ImportProgress) error {
    rec,err:=d.record();if err!=nil{return err}
    p.Floor=cloneCopyRow(p.Floor)
    rec.Import=&p
    rec.Index=p.Floor.Index
    rec.Rows=putRow(rec.Rows,p.Floor)
    rec.IDs=map[string]uint64{}
    rec.Admission=p.Floor.Items["generation_at"] // this new floor operation's OWN admission metadata
    if err=d.saveRecord(rec);err!=nil{return err}
    d.writeLog=append(d.writeLog,cloneCopyRow(p.Floor))
    if d.loseFloorReply{return errors.New("injected lost floor reply after durability")}
    return nil
}
func (d *diskFixture) WriteImport(r Row) error {
    rec,err:=d.record();if err!=nil{return err}
    if rec.Import==nil || rec.Import.Phase!="Transfer" {return errors.New("not in durable Transfer")}
    if d.dropWrites {return nil}
    rec.Rows=putRow(rec.Rows,r)
    if err=d.saveRecord(rec);err!=nil{return err}
    d.writeLog=append(d.writeLog,cloneCopyRow(r))
    d.targetWrites++
    if d.failAfter>0 && d.targetWrites==d.failAfter {return errors.New("injected I/O error after durable target row")}
    return nil
}
func (d *diskFixture) FinishImport() error {
    rec,err:=d.record();if err!=nil{return err}
    if rec.Import==nil {return errors.New("no durable attempt")}
    rec.Import.Phase="Done"
    return d.saveRecord(rec)
}
func putRow(rows []Row,r Row) []Row {
    for i:=range rows {if rows[i].Key==r.Key {rows[i]=cloneCopyRow(r);return rows}}
    return append(rows,cloneCopyRow(r))
}
func (d *diskFixture) ordinaryPut(id,key string,items map[string]string)(uint64,bool,error) {
    d.mu.Lock();defer d.mu.Unlock()
    rec,err:=d.record();if err!=nil{return 0,false,err}
    if err=CopyStartAllowed(rec.Import);err!=nil{return 0,false,err}
    if index,ok:=rec.IDs[id];ok{return index,true,nil}
    rec.Index++
    rec.Rows=putRow(rec.Rows,Row{Key:key,Items:items,Index:rec.Index})
    if rec.IDs==nil {rec.IDs=map[string]uint64{}}
    rec.IDs[id]=rec.Index
    rec.Admission="actual ordinary write"
    return rec.Index,false,d.saveRecord(rec)
}
func newDisk(t *testing.T, s CopyState) *diskFixture {
    t.Helper()
    d := &diskFixture{dir:t.TempDir()}
    if err := d.save(s); err != nil { t.Fatal(err) }
    return d
}

func TestBackupUsesDurableRowsVersionsAndNoIDMemory(t *testing.T) {
    state := CopyState{Index:9,Rows:[]Row{
        {Key:"other/z",Index:7,Items:map[string]string{"n":"2"}},
        {Key:"other/a",Index:3,Items:map[string]string{"n":"1"}},
    }}
    d := newDisk(t,state)
    file := filepath.Join(t.TempDir(),"copy")
    if err := BackupCopy(d,file,d.dir); err != nil { t.Fatal(err) }
    if d.snapshots != 1 || len(d.writeLog) != 0 { t.Fatal("not one read-only snapshot") }
    raw, err := os.ReadFile(file)
    if err != nil { t.Fatal(err) }
    lines := bytes.Split(bytes.TrimSuffix(raw,[]byte("\n")),[]byte("\n"))
    if len(lines)!=3 { t.Fatalf("unexpected copy lines: %d",len(lines)) }
    var head map[string]any
    if json.Unmarshal(lines[0],&head)!=nil || head["index"]!="9" || len(head)!=3 { t.Fatal("bad header") }
    for i,want := range []struct{key,version string}{{"other/a","3"},{"other/z","7"}} {
        var row map[string]any
        if json.Unmarshal(lines[i+1],&row)!=nil || row["key"]!=want.key || row["index"]!=want.version || len(row)!=3 {
            t.Fatalf("not exact sorted portable row %d: %s",i,lines[i+1])
        }
    }
    fi, err := os.Stat(file)
    if err!=nil || fi.Mode().Perm()!=0600 { t.Fatal("copy is not 0600",err) }
    leftovers,_:=filepath.Glob(filepath.Join(filepath.Dir(file),".configstore-copy-*"))
    if len(leftovers)!=0 { t.Fatal("temporary backup was not removed") }
}

func TestBackupInsideDataAndLinkRefuseBeforeStoreAccess(t *testing.T) {
    d:=newDisk(t,CopyState{})
    before,_:=os.ReadFile(filepath.Join(d.dir,"state.json"))
    link:=filepath.Join(t.TempDir(),"link")
    if err:=os.Symlink(d.dir,link); err!=nil { t.Fatal(err) }
    for _,file:=range []string{filepath.Join(d.dir,"copy"),filepath.Join(link,"copy")} {
        if err:=BackupCopy(d,file,d.dir); err==nil { t.Fatal("inside-data backup accepted") }
    }
    if err:=BackupTarget(filepath.Join(t.TempDir(),"copy"),string(filepath.Separator));err==nil {t.Fatal("filesystem root was treated as having an outside path")}
    after,_:=os.ReadFile(filepath.Join(d.dir,"state.json"))
    if !bytes.Equal(before,after) || d.snapshots!=0 { t.Fatal("refused backup touched the store") }
}

func TestBackupFailureKeepsExistingFile(t *testing.T) {
    file:=filepath.Join(t.TempDir(),"copy")
    if err:=os.WriteFile(file,[]byte("previous backup"),0644);err!=nil { t.Fatal(err) }
    d:=newDisk(t,CopyState{Index:1,Rows:[]Row{{Key:"other/x",Index:2,Items:map[string]string{}}}})
    if err:=BackupCopy(d,file,d.dir);err==nil { t.Fatal("bad snapshot accepted") }
    got,_:=os.ReadFile(file)
    if string(got)!="previous backup" { t.Fatal("failed backup replaced old file") }
    // A failed rename must clean its newly created temporary file too.
    targetDir:=filepath.Join(t.TempDir(),"target")
    if err:=os.Mkdir(targetDir,0700);err!=nil { t.Fatal(err) }
    if err:=WriteCopyFile(targetDir,[]byte("data"));err==nil { t.Fatal("rename onto directory accepted") }
    leftovers,_:=filepath.Glob(filepath.Join(filepath.Dir(targetDir),".configstore-copy-*"))
    if len(leftovers)!=0 { t.Fatal("failed rename leaked temporary file") }
}

func TestBackupRequiresCompleteStore(t *testing.T) {
    d:=newDisk(t,CopyState{Import:&ImportProgress{Phase:"Transfer"}})
    file:=filepath.Join(t.TempDir(),"copy")
    if err:=BackupCopy(d,file,d.dir);err==nil { t.Fatal("partial import called a complete snapshot") }
    if _,err:=os.Stat(file); !os.IsNotExist(err) { t.Fatal("partial backup wrote file") }
    if err:=BackupCopy(nil,file,d.dir);err==nil { t.Fatal("missing store accepted") }
    if err:=BackupCopy(d,file,"");err==nil { t.Fatal("unknown live data directory accepted") }
}

func TestClockGrammarAndForceBoundary(t *testing.T) {
    opts:=CopyOptions{Now:time.Unix(10,500000000)}
    for _,text:=range []string{"0","10.5","10.500","0.001"} {
        if _,ok:=readCopyTime(text);!ok { t.Fatalf("reader refused %q",text) }
    }
    for _,text:=range []string{"01","1e2","-1","1."," 1","NaN","10.5000","0."+strings.Repeat("0",1000)+"1",strings.Repeat("9",400)} {
        if _,ok:=readCopyTime(text);ok { t.Fatalf("reader accepted %q",text) }
    }
    row:=Row{Key:FloorKey,Items:map[string]string{"floor":"4294967296","generation_at":"10.501"}}
    if err:=checkCopyUpperAndClock([]Row{row},opts);err==nil { t.Fatal("clock comparison lost a fraction") }
    opts.Force=true
    if err:=checkCopyUpperAndClock([]Row{row},opts);err!=nil { t.Fatal("force failed to remove only clock refusal",err) }
    row.Items["generation_at"]="1e2"
    if err:=checkCopyUpperAndClock([]Row{row},opts);err==nil { t.Fatal("force accepted malformed time") }
    row.Items["generation_at"]="10.5"
    row.Items["floor"]="not decimal"
    if err:=checkCopyUpperAndClock([]Row{row},opts);err==nil { t.Fatal("force accepted unreliable upper") }
    epoch:=Row{Key:"testsub/epoch/u1",Items:map[string]string{"epoch":"not decimal"}}
    if err:=checkCopyUpperAndClock([]Row{epoch},opts);err==nil { t.Fatal("bad epoch accepted") }
    text,err:=copyNowText(time.Unix(10,123999999))
    if err!=nil || text!="10.123" { t.Fatal("writer did not retain milliseconds",text,err) }
}

func TestOrdinaryStartupGateUsesDurableProgress(t *testing.T) {
    if CopyStartAllowed(nil)!=nil || CopyStartAllowed(&ImportProgress{Phase:"Done"})!=nil { t.Fatal("complete store refused") }
    for _,phase:=range []string{"Transfer","New floor","corrupt"} {
        if err:=CopyStartAllowed(&ImportProgress{Phase:phase});err==nil { t.Fatal("pending import admitted ordinary writers") }
    }
}

func copyOpts(base uint64) CopyOptions {return CopyOptions{IndexBase:base,Now:time.Date(2026,11,5,12,0,0,123456789,time.UTC)}}
func seedCopy(t *testing.T) []byte {
    t.Helper()
    rows:=[]Row{
        {Key:FloorKey,Index:6,Items:map[string]string{"floor":"4294967296","generation_at":"1760745600.5"}},
        {Key:"testsub/next_id",Index:3,Items:map[string]string{"n":"2"}},
        {Key:"testsub/counters/1",Index:5,Items:map[string]string{"n":"1"}},
        {Key:"platform/manifest/testsub",Index:2,Items:map[string]string{"rev":"1"}},
        {Key:"platform/manifest/testsub2",Index:4,Items:map[string]string{"rev":"2"}},
    }
    raw,err:=EncodeCopy(7,rows);if err!=nil {t.Fatal(err)}
    return raw
}

func TestImportBackupAndInterruptedResumeKeepExactF1(t *testing.T) {
    source:=newDisk(t,CopyState{})
    if err:=ImportCopy(source,seedCopy(t),RowCeiling,copyOpts(7));err!=nil {t.Fatal(err)}
    backup:=filepath.Join(t.TempDir(),"restored-source.copy")
    if err:=BackupCopy(source,backup,source.dir);err!=nil {t.Fatal(err)}
    raw,err:=os.ReadFile(backup);if err!=nil{t.Fatal(err)}
    header,input,copyErr:=DecodeCopy(raw,RowCeiling);if copyErr!=nil{t.Fatal(copyErr)}
    var old Row
    for _,row:=range input {if row.Key==FloorKey {old=row}}
    dest:=newDisk(t,CopyState{})
    dest.failAfter=1
    if err=ImportCopy(dest,raw,RowCeiling,copyOpts(header));err==nil {t.Fatal("controlled I/O error did not interrupt transfer")}
    first,err:=dest.Snapshot();if err!=nil{t.Fatal(err)}
    if first.Import==nil || len(dest.writeLog)!=2 || dest.writeLog[0].Key!=FloorKey || dest.writeLog[1].Key==FloorKey {t.Fatal("F1 was not the first actual row write")}
    f1:=cloneCopyRow(first.Import.Floor)
    oldFloor,_:=readCopyTime(old.Items["floor"]);newFloor,_:=readCopyTime(f1.Items["floor"])
    if oldFloor==nil || newFloor==nil || newFloor.Cmp(oldFloor)<=0 {t.Fatal("F1 not above the source floor")}
    if _,_,err=dest.ordinaryPut("blocked","other/x",map[string]string{});err==nil {t.Fatal("ordinary writers admitted during Transfer")}
    // A new object reopens only the durable file. A later clock would choose a
    // different generation if the controller wrongly ran New floor again.
    reopened:=&diskFixture{dir:dest.dir}
    later:=copyOpts(header);later.Now=time.Date(2300,1,1,0,0,0,0,time.UTC)
    if err=ImportCopy(reopened,raw,RowCeiling,later);err!=nil {t.Fatal(err)}
    done,err:=reopened.Snapshot();if err!=nil{t.Fatal(err)}
    if done.Import.Phase!="Done" || !reflect.DeepEqual(done.Import.Floor,f1) {t.Fatal("resume changed F1 or failed Done")}
    actual,_:=copyRowsByKey(done.Rows)
    if !reflect.DeepEqual(actual[FloorKey],f1) || reflect.DeepEqual(actual[FloorKey],old) {t.Fatal("input floor overwrote F1")}
    for _,want:=range input {if want.Key!=FloorKey && !reflect.DeepEqual(actual[want.Key],want) {t.Fatal("lost row/version",want.Key)}}
    if len(actual)!=len(input) {t.Fatal("not exactly all non-floor input rows plus new F1")}
    for _,row:=range reopened.writeLog {if row.Key==FloorKey {t.Fatal("resume wrote F1 again")}}
    before,_:=os.ReadFile(filepath.Join(reopened.dir,"state.json"))
    if err=ImportCopy(reopened,raw,RowCeiling,later);err==nil {t.Fatal("completed import repeated")}
    after,_:=os.ReadFile(filepath.Join(reopened.dir,"state.json"))
    if !bytes.Equal(before,after) {t.Fatal("repeated import changed the directory")}
}

func TestLostFloorReplyAndIdentityAndCompleteness(t *testing.T) {
    raw:=seedCopy(t)
    d:=newDisk(t,CopyState{})
    d.loseFloorReply=true
    if err:=ImportCopy(d,raw,RowCeiling,copyOpts(7));err==nil {t.Fatal("lost reply hidden")}
    p,_:=d.Snapshot()
    reopened:=&diskFixture{dir:d.dir}
    before,_:=os.ReadFile(filepath.Join(d.dir,"state.json"))
    changed:=bytes.Replace(raw,[]byte(`"format":`),[]byte(`"format" :`),1)
    if bytes.Equal(changed,raw){t.Fatal("identity fixture failed to change valid JSON")}
    if _,_,err:=DecodeCopy(changed,RowCeiling);err!=nil{t.Fatal("identity test needs valid equivalent input",err)}
    if err:=ImportCopy(reopened,changed,RowCeiling,copyOpts(7));err==nil {t.Fatal("changed immutable input accepted")}
    after,_:=os.ReadFile(filepath.Join(d.dir,"state.json"));if !bytes.Equal(before,after){t.Fatal("different input mutated pending attempt")}
    if err:=ImportCopy(reopened,raw,RowCeiling,copyOpts(8));err==nil {t.Fatal("changed base accepted")}
    if err:=ImportCopy(reopened,raw,RowCeiling,copyOpts(7));err!=nil {t.Fatal(err)}
    final,_:=reopened.Snapshot()
    if !reflect.DeepEqual(final.Import.Floor,p.Import.Floor) {t.Fatal("lost floor reply allocated another F1")}
    broken:=newDisk(t,CopyState{});broken.dropWrites=true
    if err:=ImportCopy(broken,raw,RowCeiling,copyOpts(7));err==nil {t.Fatal("unexecuted rows claimed complete")}
    actual,_:=broken.Snapshot();if actual.Import.Phase=="Done" {t.Fatal("false completeness admitted writers")}
}

func TestCopyDoesNotCarryIDReplayMemoryOrAdmission(t *testing.T) {
    source:=newDisk(t,CopyState{})
    if _,again,err:=source.ordinaryPut("b1","other/b10",map[string]string{"n":"1"});err!=nil || again {t.Fatal(err)}
    file:=filepath.Join(t.TempDir(),"ids.copy")
    if err:=BackupCopy(source,file,source.dir);err!=nil {t.Fatal(err)}
    raw,_:=os.ReadFile(file)
    index,_,_:=DecodeCopy(raw,RowCeiling)
    dest:=newDisk(t,CopyState{})
    if err:=ImportCopy(dest,raw,RowCeiling,copyOpts(index));err!=nil {t.Fatal(err)}
    saved,err:=dest.record();if err!=nil{t.Fatal(err)}
    original,_:=source.record()
    if len(saved.IDs)!=0 || saved.Admission==original.Admission {t.Fatal("copy carried source replay/admission memory")}
    next,again,err:=dest.ordinaryPut("b1","other/b10",map[string]string{"n":"1"})
    if err!=nil || again || next<=index {t.Fatal("first ordinary replay after import",next,again,err)}
    _,again,err=dest.ordinaryPut("b1","other/b10",map[string]string{"n":"1"})
    if err!=nil || !again {t.Fatal("new store did not remember its own first replay",again,err)}
}

func TestPreflightNeverMutatesBeforeRefusing(t *testing.T) {
    raw:=seedCopy(t)
    _,rows,parseErr:=DecodeCopy(raw,RowCeiling);if parseErr!=nil{t.Fatal(parseErr)}
    overflowRows:=append([]Row{},rows...)
    for i:=range overflowRows {overflowRows[i]=cloneCopyRow(overflowRows[i]);if overflowRows[i].Key==FloorKey {overflowRows[i].Items["floor"]=strconv.FormatUint(math.MaxUint64,10)}}
    overflow,err:=EncodeCopy(7,overflowRows);if err!=nil{t.Fatal(err)}
    invalidRows:=append([]Row{},rows...)
    for i:=range invalidRows {invalidRows[i]=cloneCopyRow(invalidRows[i]);if invalidRows[i].Key==FloorKey {invalidRows[i].Items["generation_at"]="not time"}}
    invalid,err:=EncodeCopy(7,invalidRows);if err!=nil{t.Fatal(err)}
    forced:=copyOpts(7);forced.Force=true
    future:=copyOpts(7);future.Now=time.Date(2300,1,1,0,0,0,0,time.UTC)
    for _,p:=range []struct{data []byte;opts CopyOptions;initial CopyState}{
        {raw,copyOpts(6),CopyState{}},
        {raw,copyOpts(math.MaxUint64),CopyState{}},
        {overflow,forced,CopyState{}},
        {invalid,forced,CopyState{}},
        {raw,future,CopyState{}},
        {raw,copyOpts(7),CopyState{Index:math.MaxUint64}},
        {raw,copyOpts(7),CopyState{Index:1,Rows:[]Row{{Key:"other/not-fresh",Index:1,Items:map[string]string{}}}}},
    } {
        d:=newDisk(t,p.initial)
        before,_:=os.ReadFile(filepath.Join(d.dir,"state.json"))
        if err=ImportCopy(d,p.data,RowCeiling,p.opts);err==nil{t.Fatal("bad input/base/upper/freshness accepted")}
        after,_:=os.ReadFile(filepath.Join(d.dir,"state.json"))
        if !bytes.Equal(before,after) || len(d.writeLog)!=0 {t.Fatal("refusal mutated the target")}
    }
}

type emptyPort struct{}
func(emptyPort)WithCopyLock(func(CopyTxn)error)error{return nil}
type swallowedPort struct{store *diskFixture}
func(s swallowedPort)WithCopyLock(fn func(CopyTxn)error)error {
    return s.store.WithCopyLock(func(tx CopyTxn)error{_ = fn(tx);return nil})
}
func TestStoragePortMustExecuteAndPropagateOutcome(t *testing.T) {
    if err:=ImportCopy(emptyPort{},seedCopy(t),RowCeiling,copyOpts(7));err==nil{t.Fatal("unexecuted storage port reported successful import")}
    if err:=BackupCopy(emptyPort{},filepath.Join(t.TempDir(),"copy"),t.TempDir());err==nil{t.Fatal("unexecuted storage port reported successful backup")}
    d:=newDisk(t,CopyState{});d.failAfter=1
    if err:=ImportCopy(swallowedPort{d},seedCopy(t),RowCeiling,copyOpts(7));err==nil{t.Fatal("host swallowed the actual transfer I/O failure")}
    actual,err:=d.Snapshot();if err!=nil{t.Fatal(err)}
    if actual.Import==nil || actual.Import.Phase!="Transfer"{t.Fatal("not an executed interrupted transfer")}
}
'''


class CopyStorage(unittest.TestCase):
    def module(self, mod):
        for name in ("go.mod", "apidoor", "jsonstrict", "refusals", "flags", "box", "launch", "coreadapter", "admin"):
            src = OUT / name
            if src.is_dir():
                shutil.copytree(src, mod / name)
            else:
                shutil.copyfile(src, mod / name)
        (mod / "box/copy_storage_test.go").write_text(BACKUP_TEST, encoding="utf-8")

    def test_copy_port_with_real_files_and_restart(self):
        with tempfile.TemporaryDirectory(prefix="normgen-copy-") as tmp:
            mod = Path(tmp)
            self.module(mod)
            done = subprocess.run(["go", "test", "-race", "-count=1", "-v", "./box"], cwd=mod, env=ENV,
                                  capture_output=True, text=True, timeout=120)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            for name in ("TestBackupUsesDurableRowsVersionsAndNoIDMemory", "TestBackupFailureKeepsExistingFile",
                         "TestBackupInsideDataAndLinkRefuseBeforeStoreAccess", "TestBackupRequiresCompleteStore",
                         "TestClockGrammarAndForceBoundary", "TestOrdinaryStartupGateUsesDurableProgress",
                         "TestImportBackupAndInterruptedResumeKeepExactF1", "TestLostFloorReplyAndIdentityAndCompleteness",
                         "TestCopyDoesNotCarryIDReplayMemoryOrAdmission", "TestPreflightNeverMutatesBeforeRefusing",
                         "TestStoragePortMustExecuteAndPropagateOutcome"):
                self.assertIn("--- PASS: " + name, done.stdout)

    def test_published_51_steps_through_actual_commands_and_files(self):
        import gate
        with (ROOT / "Platform/01-store/forms/stages.kit.tsv").open() as stream:
            stages = list(csv.DictReader((line for line in stream if not line.startswith("#")), delimiter="\t"))
        stage = next(row for row in stages if row["stage"] == "daemon_copy")
        names = set()
        for item in gate.parse(stage["gate"]):
            if item.kind == "accept" and item.chapter == "1.3":
                self.assertIsNotNone(item.names, "use the exact published ordinary scenarios, not a guessed wildcard")
                names.update(item.names)
        inputs = ROOT / "Platform/01-store/acceptance/3"
        with (inputs / "scenarios.tsv").open() as stream:
            steps = [row for row in csv.DictReader((line for line in stream if not line.startswith("#")), delimiter="\t")
                     if row["scenario"] in names]
        self.assertEqual(len(steps), 51)
        self.assertEqual({row["scenario"] for row in steps}, names)
        with tempfile.TemporaryDirectory(prefix="normgen-copy-51-") as tmp:
            mod = Path(tmp)
            self.module(mod)
            (mod / "box/copy_scenarios_test.go").write_text(SCENARIO_TEST, encoding="utf-8")
            (mod / "coreadapter/seams.go").write_text(SEAM_BRIDGE, encoding="utf-8")
            fixture = mod / "public-copy-steps.json"
            manifests = {name: str(ROOT / "Platform/common/data/testsub" / f"{name}.subsystem.yaml")
                         for name in ("testsub", "testsub2")}
            with (inputs / "seams.tsv").open() as stream:
                seam = next(row.split("\t") for row in stream if row.startswith("s10-import-floor-resume\t"))
            fixture.write_text(json.dumps({"Steps": steps, "InputDir": str(inputs / "inputs"), "Manifests": manifests,
                                           "SeamRequest": seam[2], "SeamExpect": seam[3].strip()}), encoding="utf-8")
            env = dict(ENV, COPY_JUDGE_SCENARIOS=str(fixture))
            done = subprocess.run(["go", "test", "-race", "-count=1", "-json", "./box"], cwd=mod,
                                  env=env, capture_output=True, text=True, timeout=120)
            events = [json.loads(raw) for raw in done.stdout.splitlines()]
            failed = {event.get("Test", "") for event in events if event.get("Action") == "fail"}
            failure = "".join(event.get("Output", "") for event in events if event.get("Test", "") in failed)
            self.assertEqual(done.returncode, 0, failure + done.stderr)
            actual = {}
            prefix = "TestDaemonCopyExisting51Steps/"
            for raw in done.stdout.splitlines():
                event = json.loads(raw)
                test = event.get("Test", "")
                if test.startswith(prefix) and test.count("/") == 2 and event.get("Action") in ("pass", "fail", "skip"):
                    actual[test[len(prefix):]] = event["Action"]
            self.assertEqual(set(actual), {row["scenario"] + "/" + row["step"] for row in steps})
            self.assertEqual(set(actual.values()), {"pass"})
            self.assertTrue(any(e.get("Test") == "TestPublishedCopyCALLThroughYOURSAndNativeIO" and
                                e.get("Action") == "pass" for e in events))

    def test_runtime_mutants_are_executed_and_killed(self):
        mutants = (
            ("input_floor_transferred", "if row.Key == FloorKey {\n\t\t\t\tcontinue", "if false && row.Key == FloorKey {\n\t\t\t\tcontinue"),
            ("no_continuation", "if state.Import != nil {", "if false && state.Import != nil {"),
            ("row_versions_lost", "tx.WriteImport(cloneCopyRow(row))", "tx.WriteImport(func() Row { r := cloneCopyRow(row); r.Index = 0; return r }())"),
            ("index_not_advanced", "Index: base + 1", "Index: 1"),
            ("false_completeness", "!exists || !sameCopyRow(got, want)", "false && (!exists || !sameCopyRow(got, want))"),
        )
        with tempfile.TemporaryDirectory(prefix="normgen-copy-mutants-") as tmp:
            for name, old, new in mutants:
                with self.subTest(mutant=name):
                    mod = Path(tmp) / name
                    mod.mkdir()
                    self.module(mod)
                    source = mod / "box/copy_import.go"
                    text = source.read_text()
                    self.assertIn(old, text, "mutant must touch its stated runtime check")
                    source.write_text(text.replace(old, new, 1))
                    done = subprocess.run(["go", "test", "-count=1", "./box"], cwd=mod,
                                          env=ENV, capture_output=True, text=True, timeout=120)
                    self.assertNotEqual(done.returncode, 0, name + " survived")
                    self.assertNotIn("build failed", done.stdout + done.stderr)
                    self.assertIn("--- FAIL:", done.stdout, "a compile error is not an executed killed mutant")


class Z21CopyComponent(unittest.TestCase):
    """Selected library/real-file tests only; no live daemon, storage qualification or HTTP proof."""

    source_root = ROOT
    code_root = ROOT
    names = ("TestZ21BackupSnapshotBaseline", "TestZ21BackupPublicationOutsideMutationLock",
             "TestZ21BackupSnapshotDetachedBeforeRelease", "TestZ21BackupLockExitFailureKeepsPublishedFile")

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="z21-copy-library-")
        cls.addClassCleanup(cls.temp.cleanup)
        manifest = output_lesson.output_manifest()
        if manifest["context"]["kind"] not in ("current", "component"):
            raise ValueError("Source21 library controls require an explicit current/component context")
        ready = output_lesson.ready_outputs(source_root=cls.source_root, code_root=cls.code_root,
                                            profiles=tuple(manifest["profiles"]))
        if ready["p01-1"] / "go" != OUT:
            raise ValueError("copy-library output pointer is not the validated P01 component")
        format_, version = z21_copy_contract(cls.source_root)
        cls.template = Z21_BACKUP_TEST.replace("@@FORMAT@@", json.dumps(format_)).replace("@@VERSION@@", json.dumps(str(version)))

    @classmethod
    def tearDownClass(cls):
        # Checking/mutation tests never restore or write to the shared sealed set.
        manifest = output_lesson.output_manifest()
        output_lesson.ready_outputs(source_root=cls.source_root, code_root=cls.code_root,
                                    profiles=tuple(manifest["profiles"]))

    def module(self, name):
        path = Path(self.temp.name) / name
        path.mkdir()
        CopyStorage.module(self, path)
        (path / "box/copy_z21_test.go").write_text(self.template, encoding="utf-8")
        return path

    def test_normal_copy_library_has_complete_independent_observations(self):
        module = self.module("normal")
        failed, observed = z21_go_tests(module, self.names)
        self.assertEqual(failed, [], observed.stdout + observed.stderr)

    def test_valid_runtime_mutants_need_named_semantic_failures(self):
        baseline = self.module("mutation-baseline")
        failed, observed = z21_go_tests(baseline, self.names)
        self.assertEqual(failed, [], "normal Source baseline must pass before mutants\n" + observed.stdout + observed.stderr)
        source = (baseline / "box/copy_storage.go").read_text()
        start, end = source.index("func BackupCopy("), source.index("\n// WriteCopyFile")
        body = source[start:end]

        def once(text, old, new):
            self.assertEqual(text.count(old), 1, "the stated mutation needs one actual subject anchor")
            return text.replace(old, new, 1)

        inside = once(body, "\treturn WriteCopyFile(file, data)\n}", "\treturn nil\n}")
        inside = once(inside, "\t\treturn nil\n\t})", "\t\treturn WriteCopyFile(file, data)\n\t})")
        ignored = once(body, "if lockErr != nil {\n\t\treturn lockErr\n\t}", "if lockErr != nil {\n\t\t_ = lockErr\n\t}")
        alias = once(body, "var data []byte", "var data []byte\n\tvar snapshot CopyState")
        old_encode = ("data, err = EncodeCopy(state.Index, state.Rows)\n\t\tif err != nil {\n"
                      "\t\t\treturn err\n\t\t}")
        alias = once(alias, old_encode, "snapshot = state")
        alias = once(alias, "\treturn WriteCopyFile(file, data)\n}",
                     "\tdata, err := EncodeCopy(snapshot.Index, snapshot.Rows)\n\tif err != nil { return err }\n"
                     "\treturn WriteCopyFile(file, data)\n}")
        cases = (("output-under-lock", inside, "TestZ21BackupPublicationOutsideMutationLock"),
                 ("lock-exit-ignored", ignored, "TestZ21BackupLockExitFailureKeepsPublishedFile"),
                 ("snapshot-alias", alias, "TestZ21BackupSnapshotDetachedBeforeRelease"))
        for name, changed, obligation in cases:
            with self.subTest(mutant=name):
                module = self.module(name)
                (module / "box/copy_storage.go").write_text(source[:start] + changed + source[end:])
                failed, observed = z21_go_tests(module, self.names)
                self.assertIn(obligation, failed, "a normal survivor remains a gap\n" + observed.stdout + observed.stderr)

    def test_real_compiler_error_and_zero_named_report_are_checking_errors(self):
        from test_gen_machine import CheckingError
        module = self.module("checking-error")
        path = module / "box/copy_z21_test.go"
        path.write_text(path.read_text() + "\nthis is not Go\n")
        with self.assertRaises(CheckingError):
            z21_go_tests(module, self.names)
        module = self.module("zero-named-report")
        with self.assertRaises(CheckingError):
            z21_go_tests(module, ("TestZ21NoSuchTest",))


if __name__ == "__main__":
    unittest.main()
