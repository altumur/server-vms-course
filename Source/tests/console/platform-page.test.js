// Платформенная страница (w2cplatform/console.html) — модуль и mount, больше ничего (контракт модуля, §10):
// в ней нет своего скрипта, кроме подключения модуля, нет слов и маршрутов подсистем; со страницей работает всё
// платформенное: единицы из /manifest, правка без маски, события, отметка; данные — текстом.
const fs=require("fs"),path=require("path");
const PAGE=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.html"),"utf8");
const MOD=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"pc-page-"+process.pid+".html");
// jsdom не грузит внешние скрипты: модуль подставляется на место своего <script src>
fs.writeFileSync(TMP,PAGE.replace(/<script src="\/platform\/console\.js\?v=1"><\/script>/,()=>`<script>${MOD}</script>`));
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
const P=`x"'><img src=x onerror=window.__pwned=1>`;
b.FIX["/session"]={open:true};
b.FIX["/manifest"]={name:"testsub",rows:"things",id:"numeric",fields:[{name:"name",type:"string"},{name:"enabled",type:"bool"},{name:"key_secret",type:"string"}],metrics:{}};
b.FIX["/things"]={configured:[{id:1,name:P,enabled:true,key_secret:"***"}],rows:[{id:1,worker:P,server:P,phase:"running"}]};
b.FIX["/events"]={events:[{t:100,kind:P,subsystem:P,unit:"1",server:P,note:P}],state:"live"};
b.FIX["/servers"]={servers:{[P]:{workers:[{worker:P,load:1,capacity:2,state:"live"}],resource:"live",placeable:false,why:P}},policy:{}};
(async()=>{
const out={};
// страница: подключение модуля и mount, ничего своего
const scripts=[...PAGE.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/g)];
out.onlyModuleAndMount=scripts.length===2&&/src="\/platform\/console\.js\?v=1"/.test(scripts[0][1])&&/window\.platformConsole = PlatformConsole\.mount\(app\);/.test(scripts[1][2]);
// version: страница сверяет версию модуля до его использования (P/07 Н1.5 version) — модуль другой версии не монтируется
out.versionCheckedFirst=/if \(PlatformConsole\.version === 1\) window\.platformConsole = PlatformConsole\.mount\(app\);/.test(scripts[1][2]);
{const {JSDOM}=require("jsdom");const v2=new JSDOM(PAGE.replace(/<script src="\/platform\/console\.js\?v=1"><\/script>/,()=>`<script>${MOD.replace("const VERSION = 1;","const VERSION = 2;")}</script>`),{runScripts:"dangerously",url:"http://localhost/",beforeParse(x){x.fetch=()=>{x.__fetched=true;return new Promise(()=>{})}}}).window;
 out.otherVersionNotMounted=!v2.platformConsole&&/version 2, this page needs 1/.test(v2.document.getElementById("app").textContent)&&!v2.__fetched;v2.close();}
const bad=["camera","камер","архив","видео","footage","recording","recorder","detector","whep","/timeline","/segment","/rec/","/det/","/auto/","<video","RTCPeerConnection","fetch("]
  .filter(x=>PAGE.toLowerCase().includes(x.toLowerCase()));
out.noSubsystemWords=bad.length===0;out.found=bad.join(",");
const w=b.boot();const errs=[];const asked=[];w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
const f0=w.fetch;w.fetch=(u,i)=>{asked.push(String(u));return f0(u,i)};
await b.ready(600);await w.platformConsole.ready;const d=w.document,pc=w.platformConsole;
out.mounted=pc.version===1&&!!d.querySelector(".pc-tree [data-ref='unit:testsub/1']");
pc.select("unit:testsub/1");await b.ready(150);
const f=d.querySelector(".pc-edit");
out.secretEmptyNoMask=f.elements.key_secret.value===""&&f.elements.key_secret.type==="password";
f.elements.name.value="renamed";let n=w.__calls.length;f.dispatchEvent(new w.Event("submit",{cancelable:true}));await b.ready(100);
const c=w.__calls.slice(n).find(x=>x.method==="PUT");
out.onlyChangedNoMask=!!c&&c.body.name==="renamed"&&!JSON.stringify(c.body).includes("***");
d.querySelector('main .pc-tabs [data-tab="events"]').click();await b.ready(150);
out.eventsByUnit=asked.some(u=>/^\/events\?.*unit=testsub%2F1/.test(u))&&!asked.some(u=>/[?&]cam=/.test(u));
out.eventsShown=d.querySelectorAll(".pc-main .pc-evlist li").length===1;
const m=d.querySelector(".pc-mark");m.elements.note.value="saw it";n=w.__calls.length;m.dispatchEvent(new w.Event("submit",{cancelable:true}));await b.ready(80);
out.markSent=w.__calls.slice(n).some(x=>x.path==="/marks"&&x.body.note==="saw it"&&x.body.unit==="testsub/1"&&!("cam" in x.body));
(d.querySelector('.pc-rail [data-s="units"]').click(),d.querySelector('.pc-layout').click(),d.querySelector('[data-layout="servers"]').click());await b.ready(30);
out.neverRan=w.__pwned===undefined&&!d.querySelector("img");
out.errors=errs;
b.report(out,["errors","found"]);
try{fs.unlinkSync(TMP)}catch(e){}
process.exit(0);
})();
