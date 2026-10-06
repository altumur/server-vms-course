// Поле типа json в общей форме единицы: значение показано текстом с отступами; модуль сам разбирает текст до отправки —
// не JSON: под полем «не JSON», ничего не уходит; JSON — в теле значение (объект, список, число, строка-документ в
// кавычках остаётся строкой). Дверь строковый вход как JSON не разбирает («Архитектор»).
const fs=require("fs"),path=require("path");
const PAGE=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.html"),"utf8");
const MOD=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"pc-fjson-"+process.pid+".html");
fs.writeFileSync(TMP,PAGE.replace(/<script src="\/platform\/console\.js\?v=1"><\/script>/,()=>`<script>${MOD}</script>`)
  .replace('PlatformConsole.mount(document.getElementById("app"))','PlatformConsole.mount(document.getElementById("app"), { lang: "ru", poll_s: 0 })'));
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
const P=`x"'><img src=x onerror=window.__pwned=1>`;
b.FIX["/session"]={open:true};
b.FIX["/spec"]={name:"testsub",rows:"things",id:"numeric",fields:[{name:"name",type:"string"},{name:"rules",type:"json"}]};
b.FIX["/things"]={configured:[{id:1,name:"a",rules:{when:[{kind:P}],n:1}}],rows:[]};
b.FIX["/things/1"]={ok:true};
(async()=>{
  const w=b.boot();const errs=[];w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
  await b.ready(400);await w.platformConsole.ready;const d=w.document,out={};
  w.platformConsole.select("unit:testsub/1");await b.ready(120);
  const f=()=>d.querySelector(".pc-edit"),t=()=>f().elements.rules,err=()=>f().querySelector('[data-ferr="rules"]');
  out.shownAsIndentedText=t().tagName==="TEXTAREA"&&t().value===JSON.stringify({when:[{kind:P}],n:1},null,2)&&!/object Object/.test(f().textContent);
  const send=async v=>{t().value=v;const n=w.__calls.length;f().dispatchEvent(new w.Event("submit",{cancelable:true}));await b.ready(80);return w.__calls.slice(n).find(x=>x.method==="PUT")};
  const c0=await send("{bad");
  out.notJsonNothingSent=!c0&&!err().hidden&&/не JSON/.test(err().textContent)&&t().value==="{bad"&&/не JSON/.test(f().querySelector(".pc-err").textContent);
  const c1=await send('{"b": [2]}');
  out.objectSentAsValue=!!c1&&JSON.stringify(c1.body)==='{"rules":{"b":[2]}}'&&err().hidden;
  const c2=await send('"a string document"');
  out.quotedStringStaysAString=!!c2&&c2.body.rules==="a string document";
  const c3=await send("[1, 2]");
  out.listSentAsList=!!c3&&JSON.stringify(c3.body.rules)==="[1,2]";
  out.neverRan=w.__pwned===undefined;
  out.errors=errs;out.noErrors=!errs.length;
  b.report(out);
  try{fs.unlinkSync(TMP)}catch(e){}
  process.exit(0);
})();
