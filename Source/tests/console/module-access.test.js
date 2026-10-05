// Права в модуле: люди домена (пароль, отключение, удаление), гранты по кластерам и на домен (дать, убрать),
// аварийный пароль; скоупы словами без предметных слов; данные — текстом.
const fs=require("fs"),path=require("path");
const SRC=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"pc-acc-"+process.pid+".html");
fs.writeFileSync(TMP,`<!doctype html><div id="app"></div><script>${SRC}</script><script>window.pc=PlatformConsole.mount(document.getElementById("app"),{lang:"en"});</script>`);
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
const P=`x"'><img src=x onerror=window.__pwned=1>`;
b.FIX["/session"]={open:true};
b.FIX["/spec"]={name:"testsub",rows:"things",id:"numeric",fields:[{name:"name",type:"string"}]};
b.FIX["/things"]={configured:[],rows:[]};
b.FIX["/servers"]={servers:{},policy:{}};
b.FIX["/domain/users"]={users:[{name:"ann",how:"password",by:"root"},{name:"bob",how:"oidc",disabled:true},{name:P,how:"password"}]};
b.FIX["/domain/grants"]={grants:{domain:[{subject:"ann",cap:"admin",scope:"*"}],"c-1":[{subject:"ann",cap:"view",scope:"unit:7"},{subject:"bob",cap:"edit",scope:"labels:a,b"}]}};
b.FIX["/domain/break-glass"]={clusters:{"c-1":{set_at:1757500000}}};
(async()=>{
const w=b.boot();const errs=[];w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
w.confirm=()=>true;
await b.ready(600);await w.pc.ready;const d=w.document,pc=w.pc,out={};
const main=()=>d.querySelector("main").textContent;
d.querySelector('.pc-rail [data-s="access"]').click();await b.ready(100);
out.treePeopleAndClusters=/ann/.test(d.querySelector(".pc-tree").textContent)&&!!d.querySelector('[data-ref="grants:c-1"]')&&!!d.querySelector('[data-ref="grants:domain"]');
pc.select("person:ann");await b.ready(30);
out.personGrants=/domain · manage · all/.test(main())&&/c-1 · view · one 7/.test(main());
// пароль через диалог
const btn=re=>[...d.querySelectorAll(".pc-main button")].find(x=>re.test(x.textContent));
btn(/^Password$/).click();await b.ready(20);
const dlg=d.querySelector(".pc-dialog");out.dialogOpens=dlg.hidden===false&&dlg.querySelector("input").type==="password";
dlg.querySelector("input").value="0123456789ab";let n=w.__calls.length;
dlg.querySelector("form").dispatchEvent(new w.Event("submit",{cancelable:true}));await b.ready(80);
out.passwordPut=w.__calls.slice(n).some(x=>x.method==="PUT"&&x.path==="/domain/users/ann"&&x.body.password==="0123456789ab")&&dlg.hidden===true;
pc.select("person:bob");await b.ready(30);
out.oidcNoPassword=!btn(/^Password$/)&&/organisation/.test(main())&&/disabled/.test(main());
n=w.__calls.length;btn(/^Enable$/).click();await b.ready(80);
out.enablePut=w.__calls.slice(n).some(x=>x.path==="/domain/users/bob"&&x.body.disabled===false);
// гранты кластера
pc.select("grants:c-1");await b.ready(30);
out.labelsScope=/bob · act · with labels a,b/.test(main())&&/break-glass password set/.test(main());
n=w.__calls.length;d.querySelector("[data-rev='0']").click();await b.ready(80);
let c=w.__calls.slice(n).find(x=>x.path==="/domain/grants/c-1");
out.revokeLeavesOthers=!!c&&c.body.lines.length===1&&c.body.lines[0].subject==="bob";
pc.select("grants:c-1");await b.ready(30);
btn(/^Grant$/).click();await b.ready(20);
const f=d.querySelector(".pc-dialog form");f.elements.subject.value="ann";f.elements.cap.value="edit";f.elements.scope.value="labels:x";
n=w.__calls.length;f.dispatchEvent(new w.Event("submit",{cancelable:true}));await b.ready(80);
c=w.__calls.slice(n).find(x=>x.path==="/domain/grants/c-1");
out.grantAppends=!!c&&c.body.lines.length===3&&JSON.stringify(c.body.lines[2])==='{"subject":"ann","cap":"edit","scope":"labels:x"}';
pc.select("grants:c-1");await b.ready(30);
btn(/Break-glass/).click();await b.ready(20);
d.querySelector(".pc-dialog input").value="0123456789abcd";n=w.__calls.length;
d.querySelector(".pc-dialog form").dispatchEvent(new w.Event("submit",{cancelable:true}));await b.ready(80);
out.glassPut=w.__calls.slice(n).some(x=>x.method==="PUT"&&x.path==="/domain/break-glass/c-1");
// отмена диалога ничего не шлёт
pc.select("person:ann");await b.ready(30);btn(/^Password$/).click();await b.ready(20);
n=w.__calls.length;d.querySelector(".pc-dialog-no").click();await b.ready(40);
out.cancelSendsNothing=w.__calls.length===n;
pc.select("grants:domain");await b.ready(30);
out.domainNoGlass=!btn(/Break-glass/);
pc.select("person:"+P);await b.ready(30);
out.neverRan=w.__pwned===undefined&&!d.querySelector("img");
out.errors=errs;
b.report(out,["errors"]);
try{fs.unlinkSync(TMP)}catch(e){}
process.exit(0);
})();
