// Вызовы оболочки в библиотеку (P/07 Н1.5 adds), которых не звал ни один тест: addNote(kind, fn) — слова страницы о
// единице предупреждениями под «Размещением» (строка или список, текстом); addIcons({имя: svg}) — значки страницы по
// имени для addDecor и узлов addTreeNodes, icon(name) — их разметка, ненарисованное имя — точка; fullScreen() — тот же
// полный экран, что кнопка шапки; isFav(ref) / toggleFav(ref) — избранное синхронно со звездой узла, звездой карточки,
// панелью и хранилищем браузера. Поведение кликами — module-view, module-tree. Аудит покрытия P/07 (90661897f).
// Проход Gemini (G03; описание модуля §4, §9): addSection{id, label, icon, after, off, render} — раздел ленты за after
// (без after — над «Журналом»), off — виден выключенным с причиной в подсказке, render рисует раздел; addTab(kind, …)
// для видов server, worker, member, domain — вкладка карточки, render(host, ref, obj), select(ref, {tab}) её открывает;
// busy() вкладки — пока true, опрос карточку не перерисовывает; addBlock(kind, …) для member, domain — блок на общей
// вкладке, после блоков модуля, в порядке добавления; addAction(kind, (ref, obj) → [{label, run}]) — кнопки в шапке
// карточки перед звездой; dialog(title, fields, ok) — обещание значений полей (null — отмена), ok — надпись кнопки;
// confirm(q, more) — ответ человека, вопрос несёт q и more.
const fs=require("fs"),path=require("path");
const SRC=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"pc-adds-"+process.pid+".html");
fs.writeFileSync(TMP,`<!doctype html><div id="app"></div><script>${SRC}</script><script>window.pc=PlatformConsole.mount(document.getElementById("app"),{lang:"en"});</script>`);
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
const P=`x"'><img src=x onerror=window.__pwned=1>`;
b.FIX["/session"]={open:true};
b.FIX["/manifest"]={name:"testsub",rows:"things",id:"numeric",fields:[{name:"name",type:"string"}]};
b.FIX["/things"]={configured:[{id:1,name:"one"},{id:2,name:"two"},{id:3,name:"three"}],
  rows:[{id:1,worker:"w-1",server:"s-1",phase:"running"},{id:2,worker:"w-1",server:"s-1",phase:"running"},{id:3,worker:"w-1",server:"s-1",phase:"running"}]};
