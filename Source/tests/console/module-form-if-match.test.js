// Форма единицы и версия — P/07 Н1.5 `forms` (ADR-0094 B4; ADR-0091 доп. (28) п. 3): PUT и DELETE формы всегда несут If-Match —
// revision показанной строки; отказ 412 — экран: слова в `.pc-err`, разошедшиеся значения в `.pc-moved`, ввод человека цел,
// кнопка `.pc-reread` перечитывает строки и рисует форму заново. Прочие отказы — как прежде.
const fs=require("fs"),path=require("path");
const SRC=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"pc-ifmatch-"+process.pid+".html");
fs.writeFileSync(TMP,`<!doctype html><div id="app"></div><script>${SRC}</script><script>window.pc=PlatformConsole.mount(document.getElementById("app"),{lang:"en"});</script>`);
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
b.FIX["/session"]={open:true};
b.FIX["/manifest"]={name:"testsub",rows:"things",id:"name",fields:[{name:"name",type:"string"},{name:"start",type:"int"},{name:"note",type:"string"}]};
b.FIX["/things"]={configured:[{id:"c1",name:"c1",start:1,note:"a",revision:4}],rows:[]};
b.FIX["/servers"]={servers:{},policy:{}};
b.FIX["/events"]={events:[],state:"live"};
(async()=>{
const w=b.boot();const errs=[];w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
await b.ready(600);await w.pc.ready;const d=w.document,pc=w.pc,out={};
const main=()=>d.querySelector("main");
let answer=null;const sent=[];const base=w.fetch;
const res=(status,body)=>({ok:status<400,status,headers:{get:k=>k==="Content-Type"?"application/json":null},json:()=>Promise.resolve(body),clone(){return this;}});
w.fetch=(url,init)=>{
  if(init&&init.method&&init.method!=="GET"&&answer){sent.push({method:init.method,url:String(url),ifMatch:(init.headers||{})["If-Match"]});return Promise.resolve(res(answer.status,answer.body));}
  return base(url,init);
};
const open=async()=>{pc.select("unit:testsub/c1");await b.ready(80);return main().querySelector(".pc-edit");};
const type=(f,n,v)=>{f.elements[n].value=v;f.elements[n].dispatchEvent(new w.Event("input",{bubbles:true}));};
w.confirm=()=>true;

// 1. PUT формы несёт revision показанной строки
answer={status:200,body:{id:"c1",name:"c1",start:2,revision:5,index:"9"}};
let f=await open();type(f,"start","2");
f.dispatchEvent(new w.Event("submit",{cancelable:true}));await b.ready(100);
out.putCarriesRevision=sent.length===1&&sent[0].method==="PUT"&&sent[0].ifMatch==="4";

// 2. 412: экран, ввод цел, значения строки сейчас
sent.length=0;
answer={status:412,body:{detail:"moved",error:"revision moved",field:"/revision",revision:6,row:{id:"c1",name:"c1",start:7,note:"a",revision:6,index:"12"}}};
f=await open();type(f,"start","3");
f.dispatchEvent(new w.Event("submit",{cancelable:true}));await b.ready(100);
const moved=f.querySelector(".pc-moved");
out.movedScreen=!!moved&&/changed/.test(f.querySelector(".pc-err").textContent);
out.movedShowsCurrent=!!moved&&/start: 7/.test(moved.textContent)&&!/note/.test(moved.textContent);
out.inputKept=f.elements.start.value==="3";
out.noFieldMark=!f.querySelector("[aria-invalid=true]");

// 3. «Перечитать»: новая строка, форма нарисована заново
b.FIX["/things"]={configured:[{id:"c1",name:"c1",start:7,note:"a",revision:6}],rows:[]};
moved.querySelector(".pc-reread").click();await b.ready(150);
const g=main().querySelector(".pc-edit");
out.rereadRedraws=!!g&&String(g.elements.start.value)==="7"&&!g.querySelector(".pc-moved");

// 4. Следующая отправка несёт новую revision
sent.length=0;
answer={status:200,body:{id:"c1",name:"c1",start:8,revision:7,index:"13"}};
type(g,"start","8");g.dispatchEvent(new w.Event("submit",{cancelable:true}));await b.ready(100);
out.nextPutCarriesNewRevision=sent.length===1&&sent[0].ifMatch==="6";

// 5. Прочий отказ — прежний текст, экрана нет
sent.length=0;
answer={status:400,body:{detail:"the door is shut",error:"refused"}};
f=await open();type(f,"start","4");
f.dispatchEvent(new w.Event("submit",{cancelable:true}));await b.ready(100);
out.otherRefusalPlain=/the door is shut/.test(f.querySelector(".pc-err").textContent)&&!f.querySelector(".pc-moved");

// 6. DELETE формы несёт revision, 412 — тот же экран
sent.length=0;
answer={status:412,body:{detail:"moved",error:"revision moved",field:"/revision",revision:6}};
f=await open();
const del=main().querySelector(".pc-del");
if(del){del.click();await b.ready(100);}
out.deleteCarriesRevision=!!del&&sent.length===1&&sent[0].method==="DELETE"&&sent[0].ifMatch==="6";
out.deleteMovedScreen=!!del&&!!f.querySelector(".pc-moved");

out.errors=errs;
b.report(out,["errors"]);
try{fs.unlinkSync(TMP)}catch(e){}
process.exit(0);
})().catch(e=>{console.log("FAILED: "+(e&&e.stack||e));process.exit(1);});
