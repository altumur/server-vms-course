// Слив сервера: у доли подсистемы — сколько единиц осталось и сколько не сохранено (pending_writes); воркеры, которые
// не сказали в биении, сколько держат несохранённого (pending_unsaid), названы: пока они есть, слив не безопасен.
const fs=require("fs"),path=require("path");
const PAGE=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.html"),"utf8");
const MOD=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"pc-drain-"+process.pid+".html");
fs.writeFileSync(TMP,PAGE.replace(/<script src="\/platform\/console\.js\?v=1"><\/script>/,()=>`<script>${MOD}</script>`)
  .replace('PlatformConsole.mount(document.getElementById("app"))','PlatformConsole.mount(document.getElementById("app"), { lang: "ru", poll_s: 0 })'));
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
const P=`x"'><img src=x onerror=window.__pwned=1>`;
b.FIX["/session"]={open:true};
b.FIX["/spec"]={name:"testsub",rows:"things",id:"numeric",fields:[{name:"name",type:"string"}]};
b.FIX["/things"]={configured:[],rows:[]};
b.FIX["/servers"]={servers:{"s-1":{resource:"live",workers:[{worker:"w-1",load:1,capacity:5,state:"live"}]}},policy:{}};
b.FIX["/drain"]={draining:"s-1",safe:false,subsystems:{testsub:{subsystem:"testsub",draining:true,units:2,pending_writes:3,pending_unsaid:["w-1",P]}}};
(async()=>{
  const w=b.boot();const errs=[];w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
  await b.ready(400);const pc=w.platformConsole;await pc.ready;const d=w.document,out={};
  pc.select("server:s-1");await b.ready(80);
  const t=d.querySelector(".pc-main").textContent;
  out.partSaysUnitsAndUnsaved=/testsub: осталось единиц 2 · не сохранено 3/.test(t);
  out.unsaidNamedNotSafe=/не сказали, сколько у них несохранённого: w-1, /.test(t)&&/слив не безопасен/.test(t);
  out.neverRan=w.__pwned===undefined&&!d.querySelector(".pc-main img");
  out.errors=errs;out.noErrors=!errs.length;
  b.report(out);
  try{fs.unlinkSync(TMP)}catch(e){}
  process.exit(0);
})();
