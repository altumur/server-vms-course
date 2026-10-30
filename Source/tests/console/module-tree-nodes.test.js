// Узлы оболочки в дереве модуля — addTreeNodes(kind | servers | server, fn) (P/07 Н1.5 adds, Н1.6 adds): все пять видов
// (unit — под единицей, servers — верхний уровень дерева серверов, server — под сервером, member — под членом домена,
// access — в разделе прав) и поля узла {ref, label, icon, count, kids, badge, tags, dot, title, off, open, after,
// replaces}; after и replaces — у члена домена (after — за членами за ретранслятором, replaces — на месте строки члена).
// Выбор узла оболочки приходит в on("select"). Аудит покрытия P/07 (90661897f).
const fs=require("fs"),path=require("path");
const SRC=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"pc-nodes-"+process.pid+".html");
fs.writeFileSync(TMP,`<!doctype html><div id="app"></div><script>${SRC}</script><script>window.pc=PlatformConsole.mount(document.getElementById("app"),{lang:"en"});</script>`);
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
const P=`x"'><img src=x onerror=window.__pwned=1>`;
b.FIX["/session"]={open:true};
b.FIX["/manifest"]={name:"testsub",rows:"things",id:"numeric",fields:[{name:"name",type:"string"}]};
b.FIX["/things"]={configured:[{id:1,name:"one"},{id:2,name:"two"}],rows:[{id:1,worker:"w-1",server:"s-1",phase:"running"},{id:2,worker:"w-1",server:"s-1",phase:"running"}]};
b.FIX["/servers"]={servers:{"s-1":{resource:"live",workers:[{worker:"w-1",load:2,capacity:5,state:"live"}]}},policy:{}};
// члены домена: m-2 — за ретранслятором m-1 (topology.via), m-3 не в порядке
b.FIX["/domain"]={holder:"hold",members:[{name:"hold",holder:true,state:"ok"},{name:"m-1",state:"ok"},{name:"m-2",state:"ok"},{name:"m-3",state:"down"}],topology:{via:{"m-2":"m-1"}},units:{}};
b.FIX["/domain/users"]={users:[{name:"ann",how:"password"}]};
b.FIX["/domain/grants"]={grants:{}};
b.FIX["/domain/break-glass"]={clusters:{}};
(async()=>{
const w=b.boot();const errs=[];w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
const pc=w.pc,args={};
// вызовы оболочки — до первого опроса
pc.addTreeNodes("unit",(ref,u)=>{args.unit=[ref,u&&u.name];return ref==="unit:testsub/1"?[{ref:"x:u1",label:"under one",icon:"folder",count:3,badge:"B",tags:["t1",{text:"t2",title:"tt"}],dot:["red","bad"],title:"hint",off:true}]:[]});
pc.addTreeNodes("servers",()=>[{ref:"x:top",label:"Top",kids:[{ref:"x:kid",label:"Kid"}]},{ref:"x:open",label:"Opened",open:true,kids:[{ref:"x:okid",label:P}]}]);
pc.addTreeNodes("server",(ref,s)=>{args.server=[ref,s&&s.resource];return ref==="server:s-1"?[{ref:"x:vol",label:"Vol"}]:[]});
pc.addTreeNodes("member",(ref,m)=>{(args.member=args.member||[]).push([ref,m&&m.name]);
  return ref==="member:m-1"?[{ref:"x:m1-before",label:"Before"},{ref:"x:m1-after",label:"After",after:true}]:ref==="member:m-3"?[{ref:"x:m3-stand",label:"Stand",replaces:true}]:[]});
pc.addTreeNodes("access",()=>[{ref:"x:acct",label:"Accounts",icon:"user"}]);
let sel=null;pc.on("select",r=>{sel=r});
await pc.ready;await b.ready(150);const d=w.document,out={};
const tree=()=>d.querySelector(".pc-tree");
const row=r=>tree().querySelector(`.n[data-ref="${r}"]`);
const refs=()=>[...tree().querySelectorAll(".n[data-ref]")].map(x=>x.dataset.ref);
const pad=r=>parseInt((row(r)||{style:{}}).style.paddingLeft||"0",10);
const tw=r=>tree().querySelector(`[data-tw="${r}"]`);
// --- unit: узел под единицей, все поля строки
out.unitHasTwisty=!!tw("unit:testsub/1")&&!row("x:u1");
tw("unit:testsub/1").click();
const u1=row("x:u1");
out.unitNodeUnder=!!u1&&refs().indexOf("x:u1")===refs().indexOf("unit:testsub/1")+1&&pad("x:u1")>pad("unit:testsub/1");
out.unitFnArgs=!!args.unit&&args.unit[0].startsWith("unit:testsub/")&&typeof args.unit[1]==="string";
out.fieldLabel=!!u1&&u1.querySelector(".nm").textContent==="under one";
out.fieldIcon=!!u1&&!!u1.querySelector(".ici.ici-folder svg");
out.fieldCount=!!u1&&u1.querySelector(".cnt").textContent==="3";
out.fieldBadgeTags=!!u1&&[...u1.querySelectorAll(".n-tags .tag")].map(x=>x.textContent).join("|")==="B|t1|t2"&&u1.querySelectorAll(".n-tags .tag")[2].title==="tt";
out.fieldDot=!!u1&&!!u1.querySelector(".dot")&&u1.querySelector(".dot").title==="bad"&&u1.querySelector(".dot").style.background==="red";
out.fieldTitle=!!u1&&u1.title==="hint";
out.fieldOff=!!u1&&u1.classList.contains("off");
out.noKidsNoTwisty=!!u1&&!u1.querySelector("[data-tw]");
// --- servers и server: дерево серверов (корень — домен)
d.querySelector('.pc-rail [data-s="units"]').click();d.querySelector(".pc-layout").click();d.querySelector('[data-layout="servers"]').click();await b.ready(50);
out.serversTopLevel=!!row("x:top")&&!!row("x:open")&&pad("x:top")===pad("server:s-1");
// kids: свёрнуты, пока не раскрыли; open — раскрыт, пока не свернули
out.fieldKidsFolded=!!tw("x:top")&&!row("x:kid");
tw("x:top").click();
out.fieldKidsOpen=!!row("x:kid")&&refs().indexOf("x:kid")===refs().indexOf("x:top")+1&&pad("x:kid")>pad("x:top");
out.fieldOpen=!!row("x:okid")&&row("x:okid").querySelector(".nm").textContent===P;
tw("x:open").click();
out.fieldOpenFolds=!row("x:okid")&&!!row("x:open");
out.serverNodeFolded=!row("x:vol");
tw("server:s-1").click();
const sr=refs();
out.serverNodeUnder=!!row("x:vol")&&sr.indexOf("x:vol")>sr.indexOf("server:s-1")&&pad("x:vol")>pad("server:s-1")
  &&sr.slice(sr.indexOf("server:s-1")+1,sr.indexOf("x:vol")).every(r=>pad(r)>pad("server:s-1"));
out.serverFnArgs=!!args.server&&args.server[0]==="server:s-1"&&args.server[1]==="live";
// --- member: before — под членом, за ним члены за ретранслятором, after — после них; replaces — на месте строки члена
out.memberFnArgs=(args.member||[]).some(([r,n])=>r==="member:m-1"&&n==="m-1");
out.memberFolded=!!row("member:m-1")&&!row("x:m1-before");
tw("member:m-1").click();
const mr=refs(),iB=mr.indexOf("x:m1-before"),iM2=mr.indexOf("member:m-2"),iA=mr.indexOf("x:m1-after");
out.memberNodesUnder=iB>mr.indexOf("member:m-1")&&pad("x:m1-before")>pad("member:m-1")&&pad("x:m1-after")>pad("member:m-1");
out.fieldAfter=iB>=0&&iM2>iB&&iA>iM2;
out.fieldReplaces=!row("member:m-3")&&!!row("x:m3-stand")&&pad("x:m3-stand")===pad("member:m-1");
out.replacesOffWhenMemberNotOk=!!row("x:m3-stand")&&row("x:m3-stand").classList.contains("off");
// выбор узла оболочки — в on("select")
row("x:vol").click();
out.selectShellNode=sel==="x:vol"&&pc.selected()==="x:vol";
// --- access: узлы оболочки в разделе прав
d.querySelector('.pc-rail [data-s="access"]').click();await b.ready(150);
out.accessNode=!!row("x:acct")&&!!row("x:acct").querySelector(".ici-user svg")&&refs().indexOf("x:acct")>refs().indexOf("person:ann");
out.neverRan=w.__pwned===undefined&&!d.querySelector("img");
w.close();
out.errors=errs;
b.report(out,["errors"]);
try{fs.unlinkSync(TMP)}catch(e){}
process.exit(0);
})();
