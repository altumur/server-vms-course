// «Камеру в архив» на странице VMS курса: запись камеры на томе сервера — POST /rec/recordings {name, cam, home,
// retention_days} через console.api. Из блока «Архивы сервера» и шапки карточки сервера (addBlock, addAction), из меню
// строки сервера и тома (addMenu), с карточки тома и со вкладки «Архив» камеры. В выборе — только тома этого сервера
// (и сетевые) и только камеры, которых там ещё нет; имя — номер камеры, а если оно занято, <номер>-<том>; негодный
// срок не уходит. Двери домена (/domain/crossings) курс не отдаёт — страница туда не ходит.
const fs=require("fs"),path=require("path");
const PAGE=fs.readFileSync(path.join(__dirname,"..","..","vms","vms.shell.html"),"utf8");
const MOD=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"shell-aadd-"+process.pid+".html");
fs.writeFileSync(TMP,PAGE.replace(/<script src="\/platform\/console\.js\?v=1"><\/script>/,()=>`<script>${MOD}</script>`));
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
b.FIX["/session"]={open:true};
b.FIX["/spec"]={name:"vms",rows:"cameras",id:"numeric",fields:[{name:"name",type:"string"}]};
b.FIX["/mounts"]={root:"vms",mounts:{rec:{name:"rec",rows:"recordings",id:"name",about:{sub:"vms",field:"cam"},places:{table:"volumes"},fields:[{name:"cam",type:"string"}]}}};
b.FIX["/cameras"]={configured:[{id:1,name:"ворота"},{id:2,name:"двор"},{id:3,name:"склад"}],rows:[]};
b.FIX["/rec/recordings"]={configured:[{id:"1",cam:"1",home:"disk-a",retention_days:30},{id:"2",cam:"2",home:"nas",retention_days:30}],rows:[]};
b.FIX["/rec/volumes"]={volumes:[{name:"disk-a",server:"box-a",kind:"local",url:"file:///a",quota_bytes:1e11,enabled:true,held_by:"r-1"},
  {name:"disk-b",server:"box-b",kind:"local",url:"file:///b",quota_bytes:1e11,enabled:true},{name:"nas",kind:"network",url:"s3://x",quota_bytes:1e12,enabled:true}]};
b.FIX["/rec/keeps"]={keeps:[]};
b.FIX["/servers"]={servers:{"box-a":{resource:"live",workers:[]},"box-b":{resource:"live",workers:[]}},policy:{}};
b.FIX["/events"]={events:[],state:"live"};
(async()=>{
const w=b.boot();const errs=[];w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
w.confirm=()=>true;
await b.ready(700);await w.platformConsole.ready;await w.eval("reloadRec()");await b.ready(60);
const d=w.document,pc=w.platformConsole,out={},ev=w.eval.bind(w);
const main=()=>d.querySelector("main");
const dlg=()=>d.querySelector(".pc-dialog"),field=n=>d.querySelector(`.pc-dialog-f [name="${n}"]`);
const opts=n=>[...d.querySelectorAll(`.pc-dialog-f [name="${n}"] option`)].map(o=>o.value);
const ok=async()=>{d.querySelector(".pc-dialog-f").dispatchEvent(new w.Event("submit",{cancelable:true}));await b.ready(120)};
const no=()=>d.querySelector(".pc-dialog-no").click();
const lastPost=n=>w.__calls.slice(n).find(x=>x.method==="POST"&&x.path==="/rec/recordings");
// карточка сервера: блок «Архивы сервера» — его тома; «＋ Камеру в архив» в блоке и в шапке
pc.select("server:box-a");await b.ready(80);
const blk=main().querySelector('.pc-block[data-block="vols"]');
out.serverBlock=!!blk&&/Архивы сервера/.test(blk.textContent)&&/disk-a/.test(blk.textContent)&&!/disk-b/.test(blk.textContent)&&/Обслуживается: r-1/.test(blk.textContent);
out.headButton=[...d.querySelectorAll(".pc-hd .pc-acts button")].some(x=>/Камеру в архив/.test(x.textContent));
blk.querySelector('[data-act="arc"]').click();await b.ready(40);
out.dialogOpens=!dlg().hidden;
out.onlyThisServersVolumes=JSON.stringify(opts("home"))==='["disk-a","nas"]';
out.onlyMissingCameras=JSON.stringify(opts("cam"))==='["2","3"]';
field("cam").value="3";field("home").value="disk-a";field("days").value="14";
let n=w.__calls.length;await ok();
let c=lastPost(n);
out.recordingCreated=!!c&&JSON.stringify(c.body)==='{"name":"3","cam":"3","retention_days":14,"home":"disk-a"}'&&!!c.key;
// имя занято — <камера>-<том>
blk.isConnected||0;pc.select("server:box-a");await b.ready(60);
ev("addToArchive({server:'box-a'})");await b.ready(30);
field("cam").value="2";field("home").value="disk-a";n=w.__calls.length;await ok();
c=lastPost(n);
out.takenNameGetsVolume=!!c&&c.body.name==="2-disk-a"&&c.body.home==="disk-a";
// негодный срок не уходит
ev("addToArchive({server:'box-a'})");await b.ready(30);
field("days").value="0";n=w.__calls.length;await ok();
out.badDaysNotSent=!lastPost(n);
// меню строки сервера и тома
const open=()=>{for(let i=0;i<4;i++)d.querySelectorAll(".pc-tree [data-tw]").forEach(t=>{if(t.textContent==="▸")t.click()})};
(d.querySelector('.pc-rail [data-s="units"]').click(),d.querySelector('.pc-layout').click(),d.querySelector('[data-layout="servers"]').click());await b.ready(40);open();
const menu=ref=>{const x=d.querySelector(`.pc-tree .n[data-ref="${ref}"]`);if(!x)return"";x.dispatchEvent(new w.MouseEvent("contextmenu",{bubbles:true,clientX:5,clientY:5}));return[...d.querySelectorAll(".pc-menu button")].map(y=>y.textContent).join("|")};
out.serverMenu=/Добавить камеру в архив/.test(menu("server:box-a"));
out.volumeMenu=/Добавить камеру в этот архив/.test(menu("vol:disk-b"));
// с карточки тома: том подставлен, других нет
pc.select("vol:disk-b");await b.ready(60);
main().querySelector('[data-act="addCam"]').click();await b.ready(30);
out.fromVolumeCard=JSON.stringify(opts("home"))==='["disk-b"]'&&opts("cam").length===3;
no();
// со вкладки «Архив» камеры: камера выбрана, тома — любые и «любой свободный»
pc.select("unit:vms/1");await b.ready(60);
main().querySelector('.pc-tabs [data-tab="rec"]').click();await b.ready(150);
main().querySelector('[data-act="addRec"]').click();await b.ready(30);
out.fromCameraTab=JSON.stringify(opts("cam"))==='["1"]'&&opts("home")[0]===""&&opts("home").length===4;
field("home").value="nas";n=w.__calls.length;await ok();
c=lastPost(n);
out.fromCameraSent=!!c&&c.body.name==="1-nas"&&c.body.cam==="1"&&c.body.home==="nas";
out.noDomainDoors=!w.__calls.some(x=>/^\/domain\//.test(x.path));
out.errors=errs;
b.report(out,["errors"]);
try{fs.unlinkSync(TMP)}catch(e){}
process.exit(0);
})();
