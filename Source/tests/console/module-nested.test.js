// Вложенные группы (display.tree.nested_by): «Офис/Вход» — группа «Вход» внутри «Офис»; ref — путь целиком;
// карточка группы считает и подгруппы; переименование узла переписывает префикс у всех единиц под ним.
const fs=require("fs"),path=require("path");
const SRC=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"pc-nest-"+process.pid+".html");
fs.writeFileSync(TMP,`<!doctype html><div id="app"></div><script>${SRC}</script><script>window.pc=PlatformConsole.mount(document.getElementById("app"),{lang:"en"});</script>`);
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
b.FIX["/session"]={open:true};
b.FIX["/spec"]={name:"testsub",rows:"things",id:"numeric",fields:[{name:"name",type:"string"},{name:"folders",type:"list"}],display:{tree:{group_by:"folders",nested_by:"/"}}};
b.FIX["/things"]={configured:[{id:1,name:"gate",folders:["Office/Entrance"]},{id:2,name:"hall",folders:["Office"]},{id:3,name:"yard",folders:["Yard"]},{id:4,name:"roof",folders:[]}],rows:[]};
b.FIX["/servers"]={servers:{},policy:{}};
b.FIX["/events"]={events:[],state:"live"};
(async()=>{
const w=b.boot();const errs=[];w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
const f0=w.fetch;w.fetch=(u,i)=>{if(i&&i.method==="PUT"&&/^\/things\/\d+$/.test(u)){w.__calls.push({method:"PUT",path:u,body:JSON.parse(i.body)});return Promise.resolve({ok:true,status:200,json:()=>Promise.resolve({})})}return f0(u,i)};
await b.ready(600);await w.pc.ready;const d=w.document,pc=w.pc,out={};
const tree=()=>d.querySelector(".pc-tree"),main=()=>d.querySelector("main");
const has=r=>!!tree().querySelector(`[data-ref="${r}"]`);
out.topLevel=has("group:testsub/folders/Office")&&has("group:testsub/folders/Yard")&&has("group:testsub/folders/");
// папки свёрнуты, пока их не раскрыли (как в консоли продукта)
out.closedByDefault=!has("group:testsub/folders/Office/Entrance");
out.officeCountsBelow=/2/.test(tree().querySelector('[data-ref="group:testsub/folders/Office"] .cnt').textContent);
tree().querySelector('[data-tw="group:testsub/folders/Office"]').click();
out.closes=(tree().querySelector('[data-tw="group:testsub/folders/Office"]').click(),!has("group:testsub/folders/Office/Entrance"));
tree().querySelector('[data-tw="group:testsub/folders/Office"]').click();
out.nestedShown=has("group:testsub/folders/Office/Entrance")&&has("unit:testsub/2")&&/Entrance/.test(tree().querySelector('[data-ref="group:testsub/folders/Office/Entrance"]').textContent);
pc.select("group:testsub/folders/Office");await b.ready(60);
out.cardCountsBelow=/in it: 2/.test(main().textContent)&&!!main().querySelector("[data-out='2']")&&!main().querySelector("[data-out='1']");
[...main().querySelectorAll("button")].find(x=>/^Rename$/.test(x.textContent)).click();await b.ready(20);
d.querySelector(".pc-dialog input").value="HQ";
let n=w.__calls.length;d.querySelector(".pc-dialog form").dispatchEvent(new w.Event("submit",{cancelable:true}));await b.ready(200);
const puts=w.__calls.slice(n).filter(x=>x.method==="PUT");
out.renamePrefix=puts.some(x=>x.path==="/things/1"&&JSON.stringify(x.body)==='{"folders":["HQ/Entrance"]}')&&puts.some(x=>x.path==="/things/2"&&JSON.stringify(x.body)==='{"folders":["HQ"]}')&&!puts.some(x=>x.path==="/things/3");
const q=d.querySelector(".pc-q");q.value="gate";q.dispatchEvent(new w.Event("input"));
out.searchOpensPath=has("group:testsub/folders/Office/Entrance")&&has("unit:testsub/1")&&!has("unit:testsub/3");
out.errors=errs;
b.report(out,["errors"]);
try{fs.unlinkSync(TMP)}catch(e){}
process.exit(0);
})();
