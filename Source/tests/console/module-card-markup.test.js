// Разметка карточки целиком (P/07 Н1.5 cards: <h1>, nav.pc-tabs, <h2> → .card, button.pc-hdbtn,
// span.pc-crumbs[data-crumbs], p.pc-hdsub) — «слепок» на карточке оболочки (addCard): заголовок с крошками из
// data-crumbs — в шапку (крошки ведут к объекту), подзаголовок — под заголовок, полоса вкладок — в шапку, кнопки
// pc-hdbtn — в действия шапки, каждый <h2> — карточка .card (.ch над .cb) со своим содержимым до следующего заголовка,
// <h2> первым в своём блоке — сам блок карточкой; то же у нарисованного позже (после запроса страницы). Своё обзорное
// «<h1> + p.pc-hdsub» модуль пишет так же. Аудит покрытия P/07 (90661897f).
const fs=require("fs"),path=require("path");
const SRC=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"pc-cards-"+process.pid+".html");
fs.writeFileSync(TMP,`<!doctype html><div id="app"></div><script>${SRC}</script><script>window.pc=PlatformConsole.mount(document.getElementById("app"),{lang:"en"});</script>`);
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
b.FIX["/session"]={open:true};
b.FIX["/manifest"]={name:"testsub",rows:"things",id:"numeric",fields:[{name:"name",type:"string"}]};
b.FIX["/things"]={configured:[{id:1,name:"one"}],rows:[{id:1,worker:"w-1",server:"s-1",phase:"running"}]};
b.FIX["/servers"]={servers:{"s-1":{resource:"live",workers:[{worker:"w-1",load:1,capacity:5,state:"live"}]}},policy:{}};
const CARD=`<h1>Title <small>kind</small><span class="pc-crumbs" data-crumbs='[["Root","layout:servers"],["Mid","server:s-1"]]'></span></h1>`
  +`<p class="pc-hdsub">subtitle</p><nav class="pc-tabs"><button type="button" class="on">A</button><button type="button">B</button></nav>`
  +`<button type="button" class="pc-hdbtn">Act</button>`
  +`<h2>Section one</h2><p class="s1">body one</p><h2>Section two</h2><p class="s2">body two</p>`
  +`<div class="box"><h2>Boxed</h2><p class="s3">body three</p></div>`;