b.FIX["/servers"]={servers:{"s-1":{resource:"live",workers:[{worker:"w-1",load:3,capacity:5,state:"live"}]}},policy:{}};
b.FIX["/events"]={events:[],state:"live"};
(async()=>{
const w=b.boot();const errs=[];w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
const pc=w.pc;
// вызовы оболочки — до первого опроса
pc.addIcons({gadget:'<circle class="gadget-mark" cx="8" cy="8" r="3"/>'});
pc.addDecor("unit",ref=>ref==="unit:testsub/1"?{icon:"gadget"}:ref==="unit:testsub/2"?{icon:"nobody-drew-it"}:{});
pc.addNote("unit",(ref,u)=>ref==="unit:testsub/1"?"opening takes long: "+u.name:ref==="unit:testsub/2"?["first warning",P]:null);
pc.addNote("unit",()=>{throw new Error("page bug")});
await pc.ready;await b.ready(150);const d=w.document,out={};
const tree=()=>d.querySelector(".pc-tree"),main=()=>d.querySelector("main");
const row=r=>tree().querySelector(`.n[data-ref="${r}"]`);
// --- addIcons: значок страницы по имени — в узле (addDecor), в icon(name); имени никто не нарисовал — точка
out.iconInTree=!!row("unit:testsub/1")&&!!row("unit:testsub/1").querySelector(".ici.ici-gadget svg circle.gadget-mark");
out.iconCall=/gadget-mark/.test(pc.icon("gadget"))&&/ici-gadget/.test(pc.icon("gadget"));
out.undrawnIsDot=!!row("unit:testsub/2")&&!!row("unit:testsub/2").querySelector(".ici-nobody-drew-it")&&row("unit:testsub/2").querySelector(".ici-nobody-drew-it").textContent==="•"&&!row("unit:testsub/2").querySelector(".ici-nobody-drew-it svg");
out.moduleIconStays=/<svg/.test(pc.icon("server"));
// --- addNote: предупреждения под «Размещением» карточки единицы (.pc-err — место отказа формы, не заметка)
pc.select("unit:testsub/1");await b.ready(80);
const notes=()=>[...main().querySelectorAll(".pc-general .nt.err:not(.pc-err)")].map(x=>x.textContent);
out.noteString=JSON.stringify(notes())==='["opening takes long: one"]';
{const nt=main().querySelector(".pc-general .nt.err"),box=nt&&nt.closest(".card");
 out.noteUnderPlacement=!!box&&!!box.querySelector(".pc-state")&&!!box.querySelector(".pc-why");}
pc.select("unit:testsub/2");await b.ready(80);
out.noteList=JSON.stringify(notes())===JSON.stringify(["first warning",P]);
pc.select("unit:testsub/3");await b.ready(80);
out.noNoteNothing=notes().length===0;
out.noteAsText=w.__pwned===undefined&&!d.querySelector("img");
// --- fullScreen(): вызов страницы — то же, что кнопка шапки; Esc выходит
const root=d.querySelector(".pc"),fb=()=>main().querySelector(".pc-fullbtn")||d.querySelector(".pc-hd .pc-fullbtn");
pc.select("unit:testsub/1");await b.ready(50);
pc.fullScreen();
out.fullScreenOn=root.classList.contains("pc-full")&&!!fb()&&fb().textContent==="⤡";
pc.fullScreen();
out.fullScreenOff=!root.classList.contains("pc-full")&&fb().textContent==="⤢";
pc.fullScreen();d.dispatchEvent(new w.KeyboardEvent("keydown",{key:"Escape"}));
out.fullScreenEsc=!root.classList.contains("pc-full");
fb().click();pc.fullScreen();
out.fullScreenSameAsButton=!root.classList.contains("pc-full");
// --- isFav / toggleFav: вызовы страницы синхронны со звёздами, панелью и хранилищем
const R="unit:testsub/1";
out.isFavInitially=pc.isFav(R)===false;
pc.toggleFav(R);
const star=()=>d.querySelector(".pc-hd .pc-star")||main().querySelector(".pc-star");
out.toggleFavOn=pc.isFav(R)===true&&row(R).querySelector(".n-fav").classList.contains("on")&&star().textContent==="★"
  &&/one/.test((d.querySelector(".pc-favs .fav-panel-list")||{textContent:""}).textContent)&&/unit:testsub\/1/.test(w.localStorage.getItem("pc.favs.v1")||"");
star().click();
out.cardStarSeenByIsFav=pc.isFav(R)===false&&!row(R).querySelector(".n-fav").classList.contains("on");
row(R).querySelector(".n-fav").click();
out.treeStarSeenByIsFav=pc.isFav(R)===true;
pc.toggleFav(R);
out.toggleFavOff=pc.isFav(R)===false&&star().textContent==="☆"&&!/unit:testsub\/1/.test(w.localStorage.getItem("pc.favs.v1")||"");
// избранное — любые ref, и оболочки тоже
pc.toggleFav("x:page-own");
out.favAnyRef=pc.isFav("x:page-own")===true;
pc.toggleFav("x:page-own");
w.close();
// --- addSection, addTab для server | worker | member | domain и busy, addBlock для member | domain, addAction, dialog, confirm
b.FIX["/things"]={configured:[{id:1,name:"one"}],rows:[{id:1,worker:"w-1",server:"s-1",phase:"running"}]};
b.FIX["/domain"]={holder:"h",members:[{name:"h",holder:true,state:"ok"},{name:"m-1",state:"ok"}]};
b.FIX["/domain/alarms"]={events:[]};
{
const w=b.boot();w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
const pc=w.pc,d=w.document,main=()=>d.querySelector("main"),got={},drawn={};
pc.addIcons({gadget:'<circle class="gadget-mark" cx="8" cy="8" r="3"/>'});
pc.addSection({id:"own-sec",label:"Own section",icon:"gadget",after:"units",render:host=>{host.innerHTML='<p class="own-body">own body</p>'}});
pc.addSection({id:"off-sec",label:"Off section",off:"not licensed here",render:host=>{host.innerHTML='<p class="off-body">off</p>'}});
for(const kind of ["server","worker","member","domain"])
  pc.addTab(kind,{id:"t-"+kind,label:"Tab "+kind,render:(host,ref,obj)=>{got[kind]=[ref,obj];host.innerHTML=`<p class="tk-${kind}">${kind}</p>`}});
let busy=false;drawn.busy=0;
pc.addTab("unit",{id:"busy-tab",label:"Busy",busy:()=>busy,render:host=>{drawn.busy++;host.innerHTML=`<p class="bt">drawn ${drawn.busy}</p>`}});
for(const kind of ["member","domain"])for(const id of ["b1","b2"])
  pc.addBlock(kind,{id:kind+"-"+id,render:(host,ref,obj)=>{got["block-"+kind+"-"+id]=[ref,obj];host.innerHTML=`<div class="bk-${kind}-${id}">${id}</div>`}});
let ran=null,actArgs=null;
pc.addAction("server",(ref,obj)=>{actArgs=[ref,obj];return [{label:"Page action",run:()=>{ran=ref}}]});
await pc.ready;await b.ready(150);
// addSection: за units, без after — над «Журналом»; off — виден выключенным с причиной; render рисует раздел
const rail=()=>[...d.querySelectorAll(".pc-rail button[data-s]")].map(x=>x.dataset.s);
const r=rail(),sb=s=>d.querySelector(`.pc-rail [data-s="${s}"]`);
out.sectionAfter=r.indexOf("own-sec")===r.indexOf("units")+1&&/Own section/i.test(sb("own-sec").textContent);
out.sectionWithoutAfterAboveJournal=r.indexOf("off-sec")>=0&&r.indexOf("off-sec")===r.indexOf("journal")-1;
out.sectionOffWithReason=sb("off-sec").classList.contains("is-off")&&/not licensed here/.test(sb("off-sec").title)&&!sb("own-sec").classList.contains("is-off");
out.sectionIcon=!!sb("own-sec").querySelector(".ici-gadget svg circle.gadget-mark");
sb("own-sec").click();await b.ready(60);
out.sectionRendered=!!main().querySelector(".own-body");
sb("units").click();await b.ready(60);
// addTab для server, worker, member, domain: select(ref, {tab}) открывает вкладку, render(host, ref, obj)
for(const [kind,ref] of [["server","server:s-1"],["worker","worker:testsub/w-1"],["member","member:m-1"],["domain","domain"]]){
  pc.select(ref,{tab:"t-"+kind});await b.ready(60);
  const on=d.querySelector(".pc-tabs button.on");
  out["tab_"+kind]=!!on&&on.dataset.tab==="t-"+kind&&!!main().querySelector(`.pc-tab[data-tab="t-${kind}"]:not([hidden]) .tk-${kind}`)&&!!got[kind]&&got[kind][0]===ref&&!!got[kind][1];
  pc.select(ref,{tab:"general"});await b.ready(60);
}
out.tabMemberObj=!!got.member&&got.member[1].name==="m-1";
// addBlock для member и domain: на общей вкладке, после блоков модуля, в порядке добавления
for(const [kind,ref] of [["member","member:m-1"],["domain","domain"]]){
  pc.select(ref,{tab:"general"});await b.ready(60);
  const g=main().querySelector(".pc-general"),blocks=g?[...g.querySelectorAll(":scope > .pc-block")]:[];
  out["block_"+kind]=blocks.map(x=>x.dataset.block).join(",")===kind+"-b1,"+kind+"-b2"&&!!blocks[0].querySelector(`.bk-${kind}-b1`)
    &&!blocks[1].nextElementSibling&&!!blocks[0].previousElementSibling&&!blocks[0].previousElementSibling.classList.contains("pc-block")&&got["block-"+kind+"-b1"][0]===ref&&!!got["block-"+kind+"-b1"][1];
}
// addAction: кнопка страницы в шапке карточки, перед звездой; run по нажатию
pc.select("server:s-1",{tab:"general"});await b.ready(60);
const ab=[...d.querySelectorAll(".pc-hd button")].find(x=>x.textContent==="Page action"),st=d.querySelector(".pc-hd .pc-star");
out.actionInHeadBeforeStar=!!ab&&!!st&&!!(ab.compareDocumentPosition(st)&w.Node.DOCUMENT_POSITION_FOLLOWING)&&!!actArgs&&actArgs[0]==="server:s-1"&&!!actArgs[1];
if(ab)ab.click();
out.actionRuns=ran==="server:s-1";
pc.select("unit:testsub/1");await b.ready(60);
out.actionOnlyItsKind=![...d.querySelectorAll(".pc-hd button")].some(x=>x.textContent==="Page action");
// busy(): пока вкладка занята, опрос карточку не перерисовывает; освободилась — перерисовывает
pc.select("unit:testsub/1",{tab:"busy-tab"});await b.ready(60);
const n0=drawn.busy,node0=main().querySelector(".bt");
busy=true;b.FIX["/things"]={configured:[{id:1,name:"one-changed"}],rows:[{id:1,worker:"w-1",server:"s-1",phase:"running"}]};
await pc.refresh();await b.ready(60);
out.busyTabNotRepainted=n0>0&&drawn.busy===n0&&main().querySelector(".bt")===node0;
busy=false;await pc.refresh();await b.ready(60);
out.freeTabRepainted=drawn.busy>n0;
// dialog(title, fields, ok): обещание значений полей по нажатию ok; отмена — null
let p=pc.dialog("Ask something",[{name:"q",label:"Question",value:"v1"},{name:"pick",label:"Pick",options:[["a","A"],["b","B"]]}],"Send");
await b.ready(30);
const dlg=d.querySelector(".pc-dialog"),df=d.querySelector(".pc-dialog-f");
out.dialogShown=!!dlg&&!dlg.hidden&&/Ask something/.test(df.textContent)&&df.querySelector(".pc-dialog-ok").textContent==="Send"&&df.elements.q.value==="v1";
df.elements.q.value="v2";df.elements.pick.value="b";df.querySelector(".pc-dialog-ok").click();
let v=await p;
out.dialogGivesValues=!!v&&v.q==="v2"&&v.pick==="b"&&dlg.hidden;
p=pc.dialog("Ask again",[{name:"q",label:"Question"}]);await b.ready(30);
df.querySelector(".pc-dialog-no").click();v=await p;
out.dialogCancelNull=v===null&&dlg.hidden;
// confirm(q, more): ответ человека; вопрос несёт q и more
const asked=[];w.confirm=q=>{asked.push(q);return asked.length===1};
out.confirmYes=pc.confirm("Remove it?","It goes for good.")===true&&/Remove it\?/.test(asked[0])&&/It goes for good\./.test(asked[0]);
out.confirmNo=pc.confirm("Remove that?")===false;
w.close();
}
out.errors=errs;
b.report(out,["errors"]);
try{fs.unlinkSync(TMP)}catch(e){}
process.exit(0);
})();
