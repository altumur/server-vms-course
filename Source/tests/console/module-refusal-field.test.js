// Отказ у поля — P/07 Н1.5 `forms` (ADR-0094 B5): форма единицы и форма создания ставят текст отказа 400, 409, 412 у поля,
// которое называет `field` тела (JSON Pointer, P/06.1 Н2 «Отказ: `error` и `field`»); поля нет в форме или `field` нет —
// текст в общем `.pc-err`, как прежде.
const fs=require("fs"),path=require("path");
const SRC=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"pc-field-"+process.pid+".html");
fs.writeFileSync(TMP,`<!doctype html><div id="app"></div><script>${SRC}</script><script>window.pc=PlatformConsole.mount(document.getElementById("app"),{lang:"en"});</script>`);
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
b.FIX["/session"]={open:true};
b.FIX["/manifest"]={name:"testsub",rows:"things",id:"name",fields:[{name:"name",type:"string"},{name:"start",type:"int"},{name:"a/b",type:"string"}]};
b.FIX["/things"]={configured:[{id:"c1",name:"c1",start:1,"a/b":"x",revision:1}],rows:[]};
b.FIX["/servers"]={servers:{},policy:{}};
b.FIX["/events"]={events:[],state:"live"};
(async()=>{
const w=b.boot();const errs=[];w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
await b.ready(600);await w.pc.ready;const d=w.document,pc=w.pc,out={};
const main=()=>d.querySelector("main");
let answer=null;const base=w.fetch;
const res=(status,body)=>({ok:false,status,headers:{get:k=>k==="Content-Type"?"application/json":null},json:()=>Promise.resolve(body),clone(){return this;}});
w.fetch=(url,init)=>init&&init.method&&init.method!=="GET"&&answer?Promise.resolve(res(answer.status,answer.body)):base(url,init);
const submit=async(body,status=400)=>{
  answer={status,body};pc.select("unit:testsub/c1");await b.ready(80);
  const f=main().querySelector(".pc-edit");f.elements.start.value="2";f.elements.start.dispatchEvent(new w.Event("input",{bubbles:true}));
  f.dispatchEvent(new w.Event("submit",{cancelable:true}));await b.ready(100);return f;
};
const atField=(f,n)=>{const c=f.elements[n];if(!c||c.getAttribute("aria-invalid")!=="true")return "";const e=c.closest("div")&&c.closest("div").querySelector(".pc-field-err");return e?e.textContent:"";};
let f=await submit({detail:"start is not a number",error:"not_number",fault:"not_number",field:"/start"});
out.pending_fieldAtControl=atField(f,"start")==="start is not a number";
out.pending_firstFieldFocused=d.activeElement===f.elements.start;
f=await submit({detail:"a/b is fixed",error:"fixed",field:"/a~1b"});
out.pending_pointerDecoded=atField(f,"a/b")==="a/b is fixed";
f=await submit({detail:"row moved",error:"revision moved",field:"/revision",revision:2},412);
out.noControlGoesToCommon=/row moved/.test(f.querySelector(".pc-err").textContent);
f=await submit({detail:"the door is shut",error:"refused"});
out.noFieldGoesToCommon=/the door is shut/.test(f.querySelector(".pc-err").textContent)&&!f.querySelector("[aria-invalid=true]");
out.errors=errs;
// pending_* — отказ у поля по `field` (P/07 Н1.5 `forms`): опубликованный модуль его ещё не ставит, «Решает реализация» п. 4;
// правка байтов модуля — после поручения (модуль байт в байт в пине, сц. 01 приёмки главы 6.5); после правки — снять приставку
// pending_ и убрать имена из списка ниже.
b.report(out,["errors","pending_fieldAtControl","pending_firstFieldFocused","pending_pointerDecoded"]);
try{fs.unlinkSync(TMP)}catch(e){}
process.exit(0);
})().catch(e=>{console.log("FAILED: "+(e&&e.stack||e));process.exit(1);});