(async()=>{
const w=b.boot();const errs=[];w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
const pc=w.pc;
pc.addCard("x",(host,ref)=>{host.innerHTML=CARD});
// разделы подряд, не первым в блоке: перед первым <h2> — абзац страницы
pc.addCard("flat",host=>{host.innerHTML=`<h1>Flat</h1><p class="intro">intro</p><h2>Part A</h2><p class="pa">a</p><h2>Part B</h2><p class="pb">b</p>`});
pc.addCard("late",host=>{setTimeout(()=>{host.innerHTML=`<h1>Late</h1><p class="pc-hdsub">late sub</p><button type="button" class="pc-hdbtn">LateAct</button><h2>Later</h2><p class="l1">l</p>`},30)});
await pc.ready;await b.ready(100);const d=w.document,out={};
// шапка .pc-hd и тело .pc-main — оба внутри <main>
const hd=()=>d.querySelector(".pc-hd"),main=()=>d.querySelector(".pc-main");
// своё обзорное: <h1> и p.pc-hdsub — тоже в шапку
out.moduleOverviewHead=!main().querySelector("h1")&&!!hd().querySelector("p.pc-hdsub")&&/things|thing|servers/i.test(hd().textContent);
pc.select("x:one");await b.ready(80);
// <h1> — в шапку, span.pc-crumbs[data-crumbs] — крошки
out.h1IntoHead=!main().querySelector("h1")&&!!hd().querySelector(".cr-cur")&&hd().querySelector(".cr-cur").textContent.trim()==="Title";
out.crumbsFromData=[...hd().querySelectorAll(".cr-link")].map(x=>x.textContent+">"+x.dataset.go).join("|")==="Root>layout:servers|Mid>server:s-1"&&!d.querySelector(".pc-crumbs");
// p.pc-hdsub — под заголовок
out.hdsubIntoHead=!!hd().querySelector("p.pc-hdsub")&&hd().querySelector("p.pc-hdsub").textContent==="subtitle"&&!main().querySelector("p.pc-hdsub")
  &&!!(hd().querySelector(".hd-act").compareDocumentPosition(hd().querySelector("p.pc-hdsub"))&w.Node.DOCUMENT_POSITION_FOLLOWING);
// nav.pc-tabs — полоса вкладок шапки
const nav=hd().querySelector("nav.pc-tabs");
out.tabsIntoHead=!!nav&&!main().querySelector("nav.pc-tabs")&&nav.classList.contains("tabs")&&[...nav.querySelectorAll("button")].every(x=>x.classList.contains("tab"))&&nav.querySelectorAll("button").length===2;
// button.pc-hdbtn — в действия шапки
out.hdbtnIntoActions=!!hd().querySelector(".pc-acts button.pc-hdbtn")&&hd().querySelector(".pc-acts button.pc-hdbtn").textContent==="Act"&&!main().querySelector("button.pc-hdbtn");
// <h2> → .card: .ch над .cb, содержимое — до следующего заголовка
const cards=[...main().querySelectorAll(".card")];
const cardOf=t=>cards.find(c=>{const ch=c.querySelector(":scope > .ch");return ch&&ch.textContent===t});
const c1=cardOf("Section one"),c2=cardOf("Section two"),c3=cardOf("Boxed");
out.noH2Left=!main().querySelector("h2");
// первый <h2> карточки — первым в хосте страницы: его раздел — только до следующего заголовка
out.h2ToCard=!!c1&&!!c2&&!!c1.querySelector(":scope > .cb .s1")&&!c1.querySelector(".s2")&&!c1.contains(c2)&&!!c2.querySelector(":scope > .cb .s2")&&!c2.querySelector(".s3");
out.h2BoxIsCard=!!c3&&c3.classList.contains("box")&&!!c3.querySelector(":scope > .cb .s3");
out.headAboveBody=!!c1&&c1.firstElementChild.className==="ch"&&c1.lastElementChild.className==="cb";
// <h2> среди прочего: карточка — он и то, что за ним до следующего заголовка; абзац до него остаётся вне карточек
pc.select("flat:one");await b.ready(80);
{const fa=cardOfIn(main(),"Part A"),fb=cardOfIn(main(),"Part B");
 out.h2AmongOthersToCard=!!fa&&!!fb&&!!fa.querySelector(":scope > .cb .pa")&&!fa.querySelector(".pb")&&!!fb.querySelector(":scope > .cb .pb")&&!!main().querySelector(".intro")&&!main().querySelector(".intro").closest(".card");
 out.flatGot=main().innerHTML.slice(0,400);}
pc.select("x:one");await b.ready(80);
// крошка ведёт к объекту
[...hd().querySelectorAll(".cr-link")].find(x=>x.textContent==="Mid").click();await b.ready(50);
out.crumbGoes=pc.selected()==="server:s-1";
// нарисованное позже (после запроса страницы) — так же
pc.select("late:one");await b.ready(150);
out.lateDressed=!main().querySelector("h1")&&/Late/.test(hd().textContent)&&!!hd().querySelector("p.pc-hdsub")&&hd().querySelector("p.pc-hdsub").textContent==="late sub"
  &&!!hd().querySelector(".pc-acts button.pc-hdbtn")&&!main().querySelector("h2")&&!!cardOfIn(main(),"Later")&&!!cardOfIn(main(),"Later").querySelector(".cb .l1");
function cardOfIn(root,t){return [...root.querySelectorAll(".card")].find(c=>{const ch=c.querySelector(":scope > .ch");return ch&&ch.textContent===t})}
w.close();
out.errors=errs;
b.report(out,["errors","flatGot"]);
try{fs.unlinkSync(TMP)}catch(e){}
process.exit(0);
})();
