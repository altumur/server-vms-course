// Тома на странице VMS курса — строки таблицы мест, которую называет спека rec (places.table): под сервером его тома,
// сетевые — отдельным узлом «Сетевые архивы» на верхнем уровне; карточка тома — вид, путь, квота, кто обслуживает
// (held_by: объявлен и обслуживается — разные вещи), записи в нём; объявить (POST /rec/<таблица>, строка целиком),
// меньшая квота — только после подтверждения и с shrink_confirmed, равным ей; отозвать (DELETE) после подтверждения.
// Пропавший каталог тома — слово регистратора (volume_missing в его строке /rec/servers; корневой /servers знает только
// своих воркеров): в блоке «Архивы сервера» его сервера, имя — путь к карточке тома.
const fs=require("fs"),path=require("path");
const PAGE=fs.readFileSync(path.join(__dirname,"..","..","vms","vms.shell.html"),"utf8");
const MOD=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"shell-vol-"+process.pid+".html");
fs.writeFileSync(TMP,PAGE.replace(/<script src="\/platform\/console\.js\?v=1"><\/script>/,()=>`<script>${MOD}</script>`));
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
const G=1073741824;
b.FIX["/session"]={open:true};
b.FIX["/spec"]={name:"vms",rows:"cameras",id:"numeric",fields:[{name:"name",type:"string"}]};
b.FIX["/mounts"]={root:"vms",mounts:{rec:{name:"rec",rows:"recordings",id:"name",about:{sub:"vms",field:"cam"},places:{table:"volumes"},fields:[{name:"cam",type:"string"}]}}};
b.FIX["/cameras"]={configured:[{id:1,name:"ворота"}],rows:[]};
b.FIX["/rec/recordings"]={configured:[{id:"1",cam:"1",home:"disk-a",retention_days:30}],rows:[]};
b.FIX["/rec/volumes"]={volumes:[{name:"disk-a",server:"box-a",kind:"local",url:"file:///a",quota_bytes:100*G,enabled:true,held_by:"r-1"},
  {name:"cold",server:"box-a",kind:"backup",url:"file:///c",quota_bytes:50*G,enabled:true},{name:"nas",kind:"network",url:"s3://bucket/vms",quota_bytes:1000*G,enabled:true,access_key:"AK1",access_secret:"***"}]};
b.FIX["/rec/keeps"]={keeps:[]};
b.FIX["/servers"]={servers:{"box-a":{resource:"live",workers:[{worker:"w-1",capacity:5,load:1,state:"live",status:{volume_missing:"root-says"}}]}},policy:{}};
b.FIX["/rec/servers"]={servers:{"box-a":{resource:"live",workers:[{worker:"r-1",capacity:1,load:1,state:"live",status:{volume_missing:"cold"}}]},
  "box-b":{resource:"live",workers:[{worker:"r-9",capacity:1,load:1,state:"live",status:{volume_missing:"far"}}]}},policy:{}};
