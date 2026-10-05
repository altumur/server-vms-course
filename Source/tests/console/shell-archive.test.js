// Вкладка «Архив» камеры на странице VMS курса: её записи (/rec/recordings) — состояние словом, выключить и включить,
// том, срок, «когда писать» у записи на резервном томе (только у неё), удалить после подтверждения — каждое действие
// сразу записью через console.api (PUT/DELETE /rec/recordings/<имя>); её удержания (/rec/keeps) — поставить (с — по,
// зачем) и снять. Без rec в консоли — карточка «подсистема записи не подключена», без кнопок.
const fs=require("fs"),path=require("path");
const PAGE=fs.readFileSync(path.join(__dirname,"..","..","vms","shell.html"),"utf8");
const MOD=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"shell-arc-"+process.pid+".html");
fs.writeFileSync(TMP,PAGE.replace(/<script src="\/platform\/console\.js\?v=1"><\/script>/,()=>`<script>${MOD}</script>`));
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
const now=Date.now()/1000;
b.FIX["/session"]={open:true};
b.FIX["/spec"]={name:"vms",rows:"cameras",id:"numeric",fields:[{name:"name",type:"string"}]};
b.FIX["/mounts"]={root:"vms",mounts:{rec:{name:"rec",rows:"recordings",id:"name",about:{sub:"vms",field:"cam"},places:{table:"volumes"},fields:[{name:"cam",type:"string"}]}}};
b.FIX["/cameras"]={configured:[{id:1,name:"ворота"}],rows:[{id:1,worker:"w-1",phase:"running"}]};
b.FIX["/rec/recordings"]={configured:[{id:"1",cam:"1",home:"disk-a",retention_days:30,enabled:true},{id:"1-b",cam:"1",home:"bk",retention_days:7,enabled:false,when:"offline"}],
  rows:[{id:"1",worker:"r-1",server:"box-a",phase:"running"}]};
b.FIX["/rec/volumes"]={volumes:[{name:"disk-a",server:"box-a",kind:"local",url:"file:///a",quota_bytes:1e11,enabled:true,held_by:"r-1"},{name:"bk",server:"box-b",kind:"backup",url:"file:///b",quota_bytes:1e11,enabled:true}]};
b.FIX["/rec/keeps"]={keeps:[{name:"1-100-200",cam:"1",from:now-7200,to:now-3600,note:"кража",by:"murat",at:now-3000}]};
b.FIX["/servers"]={servers:{"box-a":{resource:"live",workers:[]}},policy:{}};
b.FIX["/events"]={events:[],state:"live"};
(async()=>{
const w=b.boot();const errs=[];w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
let confirmed=[];w.confirm=q=>{confirmed.push(q);return true};
await b.ready(700);await w.platformConsole.ready;await w.eval("reloadRec()");await b.ready(60);
const d=w.document,pc=w.platformConsole,out={};
const main=()=>d.querySelector("main"),tab=()=>main().querySelector('.pc-tab[data-tab="rec"]');
const call=(n,m,p)=>w.__calls.slice(n).find(x=>x.method===m&&x.path===p);
pc.select("unit:vms/1");await b.ready(60);
main().querySelector('.pc-tabs [data-tab="rec"]').click();await b.ready(200);
const t=tab().textContent+" "+[...tab().querySelectorAll("input")].map(x=>x.value).join(" | ");
out.recordingsListed=/Запись камеры/.test(t)&&/том «disk-a»/.test(t)&&/Пишет/.test(t)&&/Выключена/.test(t)&&/r-1 · box-a/.test(t);
// «когда писать» — только у записи на резервном томе
const whens=[...tab().querySelectorAll('[data-act="when"]')];
out.whenOnlyOnBackup=whens.length===1&&whens[0].dataset.rec==="1-b"&&whens[0].value==="offline";
const btn=(act,rec)=>tab().querySelector(`[data-act="${act}"][data-rec="${rec}"]`);
let n=w.__calls.length;btn("toggle","1").click();await b.ready(100);
let c=call(n,"PUT","/rec/recordings/1");out.switchOff=!!c&&JSON.stringify(c.body)==='{"enabled":false}'&&!!c.key;
n=w.__calls.length;btn("toggle","1-b").click();await b.ready(100);
c=call(n,"PUT","/rec/recordings/1-b");out.switchOn=!!c&&JSON.stringify(c.body)==='{"enabled":true}';
const home=btn("home","1");home.value="";n=w.__calls.length;home.dispatchEvent(new w.Event("change"));await b.ready(100);
c=call(n,"PUT","/rec/recordings/1");out.homeAny=!!c&&JSON.stringify(c.body)==='{"home":""}';
const days=btn("days","1");days.value="0";n=w.__calls.length;days.dispatchEvent(new w.Event("change"));await b.ready(60);
out.badDaysNotSent=!call(n,"PUT","/rec/recordings/1");
btn("days","1").value="45";n=w.__calls.length;btn("days","1").dispatchEvent(new w.Event("change"));await b.ready(100);
c=call(n,"PUT","/rec/recordings/1");out.days=!!c&&JSON.stringify(c.body)==='{"retention_days":45}';
const wh=btn("when","1-b");wh.value="always";n=w.__calls.length;wh.dispatchEvent(new w.Event("change"));await b.ready(100);
c=call(n,"PUT","/rec/recordings/1-b");out.when=!!c&&JSON.stringify(c.body)==='{"when":"always"}';
n=w.__calls.length;btn("del","1-b").click();await b.ready(100);
out.deleteAsksFirst=confirmed.some(q=>/Удалить запись «1-b»/.test(q))&&!!call(n,"DELETE","/rec/recordings/1-b");
// удержания: список, поставить, снять
out.keepListed=/Удержание/.test(tab().textContent)&&/кража/.test(tab().textContent)&&/поставил murat/.test(tab().textContent);
tab().querySelector('[data-act="addKeep"]').click();await b.ready(40);
const f=d.querySelector(".pc-dialog-f");f.elements.note.value="драка";
n=w.__calls.length;f.dispatchEvent(new w.Event("submit",{cancelable:true}));await b.ready(120);
c=call(n,"POST","/rec/keeps");
out.keepMade=!!c&&c.body.cam==="1"&&c.body.note==="драка"&&c.body.to>c.body.from&&Math.abs(c.body.to-c.body.from-3600)<120&&!!c.key;
n=w.__calls.length;tab().querySelector('[data-act="lift"]').click();await b.ready(100);
out.keepLifted=!!call(n,"DELETE","/rec/keeps/1-100-200");
out.errors=errs;
b.report(out,["errors"]);
// без rec: архива нет — так и сказано
for(const k of ["/mounts","/rec/recordings","/rec/volumes","/rec/keeps"])delete b.FIX[k];
const w2=b.boot();await b.ready(700);await w2.platformConsole.ready;await w2.eval("reloadRec()");
w2.platformConsole.select("unit:vms/1");await b.ready(60);
w2.document.querySelector('main .pc-tabs [data-tab="rec"]').click();await b.ready(150);
const off={noRecSaid:/подсистема записи не подключена/.test(w2.document.querySelector("main").textContent)&&!w2.document.querySelector('main [data-act="addRec"]')};
b.report(off);
try{fs.unlinkSync(TMP)}catch(e){}
process.exit(0);
})();
