// Событие refresh (P/07 Н1.5 events, Н1.6 events): после каждого опроса страница получает on("refresh", {units,
// servers, domain}) — то, что модуль прочитал (domain — вид /domain, поле позднего слоя); раздел access, прочитав свои
// двери (/domain/users, /domain/grants, /domain/break-glass), испускает refresh {access}. Аудит покрытия P/07 (90661897f).
const fs=require("fs"),path=require("path");
const SRC=require("./module-source")();
const CURRENT=process.env.PC_MODULE_SOURCE==="canonical";
const TMP=path.join(require("os").tmpdir(),"pc-refresh-"+process.pid+".html");
fs.writeFileSync(TMP,`<!doctype html><div id="app"></div><script>${SRC}</script><script>window.pc=PlatformConsole.mount(document.getElementById("app"),{lang:"en",poll_s:0.3});</script>`);
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
b.FIX["/session"]={open:true};
b.FIX["/manifest"]={name:"testsub",rows:"things",id:"numeric",fields:[{name:"name",type:"string"}]};
b.FIX["/things"]={configured:[{id:1,name:"one"}],rows:[{id:1,worker:"w-1",server:"s-1",phase:"running"}]};
b.FIX["/servers"]={servers:{"s-1":{resource:"live",workers:[{worker:"w-1",load:1,capacity:5,state:"live"}]}},policy:{}};
b.FIX["/domain"]={holder:"hold",members:[{name:"hold",holder:true,state:"ok"}],units:{}};
b.FIX["/domain/users"]={users:[{name:"ann",how:"password"}]};
b.FIX["/domain/grants"]={grants:{domain:[{subject:"ann",cap:"admin",scope:"*"}]}};
b.FIX["/domain/break-glass"]={clusters:{}};
(async()=>{
const w=b.boot();const errs=[];w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
// подписка до первого опроса: модуль монтируется синхронно, читает асинхронно
const got=[];w.pc.on("refresh",d=>got.push(d));
await w.pc.ready;await b.ready(100);const d=w.document,out={};
const keys=x=>Object.keys(x||{}).sort().join(",");
const poll=got.filter(x=>keys(x)==="domain,servers,units");
// после опроса: {units, servers, domain} — что пришло
out.refreshAfterMount=poll.length>=1;
const first=poll[0]||{};
out.refreshUnits=Array.isArray((first.units||{}).testsub)&&first.units.testsub.some(u=>u.id===1&&u.name==="one");
out.refreshServers=!!(first.servers||{})["s-1"]&&first.servers["s-1"].resource==="live";
out.refreshDomain=!!first.domain&&first.domain.holder==="hold";
// следующий опрос с изменёнными данными: событие снова, в нём новое
const n=poll.length;
b.FIX["/things"]={configured:[{id:1,name:"one"},{id:2,name:"two"}],rows:[{id:1,worker:"w-1",server:"s-1",phase:"running"}]};
await b.ready(800);
const later=got.filter(x=>keys(x)==="domain,servers,units");
out.refreshEveryPoll=later.length>n;
out.refreshNewData=later.length>n&&later[later.length-1].units.testsub.some(u=>u.id===2&&u.name==="two");
// раздел access, прочитав свои двери, — refresh {access}
const m=got.length;
d.querySelector('.pc-rail [data-s="access"]').click();await b.ready(200);
const acc=got.slice(m).filter(x=>"access" in (x||{}));
out.accessRefresh=acc.length>=1;
out.accessRefreshShape=acc.length>=1&&keys(acc[0])==="access";
out.accessRefreshData=acc.length>=1&&!!acc[0].access&&(acc[0].access.users||[]).some(u=>u.name==="ann")&&!!(acc[0].access.grants||{}).domain;
out.accessAfterItsDoors=acc.length>=1&&["/domain/users","/domain/grants","/domain/break-glass"].every(p=>w.__log.some(x=>x.url===p));
w.close();
if(CURRENT)Object.assign(out,await failureCases(errs));
out.errors=errs;
b.report(out,["errors"]);
try{fs.unlinkSync(TMP)}catch(e){}
process.exitCode=Object.entries(out).some(([key,value])=>key!=="errors"&&value!==true)||errs.length?1:0;
})().catch(error=>{console.error(error);try{fs.unlinkSync(TMP)}catch(e){}process.exitCode=1});