b.FIX["/events"]={events:[],state:"live"};
(async()=>{
const w=b.boot();const errs=[];w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
let asked=[],answer=true;w.confirm=q=>{asked.push(q);return answer};
await b.ready(700);await w.platformConsole.ready;await w.eval("reloadRec()");await b.ready(60);
const d=w.document,pc=w.platformConsole,out={};
const main=()=>d.querySelector("main"),txt=()=>main().textContent+" "+[...main().querySelectorAll("input")].map(x=>x.value).join(" | ");
const call=(n,m,p)=>w.__calls.slice(n).find(x=>x.method===m&&x.path===p);
const f=()=>d.querySelector(".pc-dialog-f"),ok=async()=>{f().dispatchEvent(new w.Event("submit",{cancelable:true}));await b.ready(120)};
(d.querySelector('.pc-rail [data-s="units"]').click(),d.querySelector('.pc-layout').click(),d.querySelector('[data-layout="servers"]').click());await b.ready(40);
for(let i=0;i<3;i++)d.querySelectorAll(".pc-tree [data-tw]").forEach(t=>{if(t.textContent==="▸")t.click()});
const node=r=>d.querySelector(`.pc-tree .n[data-ref="${r}"]`);
out.underServer=!!node("vol:disk-a")&&!!node("vol:cold")&&/резервный/.test(node("vol:cold").textContent);
out.networkApart=!!node("netvols")&&!!node("vol:nas")&&/сетевой/.test(node("vol:nas").textContent);
pc.select("vol:disk-a");await b.ready(60);
out.volumeCard=/Обслуживается: r-1/.test(txt())&&/file:\/\/\/a/.test(txt())&&/100\.0 ГБ/.test(txt())&&/запись «1»/.test(txt());
pc.select("vol:cold");await b.ready(60);
out.unservedSaid=/Никто не обслуживает/.test(txt());
pc.select("netvols");await b.ready(60);
out.netCard=/Сетевые архивы/.test(txt())&&/s3:\/\/bucket\/vms/.test(txt());
// объявить сетевой: строка целиком, ключ — только если вписан
main().querySelector('[data-act="add"]').click();await b.ready(40);
out.secretIsPassword=f().elements.access_secret.type==="password"&&f().elements.access_secret.value==="";
f().elements.name.value="nas2";f().elements.url.value="s3://other/vms";f().elements.quota.value="200";f().elements.access_secret.value="S3CR3T";
let n=w.__calls.length;await ok();
let c=call(n,"POST","/rec/volumes");
out.declared=!!c&&JSON.stringify(c.body)===JSON.stringify({name:"nas2",kind:"network",url:"s3://other/vms",quota_bytes:200*G,access_secret:"S3CR3T"})&&!!c.key;
// меньшая квота у тома, который есть: спросить; «нет» — ничего; «да» — shrink_confirmed, равный ей
pc.select("vol:disk-a");await b.ready(60);
main().querySelector('[data-act="redeclare"]').click();await b.ready(40);
out.redeclareFilled=f().elements.name.value==="disk-a"&&f().elements.server.value==="box-a"&&f().elements.quota.value==="100";
f().elements.quota.value="40";answer=false;n=w.__calls.length;await ok();
out.shrinkAsked=asked.some(q=>/Уменьшить том «disk-a» с 100\.0 ГБ до 40\.0 ГБ/.test(q))&&!call(n,"POST","/rec/volumes");
main().querySelector('[data-act="redeclare"]').click();await b.ready(40);
f().elements.quota.value="40";answer=true;n=w.__calls.length;await ok();
c=call(n,"POST","/rec/volumes");
out.shrinkConfirmed=!!c&&c.body.quota_bytes===40*G&&c.body.shrink_confirmed===40*G&&c.body.server==="box-a"&&c.body.kind==="local";
// отозвать: после подтверждения, сказано, что записи уедут, а видео не стирается
pc.select("vol:disk-a");await b.ready(60);
asked=[];n=w.__calls.length;main().querySelector('[data-act="withdraw"]').click();await b.ready(100);
out.withdrawn=asked.some(q=>/Отозвать объявление тома «disk-a»/.test(q)&&/Записей, выбравших этот том: 1/.test(q))&&!!call(n,"DELETE","/rec/volumes/disk-a");
// «＋ Архив» сервера — объявление на этом сервере
pc.select("server:box-a");await b.ready(60);
main().querySelector('.pc-block[data-block="vols"] [data-act="add"]').click();await b.ready(40);
out.serverAddPrefilled=f().elements.server.value==="box-a"&&[...f().elements.kind.options].map(o=>o.value).join(",")==="local,backup,incidents";
d.querySelector(".pc-dialog-no").click();
const blk=()=>main().querySelector('.pc-block[data-block="vols"]');
out.missingSaid=/Пропал каталог тома: cold\. Записи ушли на другие тома/.test(blk().textContent)&&!/root-says|far/.test(blk().textContent);
blk().querySelector('a[data-vol="cold"]').click();await b.ready(60);
out.missingLeadsToCard=pc.selected()==="vol:cold";
out.errors=errs;
b.report(out,["errors"]);
try{fs.unlinkSync(TMP)}catch(e){}
process.exit(0);
})();
