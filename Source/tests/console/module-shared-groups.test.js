// Группы из общих настроек домена (курс ведёт, продукт переносит: группы читает сам модуль). Поле group_by, которое
// спека делит с доменом (domain.shared), — модуль сам читает /domain/shared/<sub>: группы домена стоят в дереве и без
// единиц, их предлагает форма, карточка группы говорит, откуда она. Спека, которая поле не делит, туда не ходит.
const fs=require("fs"),path=require("path");
const SRC=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"pc-shared-"+process.pid+".html");
fs.writeFileSync(TMP,`<!doctype html><div id="app"></div><script>${SRC}</script><script>window.pc=PlatformConsole.mount(document.getElementById("app"),{lang:"en"});</script>`);
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
const P=`x"'><img src=x onerror=window.__pwned=1>`;
b.FIX["/session"]={open:true};
b.FIX["/spec"]={name:"testsub",rows:"things",id:"numeric",fields:[{name:"name",type:"string"},{name:"folders",type:"list"}],
  display:{tree:{group_by:"folders",nested_by:"/"}},domain:{keys:[],shared:["folders"]}};
b.FIX["/mounts"]={root:"testsub",mounts:{sub:{name:"other",rows:"parts",id:"name",fields:[{name:"tags",type:"list"}],display:{tree:{group_by:"tags"}}}}};
b.FIX["/things"]={configured:[{id:1,name:"gate",folders:["Yard"]}],rows:[]};
b.FIX["/sub/parts"]={configured:[],rows:[]};
b.FIX["/domain/shared/testsub"]={sub:"testsub",rev:7,fields:{folders:{groups:["Site/Hall",P],from:"domain rev 7"}}};
b.FIX["/servers"]={servers:{},policy:{}};
b.FIX["/events"]={events:[],state:"live"};
(async()=>{
const w=b.boot();const errs=[];w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
const asked=[];const f0=w.fetch;w.fetch=(u,i)=>{asked.push(String(u).split("?")[0]);return f0(u,i)};
await b.ready(600);await w.pc.ready;const d=w.document,pc=w.pc,out={};
const tree=()=>d.querySelector(".pc-tree"),main=()=>d.querySelector("main");
out.askedOnlyTheSharingSpec=asked.includes("/domain/shared/testsub")&&!asked.some(u=>/\/domain\/shared\/other/.test(u));
out.noPageCallLeft=typeof pc.addGroupValues==="undefined";
out.sharedGroupInTree=!!tree().querySelector('[data-ref="group:testsub/folders/Site"]')&&!!tree().querySelector('[data-ref="group:testsub/folders/Yard"]');
pc.select("group:testsub/folders/Site/Hall");await b.ready(60);
out.cardSaysWhence=/From the domain's shared settings \(rev 7\)/.test(main().textContent);
pc.select("group:testsub/folders/Yard");await b.ready(60);
out.ownGroupSaysNothing=!/shared settings/.test(main().textContent);
pc.select("unit:testsub/1");await b.ready(80);
const opts=[...main().querySelectorAll(".pc-addgroup option")].map(o=>o.value);
out.formOffersThem=opts.includes("Site/Hall")&&opts.includes("Site");
out.specCopy=pc.spec("testsub").domain.shared[0]==="folders"&&(pc.spec("testsub").rows="x",pc.spec("testsub").rows==="things")&&pc.spec("nope")===null;
out.neverRan=w.__pwned===undefined&&!d.querySelector("img");
out.errors=errs;
b.report(out,["errors"]);
try{fs.unlinkSync(TMP)}catch(e){}
process.exit(0);
})();
