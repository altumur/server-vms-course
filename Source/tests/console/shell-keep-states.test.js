// Состояние удержаний из биения регистраторов (ADR-0064): спека rec называет в servers.status поля с of: keeps —
// keeps {<удержание>: {state…}}, incidents_lost {<удержание>: секунды}, incidents_at_risk [<удержание>]. Строки
// регистраторов — в /rec/servers (корневой /servers знает только своих воркеров). Каждый говорит своё: пишущий
// запись — here/pushing/pushed/at risk/lost с recording, держатель архива инцидентов — kept/released/garbled.
// Страница сопоставляет ключи со строками rec/keeps; чего спека не назвала, не читает. Копия продуктового
// vmsworker/vms/consoletest/shell-keep-states.test.js (другое здесь — путь страницы).
const fs=require("fs"),path=require("path");
const PAGE=fs.readFileSync(path.join(__dirname,"..","..","vms","vms.shell.html"),"utf8");
const MOD=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"shell-ks-"+process.pid+".html");
fs.writeFileSync(TMP,PAGE.replace(/<script src="\/platform\/console\.js\?v=1"><\/script>/,()=>`<script>${MOD}</script>`).replace('{lang:"ru",','{lang:"ru",poll_s:0,'));
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
const P=`x"'><img src=x onerror=window.__pwned=1>`;
const STATUS=[{field:"keeps",title:"удержания",of:"keeps"},{field:"incidents_lost",title:"потеряно",of:"keeps"},{field:"incidents_at_risk",title:"под угрозой",of:"keeps"}];
b.FIX["/session"]={open:true};
b.FIX["/spec"]={name:"vms",rows:"cameras",id:"numeric",fields:[{name:"name",type:"string"}]};
b.FIX["/mounts"]={root:"vms",mounts:{rec:{name:"rec",rows:"recordings",id:"name",about:{sub:"vms",field:"cam"},places:{table:"volumes"},fields:[{name:"cam",type:"string"}],servers:{status:STATUS}}}};
b.FIX["/cameras"]={configured:[{id:1,name:"ворота"}],rows:[{id:1,worker:"w-1",phase:"running"}]};
b.FIX["/rec/recordings"]={configured:[{id:"1",cam:"1",home:"disk",retention_days:30,enabled:true}],rows:[]};
b.FIX["/rec/volumes"]={volumes:[{name:"inc",kind:"incidents",server:"box-a",enabled:true,admits:false,quota_bytes:1e9,held_by:"r-2"}]};
b.FIX["/rec/keeps"]={keeps:[{name:"k-kept",cam:"1",from:100,to:200,note:"note-a"},{name:"k-wait",cam:"1",from:300,to:400,note:"note-b"},{name:"k-lost",cam:"1",from:500,to:600,note:"note-c"},{name:"k-quiet",cam:"1",from:700,to:800,note:"note-d"},
  {name:"k-here",cam:"1",from:900,to:1000,note:"note-e"},{name:"k-push",cam:"1",from:1100,to:1200,note:"note-f"},{name:"k-gone",cam:"1",from:1300,to:1400,note:"note-g"}]};
b.FIX["/servers"]={servers:{"box-a":{resource:"live",workers:[{worker:"w-1",capacity:5,load:1,state:"live",status:{keeps:{"k-quiet":{state:"kept"}}}}]}},policy:{}};
b.FIX["/rec/servers"]={servers:{"box-a":{resource:"live",workers:[
  {worker:"r-1",capacity:1,load:1,state:"live",status:{"writer.state":"ok",keeps:{
    "k-here":{recording:"1-sd",state:"here",seconds:7,leaves_in_s:258841},
    "k-wait":{recording:"1-sd",state:"at risk",why:"no incident archive is served"+P},
    "k-lost":{recording:"1-sd",state:"lost",lost_seconds:42,why:"the ring wrote over it"},
    "k-push":{recording:"1-sd",state:"pushing",seconds:30}}}},
  {worker:"r-2",capacity:1,load:1,state:"live",status:{"writer.state":"ok",incidents:true,
    keeps:{"k-kept":{state:"kept",seconds:120,empty:["1-sd"]},"k-gone":{state:"released",why:"отпущено оператором",released_at:1}},
    incidents_lost:{"k-lost":42},incidents_at_risk:["k-wait"],[P]:P}}]}},policy:{}};
b.FIX["/events"]={events:[],state:"live"};
(async()=>{
const w=b.boot();const errs=[];w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
await b.ready(700);await w.platformConsole.ready;await w.platformConsole.refresh();await w.eval("reloadRec()");const d=w.document,pc=w.platformConsole,out={};
pc.select("unit:vms/1");await b.ready(80);
d.querySelector('.pc-tabs [data-tab="rec"]').click();await b.ready(200);
const rows=[...d.querySelectorAll('.pc-tab[data-tab="rec"] .it')],row=n=>rows.find(x=>x.textContent.includes(n))||{textContent:""};
out.keptSaid=/в архиве инцидентов · 120 с/.test(row("note-a").textContent);
out.emptyRecordingsSaid=/в отрезке нет кадров у 1-sd — запечатывать нечего/.test(row("note-a").textContent);
out.atRiskWhy=/1-sd: под угрозой/.test(row("note-b").textContent)&&/no incident archive is served/.test(row("note-b").textContent)&&/кольцо записи заберёт раньше/.test(row("note-b").textContent);
out.lostSaid=/1-sd: потеряно · 42 с/.test(row("note-c").textContent)&&/the ring wrote over it/.test(row("note-c").textContent)&&/архив инцидентов потерял 42 с/.test(row("note-c").textContent);
// a keep's state comes only from rec's recorders: the root's worker saying keeps is not read
out.quietSaysNothing=!/в архиве|копир|потеря|угроз/.test(row("note-d").textContent);
out.hereSaid=/1-sd: в архиве записи · 7 с · кольцо заберёт через 2 д 23 ч/.test(row("note-e").textContent);
out.pushingSaid=/1-sd: копируется в архив инцидентов · 30 с/.test(row("note-f").textContent);
out.releasedWhy=/отпущено/.test(row("note-g").textContent)&&/отпущено оператором/.test(row("note-g").textContent);
out.neverRan=w.__pwned===undefined&&!d.querySelector("main img");
out.errors=errs;out.noErrors=!errs.length;
b.report(out);
try{fs.unlinkSync(TMP)}catch(e){}
process.exit(0);
})();
