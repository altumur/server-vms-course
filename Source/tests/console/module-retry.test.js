// console.api модуля — P/07 Н1.5 `api`: один Idempotency-Key на логическое действие (вызов api), не на одинаковые
// байты; повторы действия хранят ключ и тело. Потерянный ответ (сеть, таймаут, 5xx, 409 «in flight») повторяется только у
// двери с памятью повторов владельца — POST единиц /<rows>, /<sub>/<rows> (P/06.1); задержка — заголовок Retry-After, без
// него — 2, 3, 5 с; после третьего повтора — отказ с status, body и retry, «Повторить» у уведомления шлёт тем же ключом.
// PUT, DELETE и POST дверей без памяти (/marks, /drain, …) сами не повторяются: при неизвестном исходе — сначала чтение.
// 401 — окно входа.
const fs=require("fs"),path=require("path");
const SRC=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"pc-retry-"+process.pid+".html");
fs.writeFileSync(TMP,`<!doctype html><div id="app"></div><script>${SRC}</script><script>window.pc=PlatformConsole.mount(document.getElementById("app"),{lang:"en"});window.pc.retryWaits=[20,20,20];window.pc.timeoutMs=200;</script>`);
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
b.FIX["/session"]={open:true,login_url:"/api/login"};
b.FIX["/spec"]={name:"testsub",rows:"things",id:"numeric",fields:[{name:"name",type:"string"}]};
b.FIX["/mounts"]={root:"testsub",mounts:{sub:{name:"sub",rows:"parts",id:"name",fields:[{name:"size",type:"int"}]}}};
b.FIX["/things"]={configured:[],rows:[]};
b.FIX["/sub/parts"]={configured:[],rows:[]};
b.FIX["/servers"]={servers:{},policy:{}};
(async()=>{
const w=b.boot();const errs=[];w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
await w.pc.ready;const d=w.document,pc=w.pc,out={};
const plan={},sent=[];const base=w.fetch;
const res=(status,body,ra)=>({ok:status>=200&&status<300,status,headers:{get:k=>k==="Retry-After"&&ra!==undefined?ra:k==="Content-Type"?"application/json":null},json:()=>Promise.resolve(body),text:()=>Promise.resolve(JSON.stringify(body))});
w.fetch=(url,init)=>{
  const m=init&&init.method||"GET";if(m==="GET")return base(url,init);
  sent.push({m,path:url,key:(init.headers||{})["Idempotency-Key"]||"",body:init.body,t:Date.now()});
  const s=(plan[url]||[]).shift();
  if(s==="net")return Promise.reject(new TypeError("Failed to fetch"));
  if(s==="hang")return new Promise((_,no)=>init.signal.addEventListener("abort",()=>{const e=new Error("aborted");e.name="AbortError";no(e)}));
  if(s===503)return Promise.resolve(res(503,{detail:"busy",error:"busy"}));
  if(s==="ra0")return Promise.resolve(res(503,{detail:"busy",error:"busy"},"0"));
  if(s==="inflight")return Promise.resolve(res(409,{detail:"in flight: another console holds this key"}));
  if(s===409)return Promise.resolve(res(409,{detail:"recording exists"}));
  if(s===400)return Promise.resolve(res(400,{detail:"bad name"}));
  if(s===401)return Promise.resolve(res(401,{detail:"sign in",error:"denied"}));
  return Promise.resolve(res(200,{id:"7"}));
};
const call=async(m,p,body)=>{try{return{ok:await pc.api(m,p,body)}}catch(e){return{err:e.message,status:e.status,body:e.body,retry:e.retry}}};
const keys=n=>sent.slice(-n).map(x=>x.key);
const same=a=>a.length>0&&a[0]!==""&&a.every(k=>k===a[0]);
const reads=()=>w.__log.filter(x=>x.method==="GET"&&x.url==="/things").length;
// дверь с памятью повторов: POST /<rows> и /<sub>/<rows>
plan["/things"]=[503,"net"];let x=await call("POST","/things",{name:"a"});
out.rowsRetriedOn5xxAndNet=!!x.ok&&sent.length===3&&same(keys(3))&&sent.every(s=>s.body===JSON.stringify({name:"a"}));
plan["/sub/parts"]=["inflight","inflight"];x=await call("POST","/sub/parts",{size:1});
out.subRowsRetriedOnInFlight=!!x.ok&&same(keys(3))&&sent.length===6;
plan["/things"]=["hang"];x=await call("POST","/things",{name:"t"});
out.rowsRetriedOnTimeout=!!x.ok&&same(keys(2));
// ключ — на действие: тот же запрос с тем же телом новым вызовом — новый ключ
const k1=keys(1)[0];x=await call("POST","/things",{name:"t"});out.newCallNewKeySameBody=!!x.ok&&keys(1)[0]!==k1&&keys(1)[0]!=="";
// Retry-After: заголовок, не поле тела; ожидание по умолчанию 2, 3, 5 с
pc.retryWaits=[2000,3000,5000];plan["/things"]=["ra0"];let t0=Date.now();x=await call("POST","/things",{name:"ra"});
out.retryAfterHeader=!!x.ok&&Date.now()-t0<1000&&same(keys(2));
out.defaultWaits=JSON.stringify(pc.retryWaits)==="[2000,3000,5000]";
pc.retryWaits=[20,20,20];
// окончательные ответы: 4xx и простой 409 не повторяются
let n=sent.length;plan["/things"]=[400];x=await call("POST","/things",{name:"r"});
out.noRetryOn4xx=!!x.err&&/bad name/.test(x.err)&&x.status===400&&x.body.detail==="bad name"&&sent.length===n+1;
n=sent.length;plan["/things"]=[409];x=await call("POST","/things",{name:"B"});
out.plain409IsFinal=!!x.err&&x.status===409&&sent.length===n+1;
// исчерпаны повторы: четыре отправки одним ключом, отказ с status, body и retry; «Повторить» — тот же ключ и тело
n=sent.length;plan["/things"]=["net","net","net",503];x=await call("POST","/things",{name:"b"});
out.givesUpAfterThirdRepeat=!!x.err&&sent.length===n+4&&same(keys(4))&&/not lost/.test(x.err);
out.giveUpHasStatusBody=x.status===503&&!!x.body&&x.body.error==="busy"&&!!x.retry&&x.retry.path==="/things";
const kLost=keys(1)[0];
pc.toast("refused: "+x.err);
const btn=d.querySelector(".pc-toast .pc-retry");
out.toastHasRetry=!!btn;
if(btn)btn.click();await b.ready(120);
out.retryButtonSameKey=sent.at(-1).key===kLost&&sent.at(-1).path==="/things"&&JSON.parse(sent.at(-1).body).name==="b";
// дверь без памяти повторов: POST /marks, /drain, decommission; PUT; DELETE — без автоповтора, сначала чтение
for(const [m,p,body,label] of [["POST","/marks",{unit:"testsub/1",note:"x"},"marks"],["POST","/drain?server=s-1",undefined,"drain"],["POST","/servers/s-1/decommission",{why:"x"},"decommission"],["PUT","/things/1",{name:"e"},"put"],["DELETE","/things/1",undefined,"delete"]]){
  n=sent.length;const r0=reads();plan[p]=["net"];x=await call(m,p,body);
  out["noRepeat_"+label]=!!x.err&&sent.length===n+1&&/outcome unknown/.test(x.err)&&!x.retry;
  out["readFirst_"+label]=reads()>r0;
}
n=sent.length;plan["/marks"]=[503];x=await call("POST","/marks",{unit:"testsub/1",note:"y"});
out.marks5xxNotRepeated=!!x.err&&sent.length===n+1&&x.status===503;
out.deleteNoKey=sent.filter(s=>s.m==="DELETE").every(s=>s.key==="");
out.putKeyed=sent.filter(s=>s.m==="PUT").every(s=>s.key!=="");
// 401 — окно входа
plan["/things/1"]=[401];x=await call("PUT","/things/1",{name:"f"});
out.on401Login=x.status===401&&d.querySelector(".pc-login").hidden===false;
pc.toast("Saved");out.plainToastNoButton=!d.querySelector(".pc-toast .pc-retry");
out.errors=errs;
b.report(out,["errors"]);
try{fs.unlinkSync(TMP)}catch(e){}
process.exit(0);
})();
