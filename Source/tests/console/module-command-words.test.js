// Виды command и command.failed — платформенные (семейство просьб базы воркера, ADR-0013): слово и заметку даёт модуль,
// спека их не называет. Заметка по outcome: performed, refused: <почему>, expired, unknown; без outcome — ошибка;
// late — ответ устройства пришёл после срока.
const fs=require("fs"),path=require("path");
const PAGE=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.html"),"utf8");
const MOD=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"pc-cmd-"+process.pid+".html");
fs.writeFileSync(TMP,PAGE.replace(/<script src="\/platform\/console\.js\?v=1"><\/script>/,()=>`<script>${MOD}</script>`)
  .replace('PlatformConsole.mount(document.getElementById("app"))','PlatformConsole.mount(document.getElementById("app"), { lang: "ru", poll_s: 0 })'));
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
b.FIX["/session"]={open:true};
b.FIX["/spec"]={name:"testsub",rows:"things",id:"numeric",fields:[{name:"name",type:"string"}]};
b.FIX["/things"]={configured:[{id:1,name:"a"}],rows:[]};
b.FIX["/events"]={events:[
  {t:5,kind:"command",unit:"testsub/1",action:"preset",outcome:"performed",by:"ann"},
  {t:4,kind:"command.failed",unit:"testsub/1",action:"output",outcome:"refused: the device said no",by:"bob"},
  {t:3,kind:"command.failed",unit:"testsub/1",action:"preset",outcome:"expired"},
  {t:2,kind:"command.failed",unit:"testsub/1",action:"preset",outcome:"unknown"},
  {t:1,kind:"command.failed",unit:"testsub/1",action:"reboot",error:"no answer"},
  {t:6,kind:"command",unit:"testsub/1",action:"zoom",outcome:"performed",late:true,by:"cid"}]};
(async()=>{
  const w=b.boot();const errs=[];w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
  await b.ready(400);await w.platformConsole.ready;const d=w.document;
  d.querySelector('.pc-rail [data-s="journal"]').click();await b.ready(150);
  const li=[...d.querySelectorAll(".pc-evlist li")].map(x=>x.textContent.replace(/\s+/g," "));
  const at=re=>li.find(x=>re.test(x))||"";
  const out={
    performed:/команда выполнена/.test(at(/preset · выполнена/))&&/preset · выполнена · кто: ann/.test(at(/preset · выполнена/)),
    refusedWithWhy:/команда не выполнена/.test(at(/output/))&&/output · отказ: the device said no · кто: bob/.test(at(/output/)),
    expired:/истекла: никто не выполнил вовремя/.test(at(/истекла/)),
    unknown:/неизвестно, выполнена ли/.test(at(/неизвестно/)),
    lateAfterTheDeadline:/zoom · выполнена поздно: после срока · кто: cid/.test(at(/zoom/)),
    noOutcomeSaysTheError:/reboot · no answer/.test(at(/reboot/)),
    errors:errs};
  out.noErrors=!errs.length;
  b.report(out);
  try{fs.unlinkSync(TMP)}catch(e){}
  process.exit(0);
})();
