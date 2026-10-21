// Что зовёт модуль — закрытый список P/07 Н1.4 (и Н1.6 у страницы держателя): каждый перехваченный запрос модуля,
// метод и путь, сверяется со списком `reads`/`writes`, пути `never` не появляются ни при монтировании, ни при опросе,
// ни при выборе и правках; порядок `order` при монтировании и на каждом опросе (каждые poll_s), `/events?unit=`
// выбранной единицы — каждые 5 с. Дверь держателя из where() модуль не зовёт: она только оболочке.
const fs=require("fs"),path=require("path");
const SRC=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"pc-calls-"+process.pid+".html");
const page=opts=>fs.writeFileSync(TMP,`<!doctype html><div id="app"></div><script>${SRC}</script><script>window.pc=PlatformConsole.mount(document.getElementById("app"),${opts});window.pc.retryWaits=[10,10,10];</script>`);
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
function cluster(){
  for(const k of Object.keys(b.FIX))delete b.FIX[k];
  b.FIX["/session"]={open:true,login_url:"/api/login"};
  b.FIX["/spec"]={name:"testsub",rows:"things",id:"numeric",running_gauge:"testsub_things_running",workers_gauge:"testsub_workers_live",
    fields:[{name:"name",type:"string"},{name:"labels",type:"list"}],servers:{show:[{table:"places",by:"server"}]},
    display:{tree:{group_by:"labels"}},domain:{shared:["labels"]}};
  b.FIX["/mounts"]={root:"testsub",mounts:{sub:{name:"sub",rows:"parts",id:"name",fields:[{name:"size",type:"int"}]}}};
  b.FIX["/things"]={configured:[{id:1,name:"one",labels:["a"]}],rows:[{id:1,worker:"w-1",server:"s-1",phase:"running"}]};
  b.FIX["/sub/parts"]={configured:[{id:"p1",size:1}],rows:[]};
  b.FIX["/servers"]={servers:{"s-1":{resource:"live",workers:[{worker:"w-1",load:1,capacity:5,labels:[],state:"live",idle_by_policy:false,hung:false,name_conflict:null}]}},policy:{}};
  b.FIX["/unplaceable"]=[];b.FIX["/sub/unplaceable"]=[];
  b.FIX["/domain/shared/testsub"]={fields:{labels:{groups:[]}},rev:1};
  b.FIX["/drain"]={draining:"",safe:true,subsystems:{}};b.FIX["/schema"]={};
  b.FIX["/domain"]={holder:"hold",members:[],units:{}};b.FIX["/domain/alarms"]={events:[]};
  b.FIX["/metrics"]="testsub_things_running 1\ntestsub_workers_live 1\n";
  b.FIX["/events"]={events:[],state:"live"};b.FIX["/marks"]={ok:true};
  b.FIX["/where/1"]={worker:"w-1",server:"s-1",reason:"most free",door:{url:"http://holder-door:9/",token:"t",expires:9,routes:["read"]}};
  b.FIX["/testsub/places"]={places:[{name:"pl-1",server:"s-1"}]};
}
// Н1.4 для этой спеки: корень testsub (/<rows> = /things, таблица servers.show — places), смонтированная sub (/sub/parts)
const SUBS=[{name:"testsub",base:"",rows:"things",show:["places"]},{name:"sub",base:"/sub",rows:"parts",show:[]}];
function allowed(method,url,loginUrl){
  const u=new URL(url,"http://localhost/");
  if(u.origin!=="http://localhost")return false;   // двери держателей (door из where) — только оболочке
  const p=u.pathname,seg=p.split("/").slice(1);
  const rows=SUBS.some(s=>p===s.base+"/"+s.rows),row=SUBS.some(s=>p.startsWith(s.base+"/"+s.rows+"/")&&p.slice((s.base+"/"+s.rows+"/").length).indexOf("/")<0);
  if(method==="GET"){
    if(["/session","/spec","/mounts","/servers","/unplaceable","/policy","/drain","/schema","/events","/metrics","/api/held"].includes(p))return true;
    if(SUBS.some(s=>s.base&&(p===s.base+"/spec"||p===s.base+"/unplaceable"||p.startsWith(s.base+"/where/"))))return true;
    if(rows||p.startsWith("/where/"))return true;
    if(SUBS.some(s=>s.show.some(t=>p==="/"+s.name+"/"+t)))return true;   // /<sub>/<table> только из servers.show
    if(p==="/domain"||p.startsWith("/domain/"))return true;
    if(/^\/servers\/[^/]+\/labels$/.test(p))return true;
    return false;
  }
  if(["POST","PUT","DELETE"].includes(method)&&(rows&&method==="POST"||row&&method!=="POST"))return true;
  if(method==="POST"&&p==="/marks")return true;
  if(method==="PUT"&&p==="/policy")return true;
  if((method==="POST"||method==="DELETE")&&p==="/drain")return true;
  if((method==="PUT"||method==="DELETE")&&/^\/servers\/[^/]+\/labels$/.test(p))return true;
  if((method==="POST"||method==="DELETE")&&/^\/servers\/[^/]+\/decommission$/.test(p))return true;
  if(p==="/domain"||p.startsWith("/domain/"))return true;
  if((method==="POST"||method==="DELETE")&&p==="/session")return true;
  if(method==="POST"&&(p==="/session/break-glass"||p===loginUrl))return true;
  return false;
}
const never=url=>{const p=new URL(url,"http://localhost/").pathname;return /^\/[^/]+\/requests(\/|$)/.test(p)||p==="/api/backup"||p.startsWith("/resources")||/^\/testsub\/(?!places$)[^/]+$/.test(p)||!url.startsWith("/")&&!url.startsWith("http://localhost/");};
const gets=(log,from)=>log.slice(from||0).filter(x=>x.method==="GET").map(x=>new URL(x.url,"http://localhost/").pathname);
const ORDER=["/things","/sub/parts","/servers","/unplaceable","/sub/unplaceable","/domain/shared/testsub","/drain","/schema","/domain","/domain/alarms","/api/held","/metrics"];
(async()=>{
const out={};
// --- кластер: монтирование и опрос (poll_s 0.3 с)
cluster();page(`{lang:"en",poll_s:0.3}`);
let w=b.boot();const errs=[];w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
w.confirm=()=>true;
await w.pc.ready;const mountEnd=w.__log.length,mountAt=Date.now();
out.orderAtMount=JSON.stringify(gets(w.__log).slice(0,mountEnd))===JSON.stringify(["/session","/spec","/mounts",...ORDER]);
out.orderAtMountGot=gets(w.__log).join(" ");
await b.ready(1000);
const polls=[];{const g=gets(w.__log,mountEnd);let cur=null;for(const p of g){if(p==="/things"){cur=[];polls.push(cur)}if(cur)cur.push(p)}}
out.pollsEveryPollS=polls.length>=2&&polls.length<=5;
out.pollOrder=polls.length>=2&&polls.slice(0,-1).every(x=>JSON.stringify(x)===JSON.stringify(ORDER));
out.pollNoSessionOrSpec=!gets(w.__log,mountEnd).some(p=>p==="/session"||p==="/spec"||p==="/mounts");
// --- выбор единицы: /events?unit= выбранной каждые 5 с, where() даёт дверь, модуль туда не ходит
const pc=w.pc,d=w.document;
pc.select("unit:testsub/1");await b.ready(200);
const wh=await pc.where("unit:testsub/1");
out.whereDoorObject=!!wh&&wh.door&&wh.door.url==="http://holder-door:9/"&&wh.worker==="w-1";
d.querySelector("main").querySelector('.pc-tabs [data-tab="events"]').click();await b.ready(150);
// правки модуля: отметка, сохранение формы, новая единица
const mark=d.querySelector(".pc-mark");if(mark){mark.elements.note.value="hi";mark.dispatchEvent(new w.Event("submit",{cancelable:true}))}await b.ready(100);
d.querySelector("main").querySelector('.pc-tabs [data-tab="general"]').click();await b.ready(80);
const form=d.querySelector(".pc-edit");form.elements.name.value="uno";form.dispatchEvent(new w.Event("submit",{cancelable:true}));await b.ready(150);
pc.select(null);await b.ready(30);d.querySelector(".pc-hd [data-new='testsub']").click();await b.ready(30);
const nf=d.querySelector("main .pc-new-f");nf.elements.name.value="two";nf.dispatchEvent(new w.Event("submit",{cancelable:true}));await b.ready(150);
out.writesSeen=["POST /marks","PUT /things/1","POST /things"].every(k=>w.__log.some(x=>x.method+" "+new URL(x.url,"http://localhost/").pathname===k));
// серверы: карточка сервера (таблица servers.show — /testsub/places), воркер, журнал
pc.select("server:s-1");await b.ready(150);
pc.select("worker:testsub/w-1");await b.ready(80);
d.querySelector('.pc-rail [data-s="journal"]').click();await b.ready(150);
d.querySelector('.pc-rail [data-s="units"]').click();await b.ready(50);
pc.select("unit:testsub/1");await b.ready(50);d.querySelector("main").querySelector('.pc-tabs [data-tab="events"]').click();await b.ready(Math.max(0,mountAt+10500-Date.now()));
const unitEv=w.__log.filter(x=>x.method==="GET"&&/^\/events\?/.test(x.url)&&new URL(x.url,"http://localhost/").searchParams.get("unit")==="testsub/1").map(x=>x.t);
out.unitEventsEvery5s=unitEv.some(a=>unitEv.some(c=>Math.abs(c-a-5000)<400));
out.showTableBySub=w.__log.some(x=>x.url==="/testsub/places");
const bad=w.__log.filter(x=>!allowed(x.method,x.url,"/api/login"));
out.everyCallListed=bad.length===0;out.unlisted=bad.map(x=>x.method+" "+x.url).slice(0,5).join(", ");
out.neverCalled=!w.__log.some(x=>never(x.url));
out.holderDoorNotCalled=!w.__log.some(x=>x.url.includes("holder-door"));
w.close();
// --- страница держателя (sections: [domain], Н1.6 holder): без единиц, /servers, /unplaceable; всё — из списка
for(const k of Object.keys(b.FIX))delete b.FIX[k];
b.FIX["/session"]={open:true,login_url:"/api/login"};b.FIX["/spec"]={name:"",rows:null};
b.FIX["/mounts"]={root:"",mounts:{testsub:{name:"testsub",rows:"things",id:"name",fields:[{name:"name",type:"string"}],domain:{edit:[],view:[],shared:[]}}}};
b.FIX["/domain"]={holder:"hold",members:[{name:"hold",holder:true,state:"ok"}],units:{testsub:[]}};b.FIX["/domain/alarms"]={events:[]};
b.FIX["/domain/shared"]={doc:{rev:1,shared:{}},delivery:{},declared:{}};
page(`{lang:"en",sections:["domain"],poll_s:0.3}`);
w=b.boot();await w.pc.ready;await b.ready(700);
const hg=gets(w.__log);
out.holderOrder=JSON.stringify(hg.slice(0,6))===JSON.stringify(["/session","/spec","/mounts","/domain","/domain/alarms","/domain/shared"]);
out.holderNoClusterReads=!hg.some(p=>["/servers","/unplaceable","/drain","/schema","/metrics","/events"].includes(p)||p.startsWith("/sub/")||p.endsWith("/things"));
out.holderEveryCallListed=w.__log.every(x=>allowed(x.method,x.url,"/api/login"));
w.close();
out.errors=errs;
b.report(out,["errors","unlisted","orderAtMountGot"]);
try{fs.unlinkSync(TMP)}catch(e){}
process.exit(0);
})();
