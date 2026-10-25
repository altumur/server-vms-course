// Поздний ответ «Журнала»: /events ответил, когда человек уже ушёл из раздела. Модуль журнал не рисует и не падает —
// списка .pc-evlist в чужой карточке нет, ошибки нет, карточка, куда ушли, цела (задача «Архитектора» по находке ревью
// доп. (22): paintJournal без проверки, что раздел ещё на экране).
const fs=require("fs"),path=require("path");
const PAGE=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.html"),"utf8");
const MOD=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"pc-journal-late-"+process.pid+".html");
fs.writeFileSync(TMP,PAGE.replace(/<script src="\/platform\/console\.js\?v=1"><\/script>/,()=>`<script>${MOD}</script>`)
  .replace('PlatformConsole.mount(app)','PlatformConsole.mount(app, { lang: "ru" })'));
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
b.FIX["/session"]={open:true};
b.FIX["/manifest"]={name:"testsub",rows:"things",id:"numeric",fields:[{name:"name",type:"string"}]};
b.FIX["/things"]={configured:[{id:1,name:"a"}],rows:[]};
b.FIX["/events"]={events:[{t:100,kind:"unit.started",unit:"testsub/1"}]};
const errs=[];process.on("unhandledRejection",e=>errs.push(String(e&&e.message||e)));
(async()=>{
const w=b.boot();w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
w.addEventListener("unhandledrejection",e=>errs.push(String(e.reason&&e.reason.message||e.reason)));
await b.ready(400);await w.platformConsole.ready;
const d=w.document,out={};
// /events держим, пока человек не уйдёт из журнала
let release;const gate=new Promise(r=>release=r);const real=w.fetch;
w.fetch=(url,init)=>String(url).split("?")[0].endsWith("/events")?gate.then(()=>real(url,init)):real(url,init);
d.querySelector('.pc-rail [data-s="journal"]').click();await b.ready(50);
out.journalAsked=!!d.querySelector("main .pc-evlist");
d.querySelector('.pc-rail [data-s="units"]').click();await b.ready(100);
const before=d.querySelector("main").innerHTML;
release();await b.ready(200);
out.lateNotPainted=!d.querySelector("main .pc-evlist");
out.cardKept=d.querySelector("main").innerHTML===before;
out.noError=errs.length===0;
out.errors=errs;
b.report(out,["errors"]);
process.exit(0);
})();
