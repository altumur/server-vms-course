"""Judge of the copy-to-store port: real files, controlled failures, no implementation-line source."""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out/p01-1/go"
ENV = dict(os.environ, GOFLAGS="-mod=mod", GOPROXY="off", GOWORK="off", GOTOOLCHAIN="local")

BACKUP_TEST = r'''package box

import (
    "bytes"
    "encoding/json"
    "errors"
    "os"
    "path/filepath"
    "reflect"
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
    for _,text:=range []string{"0","10.5","10.5000000000000000000","0."+strings.Repeat("0",1000)+"1"} {
        if _,ok:=readCopyTime(text);!ok { t.Fatalf("reader refused %q",text) }
    }
    for _,text:=range []string{"01","1e2","-1","1."," 1","NaN",strings.Repeat("9",400)} {
        if _,ok:=readCopyTime(text);ok { t.Fatalf("reader accepted %q",text) }
    }
    row:=Row{Key:FloorKey,Items:map[string]string{"floor":"4294967296","generation_at":"10.5000000001"}}
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
    later:=copyOpts(header);later.Now=later.Now.Add(48*time.Hour)
    if err=ImportCopy(reopened,raw,RowCeiling,later);err!=nil {t.Fatal(err)}
    done,err:=reopened.Snapshot();if err!=nil{t.Fatal(err)}
    if done.Import.Phase!="Done" || !sameCopyRow(done.Import.Floor,f1) {t.Fatal("resume changed F1 or failed Done")}
    actual,_:=copyRowsByKey(done.Rows)
    if !sameCopyRow(actual[FloorKey],f1) || sameCopyRow(actual[FloorKey],old) {t.Fatal("input floor overwrote F1")}
    for _,want:=range input {if want.Key!=FloorKey && !sameCopyRow(actual[want.Key],want) {t.Fatal("lost row/version",want.Key)}}
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
'''


class CopyStorage(unittest.TestCase):
    def test_copy_port_with_real_files_and_restart(self):
        with tempfile.TemporaryDirectory(prefix="normgen-copy-") as tmp:
            mod = Path(tmp)
            for name in ("go.mod", "apidoor", "jsonstrict", "refusals", "flags", "box"):
                src = OUT / name
                if src.is_dir():
                    shutil.copytree(src, mod / name)
                else:
                    shutil.copyfile(src, mod / name)
            shutil.copyfile(HERE / "copyrt/go/storage.go", mod / "box/copy_storage.go")
            shutil.copyfile(HERE / "copyrt/go/validation.go", mod / "box/copy_validation.go")
            (mod / "box/copy_storage_test.go").write_text(BACKUP_TEST, encoding="utf-8")
            done = subprocess.run(["go", "test", "-race", "-count=1", "-v", "./box"], cwd=mod, env=ENV,
                                  capture_output=True, text=True, timeout=120)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            for name in ("TestBackupUsesDurableRowsVersionsAndNoIDMemory", "TestBackupFailureKeepsExistingFile",
                         "TestBackupInsideDataAndLinkRefuseBeforeStoreAccess", "TestBackupRequiresCompleteStore",
                         "TestClockGrammarAndForceBoundary", "TestOrdinaryStartupGateUsesDurableProgress",
                         "TestImportBackupAndInterruptedResumeKeepExactF1", "TestLostFloorReplyAndIdentityAndCompleteness",
                         "TestCopyDoesNotCarryIDReplayMemoryOrAdmission"):
                self.assertIn("--- PASS: " + name, done.stdout)


if __name__ == "__main__":
    unittest.main()
