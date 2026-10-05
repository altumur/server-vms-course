// Отладочный вход (ADR-0050): дверь впустила без пароля — /session говорит debug: true. Модуль показывает это в шапке
// красной меткой, пока так, и не предлагает «Выйти»; без debug метки нет. Вид session.debug_open — словом модуля.
const fs=require("fs"),path=require("path");
const PAGE=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.html"),"utf8");
const MOD=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"pc-debug-"+process.pid+".html");
fs.writeFileSync(TMP,PAGE.replace(/<script src="\/platform\/console\.js\?v=1"><\/script>/,()=>`<script>${MOD}</script>`)
  .replace('PlatformConsole.mount(document.getElementById("app"))','PlatformConsole.mount(document.getElementById("app"), { lang: "ru", poll_s: 0 })'));
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
async function run(session){
  for(const k of Object.keys(b.FIX))delete b.FIX[k];
  b.FIX["/session"]=session;
  b.FIX["/spec"]={name:"testsub",rows:"things",id:"numeric",fields:[{name:"name",type:"string"}]};
  b.FIX["/things"]={configured:[{id:1,name:"a"}],rows:[]};
  b.FIX["/events"]={events:[{t:100,kind:"session.debug_open",person:"stand-admin"}]};
  const w=b.boot();const errs=[];w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
  await b.ready(400);await w.platformConsole.ready;
  const d=w.document,badge=d.querySelector(".pc-debug"),out_={};
  out_.badge=!!badge&&!badge.hidden;out_.text=badge?badge.textContent:"";
  out_.logout=d.querySelector(".pc-logout").style.display;
  d.querySelector('.pc-rail [data-s="journal"]').click();await b.ready(150);
  out_.journal=(d.querySelector(".pc-evlist")||{}).textContent||"";
  out_.errs=errs;w.close();return out_;
}
(async()=>{
  const on=await run({open:false,user:"stand-admin",debug:true,grants:[{cap:"admin",scope:"*"}]});
  const off=await run({open:false,user:"stand-admin",grants:[{cap:"admin",scope:"*"}]});
  const out={
    debugBadgeShown:on.badge&&on.text==="отладка: вход без пароля",
    noSignOutWhileDebug:on.logout==="none",
    noBadgeWithoutDebug:!off.badge&&off.logout==="block",
    kindInModulesWords:/отладочный вход без пароля включён/.test(on.journal)&&/как stand-admin/.test(on.journal),
    errors:[...on.errs,...off.errs]};
  out.noErrors=out.errors.length===0;
  b.report(out);
  try{fs.unlinkSync(TMP)}catch(e){}
  process.exit(0);
})();
