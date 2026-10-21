// Общий документ домена по schema — P/07 Н1.6 schema («Решает реализация» п. 2): у документа {name, type: json} со
// схемой страница строит форму — объект по properties, список с «добавить» и «убрать», строка, целое, да/нет, enum;
// чего форма сказать не может (объект без properties), — текст JSON на своём месте. Публикация — PUT /domain/shared
// {base_rev, shared}; пустые поля не уходят; не то, что говорит схема (не JSON, не число), — ничего не отправлено.
const fs=require("fs"),path=require("path");
const SRC=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"pc-shared-schema-"+process.pid+".html");
fs.writeFileSync(TMP,`<!doctype html><div id="app"></div><script>${SRC}</script><script>window.pc=PlatformConsole.mount(document.getElementById("app"),{lang:"en",sections:["domain"]});</script>`);
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
const P=`x"'><img src=x onerror=window.__pwned=1>`;
const RULES={type:"array",maxItems:1000,items:{type:"object",required:["name","when","then"],additionalProperties:false,
  properties:{name:{type:"string",minLength:1},enabled:{type:"boolean"},when:{type:"object"},then:{type:"object"}}}};
const TUNE={type:"object",additionalProperties:false,properties:{depth:{type:"integer"},mode:{enum:["a","b"]},arg:{type:["integer","string"]}}};
b.FIX["/session"]={open:true};b.FIX["/spec"]={name:"",rows:null};
b.FIX["/mounts"]={root:"",mounts:{testsub2:{name:"testsub2",rows:"tallies",id:"name",fields:[{name:"name",type:"string"}],domain:{shared:["rules","tune"]}}}};
b.FIX["/domain"]={holder:"hold",members:[{name:"hold",holder:true,state:"ok"}],units:{}};b.FIX["/domain/alarms"]={events:[]};
b.FIX["/domain/shared"]={doc:{rev:4,term:1,at:1,shared:{testsub2:{rules:[{name:P,enabled:true,when:{x:1},then:{y:2}}],tune:{depth:3,mode:"b"}}}},delivery:{},
  declared:{testsub2:[{name:"rules",type:"json",schema:RULES},{name:"tune",type:"json",schema:TUNE}]}};
(async()=>{
const w=b.boot();const errs=[];w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
// PUT /domain/shared публикует документ: следующее чтение отдаёт его (rev + 1)
const f0=w.fetch;w.fetch=(u,i)=>{if(i&&i.method==="PUT"&&u==="/domain/shared"){const s=b.FIX["/domain/shared"],bd=JSON.parse(i.body),sh={};
  for(const [sub,fs] of Object.entries(bd.shared))sh[sub]=Object.fromEntries(Object.entries(fs).filter(([,v])=>v!==null));
  s.doc={...s.doc,rev:s.doc.rev+1,shared:sh};b.FIX["/domain/shared"]=s;}return f0(u,i)};
await w.pc.ready;await b.ready(200);const d=w.document,out={};
const box=()=>d.querySelector(".pc-shared"),doc=n=>box().querySelector(`[data-sh="testsub2/${n}"]`);
const items=()=>[...doc("rules").querySelectorAll(":scope > .pc-sf > .pc-sf-i")];
const prop=(el,n)=>el.querySelector(`.pc-sf-p[data-n="${n}"] > .pc-sf`);
out.formNotText=!!doc("rules")&&doc("rules").dataset.shf==="1"&&items().length===1;
const it0=items()[0].querySelector(".pc-sf");
out.stringField=prop(it0,"name").tagName==="INPUT"&&prop(it0,"name").value===P&&!d.querySelector(".pc-shared img");
out.boolField=prop(it0,"enabled").tagName==="SELECT"&&prop(it0,"enabled").value==="true";
out.freeObjectIsJson=prop(it0,"when").tagName==="TEXTAREA"&&JSON.parse(prop(it0,"when").value).x===1;
out.requiredMarked=/name \*/.test(it0.textContent)&&!/enabled \*/.test(it0.textContent);
out.intAndEnum=prop(doc("tune").firstElementChild,"depth").type==="number"&&prop(doc("tune").firstElementChild,"depth").value==="3"&&prop(doc("tune").firstElementChild,"mode").value==='"b"';
out.unionIsJson=prop(doc("tune").firstElementChild,"arg").tagName==="TEXTAREA";
// добавить элемент списка, заполнить, опубликовать
doc("rules").querySelector('[data-sf="add"]').click();
const it1=items()[1].querySelector(".pc-sf");
out.addedItemByItemsSchema=items().length===2&&!!prop(it1,"name")&&!!prop(it1,"then");
prop(it1,"name").value="r2";prop(it1,"when").value="{}";prop(it1,"then").value='{"act":"go"}';
prop(doc("tune").firstElementChild,"depth").value="";prop(doc("tune").firstElementChild,"arg").value="7";
let n=w.__calls.length;box().querySelector('[data-a="publish"]').click();await b.ready(100);
let c=w.__calls.slice(n).find(x=>x.method==="PUT");
out.publishByForm=!!c&&c.path==="/domain/shared"&&c.body.base_rev===4&&JSON.stringify(c.body.shared.testsub2.rules)===JSON.stringify([{name:P,enabled:true,when:{x:1},then:{y:2}},{name:"r2",when:{},then:{act:"go"}}])
  &&JSON.stringify(c.body.shared.testsub2.tune)===JSON.stringify({mode:"b",arg:7});
// убрать элемент; не JSON и не целое — ничего не отправлено, введённое остаётся
doc("rules").querySelector(".pc-sf-i [data-sf='del']").click();
out.removed=items().length===1&&prop(items()[0].querySelector(".pc-sf"),"name").value==="r2";
prop(items()[0].querySelector(".pc-sf"),"when").value="{nope";
n=w.__calls.length;box().querySelector('[data-a="publish"]').click();await b.ready(80);
out.badJsonNothingSent=w.__calls.length===n&&/rules\/0\/when/.test(box().textContent)&&prop(items()[0].querySelector(".pc-sf"),"when").value==="{nope";
prop(items()[0].querySelector(".pc-sf"),"when").value="{}";prop(doc("tune").firstElementChild,"depth").value="2.5";
n=w.__calls.length;box().querySelector('[data-a="publish"]').click();await b.ready(80);
out.notIntegerNothingSent=w.__calls.length===n&&/tune\/depth/.test(box().textContent);
// пустой список — значение домена снимается (null)
prop(doc("tune").firstElementChild,"depth").value="";
doc("rules").querySelector(".pc-sf-i [data-sf='del']").click();
n=w.__calls.length;box().querySelector('[data-a="publish"]').click();await b.ready(100);
c=w.__calls.slice(n).find(x=>x.method==="PUT");
out.emptyListIsNull=!!c&&c.body.shared.testsub2.rules===null;
out.neverRan=w.__pwned===undefined;
out.errors=errs;
b.report(out,["errors"]);
try{fs.unlinkSync(TMP)}catch(e){}
process.exit(0);
})();
