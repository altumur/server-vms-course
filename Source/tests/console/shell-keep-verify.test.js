// «Проверить» удержание (ADR-0057 п. 3, ADR-0015): печать проверяет держатель тома инцидентов — у его двери, где лежит
// копия: по записи удержания — дверь из /rec/where/<таблица мест>/<том>?unit=rec/<запись> (жетон места этой записи),
// POST <дверь>/keeps/<имя>/verify?recording=<запись> с Bearer. Кнопка есть, только если
// спека rec открывает маршрут keeps на двери (door.routes); у тома инцидентов без держателя — проверять негде.
// Запись без кадров в отрезке (result: empty) — «нет кадров — запечатывать нечего», не провал. Копия продуктового
// vmsworker/vms/consoletest/shell-keep-verify.test.js (другое здесь — путь страницы).
const fs=require("fs"),path=require("path");
const PAGE=fs.readFileSync(path.join(__dirname,"..","..","vms","vms.shell.html"),"utf8");
const MOD=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"shell-kv-"+process.pid+".html");
fs.writeFileSync(TMP,PAGE.replace(/<script src="\/platform\/console\.js\?v=1"><\/script>/,()=>`<script>${MOD}</script>`));
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
b.FIX["/session"]={open:true};
b.FIX["/spec"]={name:"vms",rows:"cameras",id:"numeric",fields:[{name:"name",type:"string"}]};
b.FIX["/mounts"]={root:"vms",mounts:{rec:{name:"rec",rows:"recordings",id:"name",about:{sub:"vms",field:"cam"},fields:[{name:"cam",type:"string"}],
  places:{table:"volumes"},door:{routes:["timeline","segment","keeps"]}}}};
b.FIX["/cameras"]={configured:[{id:1,name:"ворота"}],rows:[]};
b.FIX["/servers"]={servers:{},policy:{}};
b.FIX["/events"]={events:[],state:"live"};
b.FIX["/rec/volumes"]={volumes:[{name:"inc",server:"box-a",kind:"incidents",url:"file:///i",enabled:true,admits:false,quota_bytes:1e9,held_by:"r-9"}]};
b.FIX["/rec/recordings"]={configured:[{id:"1",cam:"1",retention_days:30,enabled:true}],rows:[]};
b.FIX["/rec/keeps"]={keeps:[{name:"1-100-200",cam:"1",from:100,to:200,note:"улика",recordings:["1","1-b"]}]};
// дверь — жетон места для rec/<запись>: по одному на запись; проверка называет запись (?recording=)
(async()=>{
const w=b.boot();const errs=[];w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
const seen=[];let emptyRun=false;
const J=(status,body)=>Promise.resolve({status,ok:status<300,headers:{get:()=>null},json:()=>Promise.resolve(body),text:()=>Promise.resolve(JSON.stringify(body))});
{const f0=w.fetch;w.fetch=(u,i)=>{const s=String(u);seen.push([s,(i&&i.method)||"GET",((i&&i.headers)||{}).Authorization||""]);
  if(s==="/rec/where/volumes/inc?unit=rec%2F1")return J(200,{door:{url:"http://box-a:9009",token:"T1",expires:Date.now()/1000+300}});
  if(s==="/rec/where/volumes/inc?unit=rec%2F1-b")return J(200,{door:{url:"http://box-a:9009",token:"T2",expires:Date.now()/1000+300}});
  if(s==="http://box-a:9009/keeps/1-100-200/verify?recording=1")return J(200,{keep:"1-100-200",integrity:"ok",ok:true,recordings:{"1":{result:"ok"}}});
  if(s==="http://box-a:9009/keeps/1-100-200/verify?recording=1-b")return J(200,emptyRun?{keep:"1-100-200",integrity:"unknown: 1-b holds no footage in the interval",ok:false,recordings:{"1-b":{result:"empty",detail:"1-b holds no footage in the interval"}}}
    :{keep:"1-100-200",integrity:"broken: block 12 does not match the seal",ok:false,recordings:{"1-b":{result:"damaged"}}});
  return f0(u,i)}}
await b.ready(700);await w.platformConsole.ready;await w.eval("reloadRec()");const d=w.document,pc=w.platformConsole,out={};
const main=()=>d.querySelector("main");
pc.select("unit:vms/1");await b.ready(80);
main().querySelector('.pc-tabs [data-tab="rec"]').click();await b.ready(200);
const btn=re=>[...main().querySelectorAll('[data-tab="rec"].pc-tab button')].find(x=>re.test(x.textContent));
out.verifyOffered=!!btn(/Проверить/);
btn(/Проверить/).click();await b.ready(120);
out.verifyPerRecordingWithItsPlaceToken=seen.some(([u,m,a])=>u==="http://box-a:9009/keeps/1-100-200/verify?recording=1"&&m==="POST"&&a==="Bearer T1")
  &&seen.some(([u,m,a])=>u==="http://box-a:9009/keeps/1-100-200/verify?recording=1-b"&&m==="POST"&&a==="Bearer T2");
out.saidInWords=/Не подтверждено: 1: цело; 1-b: повреждено — block 12 does not match the seal/.test(d.querySelector(".pc-toast").textContent);
// запись без кадров в отрезке (result: empty) — не провал и не ожидание: сказано отдельно
emptyRun=true;btn(/Проверить/).click();await b.ready(120);
out.emptyIsNotAFailure=/^Проверено: 1: цело; в этом отрезке у 1-b нет кадров — запечатывать нечего/.test(d.querySelector(".pc-toast").textContent);
out.errors=errs;out.noErrors=!errs.length;
b.report(out);
try{fs.unlinkSync(TMP)}catch(e){}
process.exit(0);
})();
