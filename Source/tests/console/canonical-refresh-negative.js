// Отрицательные контроли P07.21: изменяются только собственные временные копии.
// Запуск: node canonical-refresh-negative.js. Канонические байты дерева не записываются.
const assert=require("node:assert/strict");
const fs=require("node:fs"),os=require("node:os"),path=require("node:path");
const {spawnSync}=require("node:child_process");
const {createHash}=require("node:crypto");
const file=path.resolve(__dirname,"../../../Platform/07-console-module/module/console.js");
const bytes=fs.readFileSync(file),source=bytes.toString("utf8");
const sha256=data=>createHash("sha256").update(data).digest("hex");
const mutants=[
  {name:"unconfirmed-root-refresh",
    from:'if (rootConfirmed) emit("refresh", { units: st.units, servers: rootServers, domain: observedDomain.value });',
    to:'emit("refresh", { units: st.units, servers: rootServers, domain: observedDomain.value });',
    failures:["failedRootNoRefresh","failedRootNextPoll","initialRootFailureNoRefresh"]},
  {name:"successful-domain-prefix",
    from:'return { phase: "error", value: null, error: e && e.message || W.refused, normalIncomplete: false, lastKnown: domainLastKnown };',
    to:'return { phase: "error", value: head && { ...head, members: [...members.values()] }, error: e && e.message || W.refused, normalIncomplete: false, lastKnown: domainLastKnown };',
    failures:["domainFailureNull","domainFailureNoPartialView","holderDomainFailureNull"]}
];
for(const mutant of mutants){
  assert.equal(source.split(mutant.from).length,2,"exactly one mutation site: "+mutant.name);
  const tmp=fs.mkdtempSync(path.join(os.tmpdir(),"p07-refresh-negative-"));
  try{
    const tests=path.join(tmp,"Source/tests/console"),canonical=path.join(tmp,"Platform/07-console-module/module/console.js");
    fs.mkdirSync(tests,{recursive:true});fs.mkdirSync(path.dirname(canonical),{recursive:true});
    for(const name of ["boot.js","module-source.js","module-refresh-event.test.js"])fs.copyFileSync(path.join(__dirname,name),path.join(tests,name));
    fs.symlinkSync(path.join(__dirname,"node_modules"),path.join(tests,"node_modules"),"dir");
    const changed=source.replace(mutant.from,mutant.to);fs.writeFileSync(canonical,changed);
    const child=spawnSync(process.execPath,[path.join(tests,"module-refresh-event.test.js")],{
      cwd:tests,env:{...process.env,PC_MODULE_SOURCE:"canonical"},encoding:"utf8",timeout:30000,maxBuffer:1024*1024
    });
    assert.ifError(child.error);assert.equal(child.status,1,"mutant must fail assertions");
    assert.equal(child.stderr,"","no crash or runtime diagnostics");
    const lines=child.stdout.split("\n"),start=lines.indexOf("{"),end=lines.lastIndexOf("}");
    assert.ok(start>=0&&end>start,"fixture assertion report");
    const report=JSON.parse(lines.slice(start,end+1).join("\n"));assert.deepEqual(report.errors,[]);
    for(const name of mutant.failures)assert.equal(report[name],false,"target assertion: "+name);
    assert.ok(lines.some(line=>line.startsWith("FAILED: ")),"red fixture verdict");
    assert.equal(fs.readFileSync(file).equals(bytes),true,"canonical bytes unchanged");
    console.log(JSON.stringify({mutant:mutant.name,source:file,source_sha256:sha256(bytes),mutant_sha256:sha256(changed),
      fixture_exit:child.status,failures:mutant.failures,result:"EXPECTED_FAIL",canonical_unchanged:true}));
  }finally{fs.rmSync(tmp,{recursive:true,force:true})}
}
