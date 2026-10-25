// Метки сервера не прочитаны: консоль отдаёт ServerRow.labels: null, labels_source: null и WorkerRow.labels: null (строка
// platform/servers/<s> не читается — общее правило выдачи этапа 3). Модуль не подставляет метки узла как действующие: в
// карточке сервера тегов нет и сказано, что строку не прочитать; у воркера — «метки не прочитаны» (C06-MODULE-LABELS-D8-01).
const fs=require("fs"),path=require("path");
const PAGE=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.html"),"utf8");
const MOD=fs.readFileSync(process.env.MODULE_FILE||path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"pc-labels-unread-"+process.pid+".html");
fs.writeFileSync(TMP,PAGE.replace(/<script src="\/platform\/console\.js\?v=1"><\/script>/,()=>`<script>${MOD}</script>`)
  .replace('PlatformConsole.mount(app)','PlatformConsole.mount(app, { lang: "ru" })'));
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
b.FIX["/session"]={open:true};
b.FIX["/manifest"]={name:"testsub",rows:"things",id:"numeric",fields:[{name:"name",type:"string"}]};
b.FIX["/things"]={configured:[{id:1,name:"a"}],rows:[]};
b.FIX["/servers"]={policy:{servers:"shared"},servers:{"srv-a":{resource:"live",labels:null,labels_source:null,labels_node:["gpu"],
  workers:[{worker:"w-1",load:0,capacity:5,labels:null,state:"live",idle_by_policy:false,hung:false,name_conflict:false}]}}};
const errs=[];process.on("unhandledRejection",e=>errs.push(String(e&&e.message||e)));
(async()=>{
const w=b.boot();w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
await b.ready(400);await w.platformConsole.ready;
const d=w.document,pc=w.platformConsole,out={},main=()=>d.querySelector("main");
pc.select("server:srv-a");await b.ready(150);
const box=main().querySelector(".pc-labels");
out.serverNoNodeTags=!!box&&![...box.querySelectorAll(".pc-tag")].some(t=>t.textContent==="gpu");
out.serverSaysUnread=!!box&&/не прочитать/.test(box.textContent);
out.workerListSaysUnread=/метки не прочитаны/.test(main().textContent);
main().querySelector('.it[data-ref^="worker:"]').click();await b.ready(500);   // карточка воркера — по его строке в карточке сервера
const vals=[...main().querySelectorAll("input")].map(i=>i.value);   // поля карточки — только для чтения, значение в value
out.workerCardSaysUnread=vals.includes("метки не прочитаны")&&!vals.some(v=>/\bgpu\b/.test(v));
out.noError=errs.length===0;
out.errors=errs;
b.report(out,["errors"]);
process.exit(0);
})();
