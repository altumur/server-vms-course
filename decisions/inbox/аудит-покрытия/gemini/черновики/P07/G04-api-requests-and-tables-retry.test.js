// Черновик G04 (P/07 Н1.5 api): POST с памятью повторов владельца для просьб (POST /<sub>/requests, P/06.4)
// против записи в таблицы подсистемы без памяти повторов (POST/DELETE /<sub>/<table>[/<key>], сначала чтение).
const fs=require("fs"),path=require("path");
const SRC=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"pc-retry-req-tbl-"+process.pid+".html");
fs.writeFileSync(TMP,`<!doctype html><div id="app"></div><script>${SRC}</script><script>window.pc=PlatformConsole.mount(document.getElementById("app"),{lang:"en"});window.pc.retryWaits=[20,20,20];</script>`);
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
b.FIX["/session"]={open:true};
b.FIX["/manifest"]={name:"testsub",rows:"things",id:"numeric",fields:[{name:"name",type:"string"}],
  requests:{actions:["recount"]},tables:[{name:"places",key:"name",fields:[{name:"name",type:"string"}]}]};
b.FIX["/things"]={configured:[],rows:[]};
b.FIX["/servers"]={servers:{},policy:{}};

(async()=>{
  const w=b.boot(),errs=[];w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
  await w.pc.ready;const pc=w.pc,out={},plan={},sent=[];
  const base=w.fetch;
  const res=(status,body)=>({ok:status>=200&&status<300,status,headers:{get:()=>"application/json"},
    json:()=>Promise.resolve(body),text:()=>Promise.resolve(JSON.stringify(body))});
  w.fetch=(url,init)=>{
    const m=init&&init.method||"GET";if(m==="GET")return base(url,init);
    sent.push({m,path:url,key:(init.headers||{})["Idempotency-Key"]||"",body:init.body});
    const s=(plan[url]||[]).shift();
    if(s==="net")return Promise.reject(new TypeError("Failed to fetch"));
    if(s===503)return Promise.resolve(res(503,{error:"busy"}));
    return Promise.resolve(res(202,{rid:"r-1"}));
  };
  const call=async(m,p,body)=>{try{return{ok:await pc.api(m,p,body)}}catch(e){return{err:e.message,status:e.status,retry:e.retry}}};
  // 1. Таблицы без памяти повторов: POST /testsub/places и DELETE /testsub/places/p1 не повторяются автоматически при обрыве сети
  let n=sent.length;plan["/testsub/places"]=["net"];
  let rTbl=await call("POST","/testsub/places",{name:"p1"});
  out.tablePostNotAutoRetried=!!rTbl.err&&sent.length===n+1;
  n=sent.length;plan["/testsub/places/p1"]=["net"];
  let rTblDel=await call("DELETE","/testsub/places/p1");
  out.tableDeleteNotAutoRetried=!!rTblDel.err&&sent.length===n+1;
  // 2. Просьба POST /testsub/requests (Н1.5 api: «POST с памятью повторов владельца (единица — P/06.1, просьба — P/06.4)»)
  n=sent.length;plan["/testsub/requests"]=[503,"net"];
  let rReq=await call("POST","/testsub/requests",{unit:"1",action:"recount"});
  out.requestsPostRetriedWithSameKey=!!rReq.ok&&sent.length===n+3&&sent.slice(n).every(x=>x.key!==""&&x.key===sent[n].key);
  w.close();
  out.errors=errs;
  b.report(out,["errors"]);
  try{fs.unlinkSync(TMP)}catch(e){}
  process.exit(0);
})();
