// Перерисовка опроса не моргает: вкладка страницы, которая рисуется после своего запроса, и карточка страницы не
// бывают пустыми между старым и новым видом — новый хост начинается с прежнего содержимого; у карточки страницы шапка
// (заголовок, звезда) остаётся, пока страница не нарисует новый заголовок. Переход на вкладку рисуется с чистого листа.
const fs=require("fs"),path=require("path");
const PAGE=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.html"),"utf8");
const MOD=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"pc-steady-"+process.pid+".html");
fs.writeFileSync(TMP,PAGE.replace(/<script src="\/platform\/console\.js\?v=1"><\/script>/,()=>`<script>${MOD}</script>`)
  .replace('PlatformConsole.mount(document.getElementById("app"))','PlatformConsole.mount(document.getElementById("app"), { lang: "ru", poll_s: 0 })'));
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
b.FIX["/session"]={open:true};
b.FIX["/spec"]={name:"testsub",rows:"things",id:"numeric",fields:[{name:"name",type:"string"}]};
b.FIX["/things"]={configured:[{id:1,name:"one"}],rows:[]};
(async()=>{
  const w=b.boot();const errs=[];w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
  await b.ready(300);const pc=w.platformConsole;await pc.ready;const d=w.document,out={};
  // вкладка, которая рисуется после «запроса»: его держит тест
  let gate=null,n=0;
  pc.addTab("unit",{id:"slow",label:"Медленная",render:async host=>{const i=++n;await new Promise(r=>{gate=r});host.innerHTML=`<p class="slow">вид ${i}</p>`}});
  pc.addCard("page",async (host,ref)=>{const i=++n;await new Promise(r=>{gate=r});host.innerHTML=`<h1>Страница ${i}</h1><p class="pg">карточка ${i}</p>`});
  pc.select("unit:testsub/1");await b.ready(30);
  d.querySelector('.pc-tabs [data-tab="slow"]').click();await b.ready(10);
  out.tabSwitchStartsClean=d.querySelector('.pc-tab[data-tab="slow"]').textContent==="";
  gate();await b.ready(10);
  const tab=()=>d.querySelector('.pc-tab[data-tab="slow"]');
  out.tabDrawn=/вид 1/.test(tab().textContent);
  await pc.refresh();await b.ready(10);
  out.tabNotBlankWhileRedrawing=/вид 1/.test(tab().textContent);
  gate();await b.ready(10);
  out.tabRedrawn=/вид 2/.test(tab().textContent);
  // карточка страницы: заголовок в шапке остаётся, пока не придёт новый
  pc.select("page:x");await b.ready(10);gate();await b.ready(30);
  const head=()=>d.querySelector(".pc-hd").textContent;
  out.cardDrawn=/Страница 3/.test(head())&&/карточка 3/.test(d.querySelector(".pc-main").textContent);
  await pc.refresh();await b.ready(10);
  out.cardAndHeadKeptWhileRedrawing=/Страница 3/.test(head())&&/карточка 3/.test(d.querySelector(".pc-main").textContent)&&!!d.querySelector(".pc-hd .pc-star");
  gate();await b.ready(30);
  out.cardAndHeadRedrawn=/Страница 4/.test(head())&&/карточка 4/.test(d.querySelector(".pc-main").textContent)&&!/Страница 3/.test(head());
  out.errors=errs;out.noErrors=!errs.length;
  b.report(out);
  try{fs.unlinkSync(TMP)}catch(e){}
  process.exit(0);
})();
