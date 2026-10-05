// Общая форма единицы по типам спеки: список — через запятую (поле group_by — блоком групп), метки — с подсказкой из
// меток серверов, секрет — пустой со словом «задан»; свой редактор одного поля (addFieldEditor) внутри формы, а
// отправка остаётся за формой; своя общая карточка (addTab "general") с console.unitForm внутри.
const fs=require("fs"),path=require("path");
const SRC=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"pc-form-"+process.pid+".html");
fs.writeFileSync(TMP,`<!doctype html><div id="app"></div><script>${SRC}</script><script>window.pc=PlatformConsole.mount(document.getElementById("app"),{lang:"en"});</script>`);
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
b.FIX["/session"]={open:true};
b.FIX["/spec"]={name:"testsub",rows:"things",id:"numeric",fields:[{name:"name",type:"string"},{name:"addr",type:"url"},{name:"folders",type:"list"},{name:"labels",type:"list"},{name:"key_secret",type:"string",bound_to:["addr"]},{name:"origin",type:"string",fixed:true},{name:"mode",type:"string",enum:["a","b"],default:"a"},{name:"tone",type:"string"}],display:{options:{mode:{a:"Alpha"},tone:{x:"Ex"}}}};
b.FIX["/things"]={configured:[{id:1,name:"one",addr:"x://1/Brand/Model",folders:["A","B"],labels:["v:a"],key_secret:"***",origin:"o-1"}],rows:[]};
b.FIX["/servers"]={servers:{"s-1":{workers:[],resource:"live",labels:["v:a","v:b"]}},policy:{}};
b.FIX["/events"]={events:[],state:"live"};
(async()=>{
const w=b.boot();const errs=[];w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
await b.ready(600);await w.pc.ready;const d=w.document,pc=w.pc,out={};
const main=()=>d.querySelector("main");
pc.select("unit:testsub/1");await b.ready(80);
let f=main().querySelector(".pc-edit");
out.fixedReadOnly=f.elements.origin.disabled===true&&f.elements.origin.value==="o-1";
out.listAsItems=f.elements.folders.value==="A, B";
out.labelsSuggestServers=[...f.querySelectorAll("#pc-dl-labels option")].map(o=>o.value).join(",")==="v:a,v:b";
// набор значений — из enum спеки, слова — из display.options; без enum слова select не делают
const ms=f.elements.mode;out.enumSelect=!!ms&&ms.tagName==="SELECT"&&[...ms.options].map(o=>o.value+"="+o.textContent).join(",")==="a=Alpha,b=b"&&f.elements.tone.tagName==="INPUT";
out.secretSaysSet=/set — empty keeps it/.test(f.elements.key_secret.placeholder)&&f.elements.key_secret.value==="";
// убрать A, добавить C; уходит только folders
f.elements.folders.value="B, C";f.elements.folders.dispatchEvent(new w.Event("input",{bubbles:true}));
out.footerArmed=d.querySelector(".pc-save").disabled===false;
let n=w.__calls.length;f.dispatchEvent(new w.Event("submit",{cancelable:true}));await b.ready(100);
let c=w.__calls.slice(n).find(x=>x.method==="PUT");
out.listSent=!!c&&JSON.stringify(c.body)==='{"folders":["B","C"]}';
// свой редактор поля addr: показывает разбор, пишет значение через set; форма отправляет
pc.addFieldEditor("unit","addr",(host,ref,obj,value,set)=>{
  host.innerHTML=`<input class="my-addr" value="${value}"><span class="my-parsed">${value.split("/")[3]||""}</span>`;
  host.querySelector(".my-addr").oninput=e=>set(e.target.value);
});
pc.select("unit:testsub/1");await b.ready(80);
f=main().querySelector(".pc-edit");
out.editorInForm=!!f.querySelector(".pc-editor .my-addr")&&f.querySelector(".my-parsed").textContent==="Brand";
const ma=f.querySelector(".my-addr");ma.value="x://2/Other/M";ma.dispatchEvent(new w.Event("input"));
f.elements.key_secret.value="k2";
n=w.__calls.length;f.dispatchEvent(new w.Event("submit",{cancelable:true}));await b.ready(100);
c=w.__calls.slice(n).find(x=>x.method==="PUT");
out.editorValueSentByForm=!!c&&c.body.addr==="x://2/Other/M"&&c.body.key_secret==="k2";
// bound_to работает и через свой редактор
pc.select("unit:testsub/1");await b.ready(80);
f=main().querySelector(".pc-edit");const ma2=f.querySelector(".my-addr");ma2.value="x://3/A/B";ma2.dispatchEvent(new w.Event("input"));
n=w.__calls.length;f.dispatchEvent(new w.Event("submit",{cancelable:true}));await b.ready(60);
out.boundViaEditor=w.__calls.length===n&&/key_secret: is bound/.test(f.querySelector(".pc-err").textContent);
// своя общая карточка с unitForm внутри
pc.addTab("unit",{id:"general",label:"General",render:(host,ref)=>{host.innerHTML='<div class="my-head">my layout</div><div class="my-form"></div>';pc.unitForm(host.querySelector(".my-form"),ref)}});
pc.select("unit:testsub/1");await b.ready(80);
out.ownGeneralWithForm=!!main().querySelector(".my-head")&&!!main().querySelector(".my-form .pc-edit")&&main().querySelectorAll(".pc-edit").length===1;
out.noGeneralTabInBar=!main().querySelector('.pc-tabs [data-tab="general"]')||main().querySelectorAll('.pc-tabs [data-tab="general"]').length<=1;
out.errors=errs;
b.report(out,["errors"]);
try{fs.unlinkSync(TMP)}catch(e){}
process.exit(0);
})();
