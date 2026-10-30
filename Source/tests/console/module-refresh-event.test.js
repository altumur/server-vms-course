// Событие refresh (P/07 Н1.5 events, Н1.6 events): после каждого опроса страница получает on("refresh", {units,
// servers, domain}) — то, что модуль прочитал (domain — вид /domain, поле позднего слоя); раздел access, прочитав свои
// двери (/domain/users, /domain/grants, /domain/break-glass), испускает refresh {access}. Аудит покрытия P/07 (90661897f).
const fs=require("fs"),path=require("path");
const SRC=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"pc-refresh-"+process.pid+".html");
fs.writeFileSync(TMP,`<!doctype html><div id="app"></div><script>${SRC}</script><script>window.pc=PlatformConsole.mount(document.getElementById("app"),{lang:"en",poll_s:0.3});</script>`);
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
b.FIX["/session"]={open:true};
b.FIX["/manifest"]={name:"testsub",rows:"things",id:"numeric",fields:[{name:"name",type:"string"}]};
b.FIX["/things"]={configured:[{id:1,name:"one"}],rows:[{id:1,worker:"w-1",server:"s-1",phase:"running"}]};
b.FIX["/servers"]={servers:{"s-1":{resource:"live",workers:[{worker:"w-1",load:1,capacity:5,state:"live"}]}},policy:{}};
b.FIX["/domain"]={holder:"hold",members:[{name:"hold",holder:true,state:"ok"}],units:{}};
b.FIX["/domain/users"]={users:[{name:"ann",how:"password"}]};
b.FIX["/domain/grants"]={grants:{domain:[{subject:"ann",cap:"admin",scope:"*"}]}};
b.FIX["/domain/break-glass"]={clusters:{}};
(async()=>{
const w=b.boot();const errs=[];w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
// подписка до первого опроса: модуль монтируется синхронно, читает асинхронно
const got=[];w.pc.on("refresh",d=>got.push(d));
await w.pc.ready;await b.ready(100);const d=w.document,out={};
const keys=x=>Object.keys(x||{}).sort().join(",");
const poll=got.filter(x=>keys(x)==="domain,servers,units");
// после опроса: {units, servers, domain} — что пришло
out.refreshAfterMount=poll.length>=1;
const first=poll[0]||{};
out.refreshUnits=Array.isArray((first.units||{}).testsub)&&first.units.testsub.some(u=>u.id===1&&u.name==="one");
out.refreshServers=!!(first.servers||{})["s-1"]&&first.servers["s-1"].resource==="live";
out.refreshDomain=!!first.domain&&first.domain.holder==="hold";
// следующий опрос с изменёнными данными: событие снова, в нём новое
const n=poll.length;
b.FIX["/things"]={configured:[{id:1,name:"one"},{id:2,name:"two"}],rows:[{id:1,worker:"w-1",server:"s-1",phase:"running"}]};
await b.ready(800);
const later=got.filter(x=>keys(x)==="domain,servers,units");
out.refreshEveryPoll=later.length>n;
out.refreshNewData=later.length>n&&later[later.length-1].units.testsub.some(u=>u.id===2&&u.name==="two");
// раздел access, прочитав свои двери, — refresh {access}
const m=got.length;
d.querySelector('.pc-rail [data-s="access"]').click();await b.ready(200);
const acc=got.slice(m).filter(x=>"access" in (x||{}));
out.accessRefresh=acc.length>=1;
out.accessRefreshShape=acc.length>=1&&keys(acc[0])==="access";
out.accessRefreshData=acc.length>=1&&!!acc[0].access&&(acc[0].access.users||[]).some(u=>u.name==="ann")&&!!(acc[0].access.grants||{}).domain;
out.accessAfterItsDoors=acc.length>=1&&["/domain/users","/domain/grants","/domain/break-glass"].every(p=>w.__log.some(x=>x.url===p));
w.close();
out.errors=errs;
b.report(out,["errors"]);
try{fs.unlinkSync(TMP)}catch(e){}
process.exit(0);
})();
