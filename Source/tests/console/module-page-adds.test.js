// Вызовы оболочки в библиотеку (P/07 Н1.5 adds), которых не звал ни один тест: addNote(kind, fn) — слова страницы о
// единице предупреждениями под «Размещением» (строка или список, текстом); addIcons({имя: svg}) — значки страницы по
// имени для addDecor и узлов addTreeNodes, icon(name) — их разметка, ненарисованное имя — точка; fullScreen() — тот же
// полный экран, что кнопка шапки; isFav(ref) / toggleFav(ref) — избранное синхронно со звездой узла, звездой карточки,
// панелью и хранилищем браузера. Поведение кликами — module-view, module-tree. Аудит покрытия P/07 (90661897f).
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
out.errors=errs;
b.report(out,["errors"]);
try{fs.unlinkSync(TMP)}catch(e){}
process.exit(0);
})();