// Управляем только API и часы среды. Периодический callback остаётся callback модуля;
// clearInterval снимает его, поэтому остановка опроса не скрывается ручным вызовом load.
// Счёт событий проверяется после завершения каждого опроса, payload копируется при получении.
async function failureCases(errs){
  const assert=require("node:assert/strict"),out={};
  const plain=x=>JSON.parse(JSON.stringify(x));
  const equal=(a,c)=>{try{assert.deepEqual(plain(a),plain(c));return true}catch(e){return false}};
  const response=(status,value)=>({ok:status===200,status,headers:{get:()=>"application/json"},
    json:async()=>plain(value),text:async()=>JSON.stringify(value)});
  const servers={"s-1":{resource:"live",workers:[]}};
  const head={holder:"hold",members:[{name:"head-member",holder:true,state:"ok"}],units:{testsub:[]},
    pending:{"head-member":0},outcomes:{"head-member":[]},reports:{},contested:{},complete:true};
  const tail={members:[{name:"tail-member",state:"ok"}],units:{testsub:[]}};
  const cursor="opaque/+?=& token";
  const configure=()=>{
    for(const k of Object.keys(b.FIX))delete b.FIX[k];
    b.FIX["/session"]={open:true};
    b.FIX["/manifest"]={name:"testsub",rows:"things",id:"numeric",fields:[{name:"name",type:"string"}]};
    b.FIX["/mounts"]={root:"testsub",mounts:{}};
    b.FIX["/things"]={configured:[{id:1,name:"initial-unit"}],rows:[]};
    b.FIX["/servers"]={servers,policy:{min:1}};
    b.FIX["/unplaceable"]=[];
    b.FIX["/domain"]=head;
    b.FIX["/domain/alarms"]={events:[]};
  };
  function open(holder=false){
    fs.writeFileSync(TMP,`<!doctype html><div id="app"></div><script>${SRC}</script><script>window.pc=PlatformConsole.mount(document.getElementById("app"),{lang:"en",poll_s:1${holder?',sections:["domain"]':''}});</script>`);
    const w=b.boot(),intervals=new Map(),got=[],requests=[];
    let timer=0,rootStatus=200,paged=false,broken=false;
    w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
    w.setInterval=(fn,ms)=>{const id=++timer;intervals.set(id,{fn,ms});return id};
    w.clearInterval=id=>intervals.delete(id);
    const fetch=w.fetch;
    w.fetch=(url,init)=>{
      const p=String(url);
      if(p==="/servers"||p==="/domain"||p.startsWith("/domain?")){
        w.__log.push({method:"GET",url:p,t:Date.now()});requests.push(p);
        if(p==="/servers")return Promise.resolve(response(rootStatus,rootStatus===200?b.FIX[p]:{error:"unavailable"}));
        if(p==="/domain")return Promise.resolve(response(200,paged?{...b.FIX[p],cursor}:b.FIX[p]));
        if(p!=="/domain?cursor="+encodeURIComponent(cursor))return Promise.reject(new Error("unexpected cursor URL: "+p));
        if(broken)return Promise.reject(new TypeError("connection dropped on domain continuation"));
        return Promise.resolve(response(200,tail));
      }
      return fetch(url,init);
    };
    w.pc.on("refresh",data=>got.push(plain(data)));
    return {w,got,requests,setRoot:status=>rootStatus=status,setPages:(on,fail)=>{paged=on;broken=fail},
      async poll(){
        const scheduled=[...intervals.values()].filter(t=>t.ms===1000);
        assert.equal(scheduled.length,1,"one active ordinary poll");
        await scheduled[0].fn();
        await b.ready(0); // queued microtasks and zero-delay work finish before counting events
      }};
  }
  configure();
  let s=open();
  try{
    await s.w.pc.ready;
    out.confirmedRootMap=equal(s.got.map(x=>x.servers),[servers]);
    await s.poll();
    out.unchangedRootRefresh=s.got.length===2&&equal(s.got[1].servers,servers);
    s.setRoot(503);
    b.FIX["/things"]={configured:[{id:1,name:"failed-poll-unit"}],rows:[]};
    b.FIX["/domain"]={...head,holder:"failed-poll-domain"};
    let logStart=s.w.__log.length;
    await s.poll();
    out.failedRootNoRefresh=s.got.length===2; // no other data of this poll reaches the subscriber (R174)
    out.failedRootOrdinaryReads=["/things","/servers","/unplaceable","/domain","/api/held"].every(p=>s.w.__log.slice(logStart).some(x=>x.url===p));
    out.failedRootLocalRepaint=s.w.document.querySelector(".pc-tree").textContent.includes("failed-poll-unit");
    logStart=s.w.__log.length;
    await s.poll();
    out.failedRootNextPoll=s.w.__log.slice(logStart).some(x=>x.url==="/servers")&&s.got.length===2;
    s.setRoot(200);
    b.FIX["/things"]={configured:[{id:1,name:"recovered-unit"}],rows:[]};
    b.FIX["/domain"]=head;
    await s.poll();
    out.sameMapRecovery=s.got.length===3&&equal(s.got[2].servers,servers);
    out.noMissedRefreshReplay=s.got.length===3&&s.got.every(x=>!JSON.stringify(x).includes("failed-poll-"));
    out.recoveryFreshUnits=s.got.length===3&&s.got[2].units.testsub[0].name==="recovered-unit";
    await s.poll();
    out.recoveredOrdinaryFrequency=s.got.length===4;
    b.FIX["/servers"]={servers:{},policy:{min:1}};
    await s.poll();
    out.confirmedEmptyMap=s.got.length===5&&equal(s.got[4].servers,{});
    // Domain continuation: a successful two-page control precedes the failed read.
    s.setPages(true,false);
    await s.poll();
    out.domainTwoPageControl=s.got.length===6&&equal(s.got[5].domain.members.map(m=>m.name),["head-member","tail-member"]);
    s.setPages(true,true);
    const n=s.got.length,start=s.requests.length;
    await s.poll();
    out.domainContinuationRequested=s.requests.slice(start).includes("/domain?cursor="+encodeURIComponent(cursor));
    out.domainFailureNull=s.got.length===n+1&&s.got[n].domain===null;
    out.domainFailureNoPartialView=s.got.slice(n).every(x=>x.domain===null);
    out.domainFailureKeepsRootRefresh=s.got.length===n+1&&equal(s.got[n].servers,{});
    s.setPages(true,false);
    await s.poll();
    out.domainRecovery=s.got.length===n+2&&equal(s.got[n+1].domain.members.map(m=>m.name),["head-member","tail-member"]);
  }finally{s.w.close()}
  // The initial {} is not a successful root observation; there was no earlier map.
  configure();s=open();s.setRoot(503);
  try{
    await s.w.pc.ready;
    out.initialRootFailureNoRefresh=s.got.length===0;
    s.setRoot(200);b.FIX["/servers"]={servers:{},policy:{}};
    await s.poll();
    out.initialRootRecovery=s.got.length===1&&equal(s.got[0].servers,{});
  }finally{s.w.close()}
  // Both loaders share the refusal rule; holder-only refresh has no root gate.
  configure();s=open(true);s.setPages(true,false);
  try{
    await s.w.pc.ready;
    out.holderTwoPageControl=s.got.length===1&&equal(s.got[0].domain.members.map(m=>m.name),["head-member","tail-member"]);
    s.setPages(true,true);let start=s.requests.length;
    await s.poll();
    out.holderContinuationRequested=s.requests.slice(start).includes("/domain?cursor="+encodeURIComponent(cursor));
    out.holderDomainFailureNull=s.got.length===2&&equal(s.got[1],{domain:null});
    out.holderNoRootReads=!s.requests.includes("/servers");
    s.setPages(true,false);await s.poll();
    out.holderDomainRecovery=s.got.length===3&&s.got[2].domain.members.length===2;
  }finally{s.w.close()}
  return out;
}
