// Камера на странице VMS курса: что хост драйверов делает с ней — под «Размещением» карточки вслух: «открытие не
// завершается» (устройство ещё не открылось: device_state opening) и «сбой устройства» (phase failed, слова держателя);
// у работающей — ничего. Знак камеры и её адрес меткой в дереве (addDecor); источник с тем, что он говорит (адрес,
// производитель, канал — addFieldEditor), отправляет форма модуля. События VMS — словами в «Журнале» модуля
// (addEventNote): тома, карты, запись; неописанное — видом, без петли. (По образцу продуктового shell-camera-state.)
const fs=require("fs"),path=require("path");
const PAGE=fs.readFileSync(path.join(__dirname,"..","..","vms","vms.shell.html"),"utf8");
const MOD=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"shell-cst-"+process.pid+".html");
fs.writeFileSync(TMP,PAGE.replace(/<script src="\/platform\/console\.js\?v=1"><\/script>/,()=>`<script>${MOD}</script>`));
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
const now=Date.now()/1000;
b.FIX["/session"]={open:true};
b.FIX["/spec"]={name:"vms",rows:"cameras",id:"numeric",fields:[{name:"name",type:"string"},{name:"source",type:"url"},{name:"live",type:"string"}],
  display:{unit:"камера",units:"камеры",events:false,
    form:[{title:"Подключение",fields:["source"]},{title:"Размещение",placement:true,fields:["live"]}]}};
// слова видов — у спеки rec (её display.kinds), описание — у страницы
b.FIX["/mounts"]={root:"vms",mounts:{rec:{name:"rec",rows:"recordings",id:"name",about:{sub:"vms",field:"cam"},fields:[{name:"cam",type:"string"}],
  display:{kinds:{"volume.missing":"каталог тома пропал","archive.volume.shrunk":"том уменьшен","card.failing":"карта камеры сбоит","camera.uplink.short":"канал камеры не успевает"}}}}};
b.FIX["/rec/recordings"]={configured:[],rows:[]};
b.FIX["/cameras"]={configured:[{id:1,name:"ворота",source:"driverpack://acme/10.0.0.90/ch/1"},{id:2,name:"двор",source:"rtsp://10.0.0.12:8554/main"},{id:3,name:"склад",source:"driverpack://acme/10.0.0.50/ch/2"}],
 rows:[{id:1,worker:"w-1",phase:"running"},{id:2,worker:"w-1",phase:"running",device_state:"opening"},{id:3,worker:"w-1",phase:"failed",why:"its password cannot be opened: bad seal"}]};
b.FIX["/servers"]={servers:{"box-a":{workers:[{worker:"w-1",capacity:50,load:3,state:"live",labels:""}],resource:"live"}},policy:{}};
b.FIX["/events"]={events:[
  {t:now-60,subsystem:"rec",kind:"volume.missing",unit:"rec/main",class:"alarm",volume:"main",server:"box-a",recorder:"r-1",detail:"no such directory"},
  {t:now-30,subsystem:"rec",kind:"archive.volume.shrunk",unit:"rec/main",volume:"main",was:2147483648,quota_bytes:1073741824},
  {t:now-20,subsystem:"rec",kind:"card.failing",unit:"rec/1-sd",class:"alarm",state:"worn",error:"write error"},
  {t:now-10,subsystem:"rec",kind:"camera.uplink.short",unit:"rec/1-sd",class:"alarm",behind_s:95},
  {t:now-4,subsystem:"vms",kind:"camera.frames.absurd_time",unit:"vms/1"}],state:"live"};
(async()=>{
const w=b.boot();const errs=[];w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
await b.ready(700);await w.platformConsole.ready;const d=w.document,pc=w.platformConsole,out={};
const main=()=>d.querySelector("main").textContent+" "+[...d.querySelectorAll("main input")].map(x=>x.value).join(" | ");
// дерево: знак камеры и адрес меткой
const row=d.querySelector('.pc-tree [data-ref="unit:vms/1"]')||null;
const open=()=>{for(let i=0;i<3;i++)d.querySelectorAll(".pc-tree [data-tw]").forEach(t=>{if(t.textContent==="▸")t.click()})};open();
const r1=d.querySelector('.pc-tree [data-ref="unit:vms/1"]');
out.cameraSignAndAddress=!!r1&&!!r1.querySelector(".ici-camera")&&/10\.0\.0\.90/.test(r1.textContent);
pc.select("unit:vms/1");await b.ready(80);
out.runningSaysNothing=!/открытие не завершается|сбой устройства/.test(main());
// источник: адрес, производитель, канал — только для чтения; правка идёт в форму модуля
const src=d.querySelector("main .vms-src");
out.sourceRead=!!src&&/10\.0\.0\.90/.test(main())&&/acme/.test(main())&&[...d.querySelectorAll("main input[readonly]")].some(x=>x.value==="1");
src.value="driverpack://acme/10.0.0.91/ch/3";src.dispatchEvent(new w.Event("input",{bubbles:true}));
out.sourceReparsed=[...d.querySelectorAll("main input[readonly]")].some(x=>x.value==="10.0.0.91")&&[...d.querySelectorAll("main input[readonly]")].some(x=>x.value==="3");
pc.select("unit:vms/2");await b.ready(80);
out.openingSaid=/открытие не завершается/.test(main());
out.rtspHost=[...d.querySelectorAll("main input[readonly]")].some(x=>x.value==="10.0.0.12:8554");
pc.select("unit:vms/3");await b.ready(80);
out.failedSaid=/сбой устройства — its password cannot be opened/.test(main());
d.querySelector('.pc-rail [data-s="journal"]').click();await b.ready(200);
const t=main();
out.volumeMissingInWords=/каталог тома пропал/.test(t)&&/том main · на box-a · держал r-1 · no such directory/.test(t);
out.shrunkInWords=/том уменьшен/.test(t)&&/2\.0 ГБ → 1\.0 ГБ/.test(t);
out.cardInWords=/карта камеры сбоит/.test(t)&&/карта камеры: worn · write error/.test(t);
out.uplinkInWords=/канал камеры не успевает/.test(t)&&/отстаёт на 1 мин 35 с/.test(t);
out.noLoopOnUndescribed=/camera\.frames\.absurd_time/.test(d.querySelector("main").innerHTML);
out.errors=errs;
b.report(out,["errors"]);
try{fs.unlinkSync(TMP)}catch(e){}
process.exit(0);
})();
