// Домен глазами VMS на странице курса — из вида держателя домена (/domain: его units и tables): под членом его камеры и
// архивы (addTreeNodes), карточки камеры и архива (addCard: имя в домене, номер, воркер, сервер, «пишет кластер» из
// таблицы vms/crossings), блок члена «Камеры» и «Архивы» без платформенных частей (addBlock), на «Обзоре» домена —
// «Пересечения». Только чтение: правки домена идут его дверью, курс не отдаёт их консоли — страница туда не пишет.
// Члены в фикстуре — списком, как их ждёт модуль (контракт; курсовой /domain пока говорит их словарём — долг части A,
// в отчёте шага); камеры и архивы — units курса, пересечения — его tables.
const fs=require("fs"),path=require("path");
const PAGE=fs.readFileSync(path.join(__dirname,"..","..","vms","vms.shell.html"),"utf8");
const MOD=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"shell-dom-"+process.pid+".html");
fs.writeFileSync(TMP,PAGE.replace(/<script src="\/platform\/console\.js\?v=1"><\/script>/,()=>`<script>${MOD}</script>`));
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
const u=(sub,cluster,unit,o={})=>({sub,cluster,unit,ref:"",name:"",server:cluster+"-srv",worker:sub==="vms"?"w-1":"r-1",phase:"running",worker_state:"live",as_of:"as of 2 s ago",...o});
b.FIX["/session"]={open:true};
b.FIX["/spec"]={name:"vms",rows:"cameras",id:"numeric",fields:[{name:"name",type:"string"}]};
b.FIX["/cameras"]={configured:[],rows:[]};
b.FIX["/servers"]={servers:{"box-a":{resource:"live",workers:[]}},policy:{}};
b.FIX["/events"]={events:[],state:"live"};
b.FIX["/domain"]={holder:"srv",age:1,complete:true,members:["srv","office","north"].map(n=>({name:n,state:"ok",age:2,holder:n==="srv"})),
  units:[u("vms","office","1",{ref:"SN-A",name:"door a"}),u("vms","office","2",{ref:"SN-B",name:"door b",worker_state:"stale"}),u("rec","office","1"),
         u("vms","north","1",{ref:"SN-C",name:"gate",worker_state:"configured"}),u("vms","north","2",{ref:"SN-D",name:"yard"})],
  tables:{"vms/crossings":{"SN-C":"office"}},causes:[]};
(async()=>{
const w=b.boot();const errs=[];w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
await b.ready(700);await w.platformConsole.ready;await w.platformConsole.refresh();await b.ready(50);
const d=w.document,pc=w.platformConsole,out={};
const main=()=>d.querySelector("main"),txt=()=>main().textContent+" "+[...main().querySelectorAll("input")].map(x=>x.value).join(" | ");
(d.querySelector('.pc-rail [data-s="units"]').click(),d.querySelector('.pc-layout').click(),d.querySelector('[data-layout="servers"]').click());await b.ready(40);
d.querySelectorAll('.pc-tree [data-tw^="member:"]').forEach(t=>{if(t.textContent==="▸")t.click()});await b.ready(20);
const row=r=>d.querySelector(`.pc-tree .n[data-ref="${r}"]`);
out.camerasUnderMember=!!row("dc:office/1")&&!!row("dc:office/2")&&!!row("dc:north/1")&&!!row("dc:north/2");
out.cameraSignAndRef=!!row("dc:office/1").querySelector(".ici-camera")&&/SN-A/.test(row("dc:office/1").textContent);
out.archiveAfterCameras=!!row("da:office/1")&&[...d.querySelectorAll(".pc-tree .n")].indexOf(row("dc:office/2"))<[...d.querySelectorAll(".pc-tree .n")].indexOf(row("da:office/1"));
// камера: имя в домене, номер, воркер, сервер; кто её пишет — из пересечений
pc.select("dc:north/1");await b.ready(60);
out.cameraCard=/gate/.test(txt())&&/SN-C/.test(txt())&&/north-srv/.test(txt())&&/настроена, никто не держит/.test(txt())&&[...main().querySelectorAll("input")].some(x=>x.value==="office")&&!!main().querySelector(".pc-star");
pc.select("dc:office/2");await b.ready(60);
out.staleSaid=/воркер молчит/.test(txt());
pc.select("da:office/1");await b.ready(60);
out.archiveCard=/Архив · 1/.test(txt())&&/r-1/.test(txt())&&/задаются в самом кластере/.test(txt());
// блок члена: камеры и архивы; платформенное (вывод из домена и т. п.) — модуля, не в блоке
pc.select("member:office");await b.ready(60);
const blk=main().querySelector('.pc-block[data-block="vms"]');
out.memberBlock=!!blk&&/Камеры/.test(blk.textContent)&&/door a/.test(blk.textContent)&&/Архивы/.test(blk.textContent)&&!/Вывести из домена/.test(blk.textContent);
blk.querySelector('[data-act="go"]').click();await b.ready(60);
out.blockRowOpensCard=pc.selected()==="dc:office/1";
// обзор домена: пересечения
pc.select("domain");await b.ready(60);
const dom=main().querySelector('.pc-block[data-block="vms"]');
out.crossings=!!dom&&/Пересечения/.test(dom.textContent)&&/gate · north/.test(dom.textContent)&&/office/.test(dom.textContent);
out.readOnly=!w.__calls.some(x=>/^\/domain/.test(x.path));
out.errors=errs;
b.report(out,["errors"]);
try{fs.unlinkSync(TMP)}catch(e){}
process.exit(0);
})();
