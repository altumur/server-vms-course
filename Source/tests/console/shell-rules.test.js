// «Сценарии» страницы VMS курса — раздел страницы (addSection после «Объектов»): список сценариев подсистемы auto с их
// состоянием (следит, отказан — со словами вычислителя), редактор «если — то»: события со словами из display.kinds
// спеки VMS, действия — только те, под что написан исполнитель (каталог спеки auto; действия детекторов — когда консоль
// монтирует det), отказы — до отправки, теми же словами; новый — POST /auto/scenarios, существующий — PUT без имени,
// удаление — после подтверждения; последние срабатывания — события fired вычислителя.
const fs=require("fs"),path=require("path");
const PAGE=fs.readFileSync(path.join(__dirname,"..","..","vms","shell.html"),"utf8");
const MOD=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"shell-rules-"+process.pid+".html");
fs.writeFileSync(TMP,PAGE.replace(/<script src="\/platform\/console\.js\?v=1"><\/script>/,()=>`<script>${MOD}</script>`));
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
const now=Date.now()/1000;
b.FIX["/session"]={open:true};
b.FIX["/spec"]={name:"vms",rows:"cameras",id:"numeric",fields:[{name:"name",type:"string"}],display:{kinds:{"io.input":"вход устройства",silent:"камера молчит"}}};
b.FIX["/cameras"]={configured:[{id:1,name:"ворота"}],rows:[]};
b.FIX["/servers"]={servers:{},policy:{}};
b.FIX["/auto/scenarios"]={configured:[{id:"door",name:"door",enabled:true,when:JSON.stringify([{sub:"vms",kind:"io.input",unit:"12",match:{port:"1"}}]),then:JSON.stringify([{sub:"vms",action:"output",unit:"12",port:"2"}]),within:0},
  {id:"bad",name:"bad",enabled:true,when:[{sub:"vms",kind:"silent"}],then:[{sub:"rec",action:"record",cam:"9",minutes:"10"}]}],
  rows:[{id:"door",worker:"a-1",phase:"running"},{id:"bad",worker:"a-1",phase:"refused",why:"no camera 9",unfit:["no camera 9"]}]};
b.FIX["/events"]={events:[{t:now-60,subsystem:"auto",kind:"fired",unit:"auto/door",actions:1}],state:"live"};
(async()=>{
const w=b.boot();const errs=[];w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
let asked=[];w.confirm=q=>{asked.push(q);return true};
await b.ready(700);await w.platformConsole.ready;
const d=w.document,pc=w.platformConsole,out={};
const main=()=>d.querySelector("main"),host=()=>main().querySelector(".vms-rules");
const call=(n,m,p)=>w.__calls.slice(n).find(x=>x.method===m&&x.path===p);
const rail=d.querySelector('.pc-rail [data-s="rules"]');
out.sectionAfterUnits=!!rail&&rail.previousElementSibling&&rail.previousElementSibling.dataset.s==="units";
rail.click();await b.ready(200);
out.listed=/door/.test(host().textContent)&&/следит/.test(host().textContent)&&/отказан/.test(host().textContent);
const pick=id=>host().querySelector(`[data-act="pick"][data-id="${id}"]`).click();
pick("bad");await b.ready(60);
out.refusalShown=/Вычислитель отказал: no camera 9/.test(host().textContent);
pick("door");await b.ready(150);
out.whenRead=[...host().querySelectorAll('[data-act="tf"]')].map(x=>x.value).join("|")==="vms|io.input|12|port=1";
out.kindsFromSpec=[...host().querySelectorAll("#vms-kinds option")].map(o=>o.value+"="+o.textContent).join(",")==="io.input=вход устройства,silent=камера молчит";
out.lastFired=/Последние срабатывания/.test(host().textContent)&&[...host().querySelectorAll("table td")].pop().textContent==="1";
// без det в консоли — действий детекторов нет
const acts=()=>[...host().querySelectorAll('[data-act="akind"] option')].map(o=>o.textContent);
out.noDetWithoutDet=acts().join(",")==="Щёлкнуть реле,Встать в пресет,Записывать";
// правка: порт — PUT без имени, только поля сценария
const port=[...host().querySelectorAll('[data-act="af"]')].find(x=>x.dataset.f==="port");port.value="3";port.dispatchEvent(new w.Event("change"));await b.ready(30);
let n=w.__calls.length;host().querySelector('[data-act="save"]').click();await b.ready(150);
let c=call(n,"PUT","/auto/scenarios/door");
out.editPut=!!c&&!("name" in c.body)&&c.body.then[0].port==="3"&&c.body.when[0].match.port==="1"&&!!c.key;
// новый: пустое поле действия — отказ до отправки, теми же словами
host().querySelector('[data-act="new"]').click();await b.ready(40);
const nm=host().querySelector('[data-act="rf"][data-f="name"]');nm.value="night";nm.dispatchEvent(new w.Event("change"));await b.ready(30);
out.refusedBeforeSending=/не заполнено поле «Устройство»/.test(host().textContent);
n=w.__calls.length;host().querySelector('[data-act="save"]').click();await b.ready(60);
out.notSent=!call(n,"POST","/auto/scenarios");
const ak=host().querySelector('[data-act="akind"]');ak.value="2";ak.dispatchEvent(new w.Event("change"));await b.ready(30);   // «Записывать»
for(const [f,v] of [["cam","1"],["minutes","5"]]){const x=[...host().querySelectorAll('[data-act="af"]')].find(y=>y.dataset.f===f);x.value=v;x.dispatchEvent(new w.Event("change"));await b.ready(20)}
n=w.__calls.length;host().querySelector('[data-act="save"]').click();await b.ready(150);
c=call(n,"POST","/auto/scenarios");
out.newPost=!!c&&c.body.name==="night"&&c.body.when[0].sub==="vms"&&c.body.when[0].kind==="io.input"&&JSON.stringify(c.body.then)==='[{"sub":"rec","action":"record","cam":"1","minutes":"5"}]';
pick("door");await b.ready(60);
n=w.__calls.length;host().querySelector('[data-act="del"]').click();await b.ready(150);
out.deleteAsksFirst=asked.some(q=>/Удалить сценарий «door»/.test(q))&&!!call(n,"DELETE","/auto/scenarios/door");
out.noInlineHandlers=!host().querySelector("[onclick],[onchange],[oninput]");
out.errors=errs;
b.report(out,["errors"]);
// с det в консоли — и действия детекторов
b.FIX["/det/spec"]={name:"det"};
const w2=b.boot();await b.ready(700);await w2.platformConsole.ready;
w2.document.querySelector('.pc-rail [data-s="rules"]').click();await b.ready(200);
w2.document.querySelector('.vms-rules [data-act="pick"][data-id="door"]').click();await b.ready(60);
b.report({detActionsWithDet:[...w2.document.querySelectorAll('.vms-rules [data-act="akind"] option')].map(o=>o.textContent).includes("Искать в архиве")});
try{fs.unlinkSync(TMP)}catch(e){}
process.exit(0);
})();
