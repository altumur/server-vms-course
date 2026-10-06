// Контракт платформенного модуля (server-vms-course/КОНСОЛЬ-МОДУЛЬ-ПЛАТФОРМЫ.md, v1) на фиктивной подсистеме:
// минимальная оболочка (модуль и mount), словарь, закрытый список маршрутов, выбор, display и about из спеки,
// may по грантам, правка без маски, вызовы оболочки в библиотеку.
const fs=require("fs"),path=require("path");
const SRC=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"pc-module-"+process.pid+".html");
const OPTS=process.env.PC_OPTS||`{lang:"en"}`;
fs.writeFileSync(TMP,`<!doctype html><div id="app"></div><script>${SRC}</script><script>window.pc=PlatformConsole.mount(document.getElementById("app"),${OPTS});</script>`);
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
const P=`x"'><img src=x onerror=window.__pwned=1>`;
b.FIX["/session"]={open:true};
b.FIX["/spec"]={name:"testsub",rows:"things",id:"numeric",fields:[{name:"name",type:"string"},{name:"enabled",type:"bool"},{name:"labels",type:"list"},{name:"key_secret",type:"string"}],metrics:{prefix:"testsub",running:"things_running"},display:{unit:"thing",units:"things",field_help:{name:"what to call it"},kinds:{"x.y":"x went y"}}};
b.FIX["/mounts"]={root:"testsub",mounts:{sub:{name:"subthings",rows:"parts",id:"name",about:{sub:"testsub",field:"thing"},fields:[{name:"thing",type:"string"},{name:"size",type:"int"}]}}};
b.FIX["/things"]={configured:[{id:1,name:"one",labels:["a"],key_secret:"***",enabled:true},{id:2,name:P,labels:[],key_secret:"",enabled:true}],rows:[{id:1,worker:"w-1",server:"s-1",phase:"running"}]};
b.FIX["/sub/parts"]={configured:[{id:"p1",thing:"1",size:3}],rows:[]};
b.FIX["/servers"]={servers:{"s-1":{resource:"live",workers:[{worker:"w-1",load:1,capacity:5,state:"live"}],placeable:true}},policy:{}};
b.FIX["/where/1"]={worker:"w-1",server:"s-1",reason:"most free",door:"http://s-1:9/"};
b.FIX["/events"]={events:[{t:1,kind:"x.y",subsystem:"testsub",unit:"1",note:P}],state:"live"};
(async()=>{
const w=b.boot();const errs=[];w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
w.confirm=()=>true;
// закрытый список маршрутов (§2): каждый запрос модуля сверяется
const seen=[];const f0=w.fetch;w.fetch=(u,i)=>{seen.push(String(u).split("?")[0].replace(/^https?:\/\/[^/]+/,""));return f0(u,i)};
await b.ready(700);const d=w.document,ev=w.eval.bind(w),out={};
const pc=w.pc;await pc.ready;
// словарь по исходнику модуля, с долгом из platform-words.debt
let src=SRC;for(const l of fs.readFileSync(path.join(__dirname,"platform-words.debt"),"utf8").split("\n"))if(l&&!l.startsWith("#"))src=src.split(l.split("\t")[0]).join("");
// «live» как состояние (живой пульс, live/silent, *_live) — платформенное слово; запрещено только как имя
// подсистемы живого видео: live_url, LIVE_NAME, /live/, livecontroller и подобные — правило по токену (§2 контракта).
const words=/\b(vms|cams?|cameras?|rec|det|auto|recordings?|recorders?|detectors?|footage|video|rtsp|whep|timeline|volumes?|archives?|device|segments?)\b|\blive_\w|\bLIVE_\w|\/live\/|\blive(controller|worker|gateway|gw)\b|камер|архив|видео|запис/i;
const hit=src.split("\n").map((l,i)=>[i+1,l]).filter(([,l])=>words.test(l.replace(/^\s*\/\/.*$/,"")));
out.vocabularyClean=hit.length===0;
out.liveRuleIsByToken=["live_url","LIVE_NAME","/live/","livecontroller"].every(x=>words.test(x))&&!["state === \"live\"","workers_live","live/silent"].some(x=>words.test(x));out.hits=hit.slice(0,3).map(([n,l])=>n+": "+l.trim().slice(0,80)).join(" | ");
// spec(name): копия спеки для кода страницы — правка копии модуль не трогает; неизвестная подсистема — null
{const sp=pc.spec("testsub");out.specCopy=!!sp&&sp.rows==="things"&&(sp.rows="x",pc.spec("testsub").rows==="things")&&pc.spec("nope")===null;}
out.version=pc.version===1&&w.PlatformConsole.version===1;
const tree=()=>d.querySelector(".pc-tree").textContent;
out.displayWords=d.querySelector(".pc-hunits-l").textContent==="Things";
// about из спеки: части вложены под единицей 1
ev(`document.querySelector('[data-tw="unit:testsub/1"]').click()`);
out.aboutNested=!!d.querySelector('[data-ref="unit:subthings/p1"]')&&![...d.querySelectorAll(".pc-tree .pc-g")].some(x=>/parts/.test(x.textContent));
// выбор и событие select
let got=null;pc.on("select",(ref,obj)=>{got=[ref,obj&&obj.name]});
pc.select("unit:testsub/1");await b.ready(150);
out.selectEvent=got&&got[0]==="unit:testsub/1"&&got[1]==="one"&&pc.selected()==="unit:testsub/1";
const main=()=>d.querySelector("main");
out.fieldHelp=!!main().querySelector('[title="what to call it"]');
out.whyShown=/most free/.test(main().textContent);
main().querySelector('.pc-tabs [data-tab="events"]').click();await b.ready(150);
out.kindWord=/x went y/.test(main().textContent);
main().querySelector('.pc-tabs [data-tab="general"]').click();await b.ready(80);
const form=main().querySelector(".pc-edit");
out.secretEmpty=form.elements.key_secret.type==="password"&&form.elements.key_secret.value===""&&/set/.test(form.elements.key_secret.placeholder);
form.elements.name.value="uno";let n=w.__calls.length;form.dispatchEvent(new w.Event("submit",{cancelable:true}));await b.ready(120);
let c=w.__calls.slice(n).find(x=>x.method==="PUT");
out.onlyChanged=!!c&&c.path==="/things/1"&&c.body.name==="uno"&&!("key_secret" in c.body)&&!("labels" in c.body)&&!!c.key;
// where() отдаёт door, модуль туда не ходит
const wh=await pc.where("unit:testsub/1");
out.whereGivesDoor=wh&&wh.door==="http://s-1:9/";
// вызовы оболочки
pc.addTab("unit",{id:"t",label:"Extra",render:(host,ref)=>{host.textContent="tab for "+ref}});
pc.addMenu("unit",ref=>[{label:"Do it",run:()=>{w.__ran=ref}}]);
pc.select("unit:testsub/1");await b.ready(120);
out.tabBar=[...main().querySelectorAll(".pc-tabs button")].map(x=>x.textContent).join("|")==="General|Extra|Events"&&main().querySelector(".pc-general").hidden===false;
main().querySelector('.pc-tabs [data-tab="t"]').click();await b.ready(80);
out.tabRendered=/tab for unit:testsub\/1/.test(main().textContent)&&main().querySelector(".pc-general").hidden===true;
main().querySelector('.pc-tabs [data-tab="general"]').click();await b.ready(80);
d.querySelector('[data-ref="unit:testsub/1"]').dispatchEvent(new w.MouseEvent("contextmenu",{bubbles:true,clientX:5,clientY:5}));
const mb=[...d.querySelectorAll(".pc-menu button")].find(x=>x.textContent==="Do it");if(mb)mb.click();
out.menuRuns=w.__ran==="unit:testsub/1";
// addDecor: иконка классом, значок текстом (экранирован), и в узле, и в заголовке карточки
pc.addDecor("unit",ref=>ref==="unit:testsub/1"?{icon:"star\"><b>x",badge:P,title:"T"}:{});
const node=d.querySelector('[data-ref="unit:testsub/1"]');
out.decorIcon=!!node.querySelector(".ici.ici-starbx")&&node.querySelector(".pc-badge").textContent===P;
pc.select("unit:testsub/1");await b.ready(80);
out.decorInTitle=!!main().querySelector(".pc-hd .ici-starbx");
// серверы и единицы воркера
(d.querySelector('.pc-rail [data-s="units"]').click(),d.querySelector('.pc-layout').click(),d.querySelector('[data-layout="servers"]').click());
pc.select("worker:w-1");await b.ready(50);
out.workerUnits=/one/.test(main().textContent)&&/thing/.test(main().textContent);
// вредная строка — текстом
out.neverRan=w.__pwned===undefined&&!d.querySelector("img");
// маршруты
const allowed=/^\/(spec|mounts|session|servers(\/.*)?|policy|drain|schema|unplaceable|where\/.*|events|marks|metrics|things(\/.*)?|sub\/(spec|parts(\/.*)?|unplaceable|where\/.*)|domain(\/.*)?|api\/held)$/;   // /api/held: the one process door it reads (§10a)
const foreign=[...new Set(seen)].filter(p=>!allowed.test(p));
out.onlyListedRoutes=foreign.length===0;out.foreign=foreign.join(",");
out.errors=errs;
b.report(out,["errors","hits","foreign"]);
try{fs.unlinkSync(TMP)}catch(e){}
process.exit(0);
})();
