// Одна отправка — один ключ (console.api модуля, как в консоли продукта): тот же запрос с тем же телом повторяется с тем
// же Idempotency-Key, пока ответ не окончательный (сеть, таймаут, 5xx, 409 «in flight» — не ответ); 2xx и 4xx ключ
// закрывают; DELETE — без ключа и без повтора; кончились попытки — отказ «не потеряно», и «Повторить» у уведомления
// шлёт тем же ключом.
const fs=require("fs"),path=require("path");
const SRC=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"pc-retry-"+process.pid+".html");
fs.writeFileSync(TMP,`<!doctype html><div id="app"></div><script>${SRC}</script><script>window.pc=PlatformConsole.mount(document.getElementById("app"),{lang:"en",poll_s:0});window.pc.retryWaits=[20,20,20];window.pc.timeoutMs=200;</script>`);
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
b.FIX["/session"]={open:true};
b.FIX["/spec"]={name:"testsub",rows:"things",id:"numeric",fields:[{name:"name",type:"string"}]};
b.FIX["/things"]={configured:[],rows:[]};
b.FIX["/servers"]={servers:{},policy:{}};
(async()=>{
const w=b.boot();const errs=[];w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
await b.ready(600);await w.pc.ready;const d=w.document,pc=w.pc,out={};
const plan={},sent=[];const base=w.fetch;
const res=(status,body)=>({ok:status>=200&&status<300,status,headers:{get:()=>"application/json"},json:()=>Promise.resolve(body),text:()=>Promise.resolve(JSON.stringify(body))});
w.fetch=(url,init)=>{
  const m=init&&init.method||"GET";if(m==="GET")return base(url,init);
  sent.push({m,path:url,key:(init.headers||{})["Idempotency-Key"]||"",body:init.body});
  const s=(plan[url]||[]).shift();
  if(s==="net")return Promise.reject(new TypeError("Failed to fetch"));
  if(s==="hang")return new Promise((_,no)=>init.signal.addEventListener("abort",()=>{const e=new Error("aborted");e.name="AbortError";no(e)}));
  if(s===503)return Promise.resolve(res(503,{detail:"busy",retry_after:0}));
  if(s==="inflight")return Promise.resolve(res(409,{detail:"in flight: another console holds this key"}));
  if(s===409)return Promise.resolve(res(409,{detail:"recording exists"}));
  if(s===400)return Promise.resolve(res(400,{detail:"bad name"}));
  return Promise.resolve(res(200,{id:"7"}));
};
const call=async(m,p,body)=>{try{return{ok:await pc.api(m,p,body)}}catch(e){return{err:e.message}}};
const keys=n=>sent.slice(-n).map(x=>x.key);
const same=a=>a.length>0&&a[0]!==""&&a.every(k=>k===a[0]);
plan["/things"]=[503,"net"];let x=await call("POST","/things",{name:"a"});
out.retriedOn5xxAndNet=!!x.ok&&sent.length===3&&same(keys(3));
plan["/sub/x"]=["inflight","inflight"];x=await call("POST","/sub/x",{ref:"A"});
out.retriedOnInFlight=!!x.ok&&same(keys(3))&&sent.length===6;
plan["/marks"]=["hang"];x=await call("POST","/marks",{t:1});
out.retriedOnTimeout=!!x.ok&&same(keys(2));
const k1=keys(1)[0];x=await call("POST","/marks",{t:1});out.newKeyAfterSuccess=!!x.ok&&keys(1)[0]!==k1;
let n=sent.length;plan["/sub/r"]=[400];x=await call("POST","/sub/r",{name:"r"});
out.noRetryOn4xx=!!x.err&&/bad name/.test(x.err)&&sent.length===n+1;
const k400=keys(1)[0];x=await call("POST","/sub/r",{name:"r"});out.keyClosedAfter4xx=!!x.ok&&keys(1)[0]!==k400;
n=sent.length;plan["/sub/b"]=[409];x=await call("POST","/sub/b",{ref:"B"});
out.plain409IsFinal=!!x.err&&sent.length===n+1;
n=sent.length;plan["/things"]=["net","net","net","net"];x=await call("POST","/things",{name:"b"});
out.givesUpAfter4=!!x.err&&sent.length===n+4&&same(keys(4))&&/not lost/.test(x.err);
const kLost=keys(1)[0];
pc.toast("refused: "+x.err);
const btn=d.querySelector(".pc-toast .pc-retry");
out.toastHasRetry=!!btn;
if(btn)btn.click();await b.ready(120);
out.retryButtonSameKey=sent.at(-1).key===kLost&&sent.at(-1).path==="/things"&&JSON.parse(sent.at(-1).body).name==="b";
plan["/things"]=["net","net","net","net"];await call("POST","/things",{name:"c"});const kc=keys(1)[0];
x=await call("POST","/things",{name:"c"});out.sameFormSameKey=!!x.ok&&keys(1)[0]===kc;
plan["/things"]=["net","net","net","net"];await call("POST","/things",{name:"d"});const kd=keys(1)[0];
x=await call("POST","/things",{name:"d2"});out.otherBodyNewKey=!!x.ok&&keys(1)[0]!==kd;
plan["/things/1"]=[503];x=await call("PUT","/things/1",{name:"e"});
out.putRetried=!!x.ok&&same(keys(2));
n=sent.length;plan["/things/1"]=[503];x=await call("DELETE","/things/1");
out.deleteNotRetried=!!x.err&&sent.length===n+1&&keys(1)[0]==="";
pc.toast("Saved");out.plainToastNoButton=!d.querySelector(".pc-toast .pc-retry");
out.errors=errs;
b.report(out,["errors"]);
try{fs.unlinkSync(TMP)}catch(e){}
process.exit(0);
})();
