// Лента в модуле — P/07 Н1.4 `changes` (ADR-0094 B2): номер берётся раньше первого чтения строк, дальше запрос с `after` и
// `wait`, не чаще раза в секунду; сообщение о строке своей подсистемы и сброс читают данные сразу, чужая подсистема и пустой
// ответ — нет; 404 снимает ленту, опрос живёт; страница держателя ленту не зовёт.
const fs=require("fs"),path=require("path");
const SRC=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"pc-changes-"+process.pid+".html");
const page=opts=>fs.writeFileSync(TMP,`<!doctype html><div id="app"></div><script>${SRC}</script><script>window.pc=PlatformConsole.mount(document.getElementById("app"),${opts});</script>`);
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
function cluster(){
  for(const k of Object.keys(b.FIX))delete b.FIX[k];
  b.FIX["/session"]={open:true};
  b.FIX["/manifest"]={name:"testsub",rows:"things",id:"numeric",fields:[{name:"name",type:"string"}]};
  b.FIX["/things"]={configured:[{id:1,name:"gate"}],rows:[]};
  b.FIX["/servers"]={servers:{},policy:{}};
  b.FIX["/events"]={events:[],state:"live"};
}
const urls=w=>w.__log.map(x=>x.url);
const reads=w=>urls(w).filter(u=>u==="/things").length;
const feeds=w=>urls(w).filter(u=>u.startsWith("/changes"));
(async()=>{
const out={};
// --- лента есть; опрос далеко, так что всякое чтение строк здесь — от ленты
cluster();b.FIX["/changes"]={position:"p1",changes:[]};page(`{lang:"en",poll_s:60}`);
let w=b.boot();const errs=[];w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
await w.pc.ready;await b.ready(100);
const u=urls(w);
out.numberBeforeRows=u.indexOf("/changes")>=0&&u.indexOf("/changes")<u.indexOf("/things");
out.firstHasNoAfter=feeds(w)[0]==="/changes";
await b.ready(1300);
out.afterAndWait=feeds(w).includes("/changes?after=p1&wait=15");
const quick=feeds(w).length;
out.atMostOneASecond=quick<=3;
// пустой ответ строк не читает
let r0=reads(w);await b.ready(1200);
out.emptyReadsNothing=reads(w)===r0;
// сообщение о своей подсистеме — чтение сразу, следующий запрос — с новым номером
b.FIX["/changes"]={position:"p2",changes:[{n:"p2",key:"testsub/things/1",revision:2,at:1}]};
await b.ready(1300);
b.FIX["/changes"]={position:"p2",changes:[]};
out.messageReads=reads(w)>r0;
await b.ready(1300);
out.nextAfterPosition=feeds(w).includes("/changes?after=p2&wait=15");
// чужая подсистема — чтения нет
r0=reads(w);
b.FIX["/changes"]={position:"p3",changes:[{n:"p3",key:"other/things/1",revision:2,at:1}]};
await b.ready(1300);
b.FIX["/changes"]={position:"p3",changes:[]};
await b.ready(100);
out.foreignSubsystemReadsNothing=reads(w)===r0;
// сброс — чтение, продолжаем с его номера
b.FIX["/changes"]={position:"p4",changes:[],reset:true};
await b.ready(1300);
b.FIX["/changes"]={position:"p4",changes:[]};
out.resetReads=reads(w)>r0;
await b.ready(1300);
out.afterReset=feeds(w).includes("/changes?after=p4&wait=15");
out.noProblem=errs.length===0;
// --- ленты нет: один запрос, опрос идёт
cluster();page(`{lang:"en",poll_s:0.3}`);
w=b.boot();
await w.pc.ready;await b.ready(1500);
out.noFeedOneRequest=feeds(w).length===1;
out.noFeedPollLives=reads(w)>=3;
// --- страница держателя: ленты нет у консоли домена
cluster();b.FIX["/changes"]={position:"p1",changes:[]};b.FIX["/manifest"]={};b.FIX["/mounts"]={root:"",mounts:{}};
b.FIX["/domain"]={holder:"hold",members:[],units:{}};b.FIX["/domain/alarms"]={events:[]};
page(`{lang:"en",sections:["domain"],poll_s:60}`);
w=b.boot();
await b.ready(1200);
out.holderNoFeed=feeds(w).length===0;
out.errors=errs;
b.report(out,["errors"]);
try{fs.unlinkSync(TMP)}catch(e){}
process.exit(0);
})();
