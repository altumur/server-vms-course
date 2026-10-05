// Группы в модуле: узел группы по display.tree.group_by — объект group:<sub>/<поле>/<значение> с карточкой (единицы,
// число), «без группы», переименование (PUT поля-списка у каждой, отчёт о неудачах), добавить в группу, убрать из неё.
const fs=require("fs"),path=require("path");
const SRC=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"pc-grp-"+process.pid+".html");
fs.writeFileSync(TMP,`<!doctype html><div id="app"></div><script>${SRC}</script><script>window.pc=PlatformConsole.mount(document.getElementById("app"),{lang:"en"});</script>`);
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
const P=`x"'><img src=x onerror=window.__pwned=1>`;
b.FIX["/session"]={open:true};
b.FIX["/spec"]={name:"testsub",rows:"things",id:"numeric",fields:[{name:"name",type:"string"},{name:"folders",type:"list"}],display:{tree:{group_by:"folders"}}};
b.FIX["/things"]={configured:[{id:1,name:"gate",folders:["Yard","Main"]},{id:2,name:"door",folders:["Yard"]},{id:3,name:"roof",folders:[]},{id:4,name:P,folders:[P]}],rows:[]};
b.FIX["/servers"]={servers:{},policy:{}};
b.FIX["/events"]={events:[],state:"live"};
(async()=>{
const w=b.boot();const errs=[];w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
// unit 2 refuses the rename
const f0=w.fetch;w.fetch=(u,i)=>{if(i&&i.method==="PUT"&&u==="/things/2"&&JSON.parse(i.body).folders.includes("Garden"))return Promise.resolve({ok:false,status:409,json:()=>Promise.resolve({detail:"busy row"})});if(i&&i.method==="PUT"&&/^\/things\/\d+$/.test(u)){w.__calls.push({method:"PUT",path:u,body:JSON.parse(i.body),key:(i.headers||{})["Idempotency-Key"]||""});return Promise.resolve({ok:true,status:200,json:()=>Promise.resolve({})})}return f0(u,i)};
await b.ready(600);await w.pc.ready;const d=w.document,pc=w.pc,out={};
const tree=()=>d.querySelector(".pc-tree"),main=()=>d.querySelector("main");
out.groupNodes=!!tree().querySelector('[data-ref="group:testsub/folders/Yard"]')&&!!tree().querySelector('[data-ref="group:testsub/folders/"]');
tree().querySelector('[data-ref="group:testsub/folders/Yard"]').click();await b.ready(60);
out.groupCard=/Yard/.test(main().querySelector(".pc-hd").textContent)&&/in it: 2/.test(main().textContent)&&/gate/.test(main().textContent)&&/door/.test(main().textContent);
// переименовать: 1 удалось, 2 отказал — отчёт
[...main().querySelectorAll("button")].find(x=>/^Rename$/.test(x.textContent)).click();await b.ready(20);
d.querySelector(".pc-dialog input").value="Garden";
let n=w.__calls.length;d.querySelector(".pc-dialog form").dispatchEvent(new w.Event("submit",{cancelable:true}));await b.ready(200);
const puts=w.__calls.slice(n).filter(x=>x.method==="PUT");
out.renamePutsList=puts.some(x=>x.path==="/things/1"&&JSON.stringify(x.body)==='{"folders":["Garden","Main"]}');
out.renameReportsFailure=/not done for 1: door: busy row/.test(d.querySelector(".pc-toast").textContent);
// добавить в группу / убрать из неё
pc.select("group:testsub/folders/Main");await b.ready(60);
[...main().querySelectorAll("button")].find(x=>/Add to this group/.test(x.textContent)).click();await b.ready(20);
d.querySelector(".pc-dialog select").value="3";
n=w.__calls.length;d.querySelector(".pc-dialog form").dispatchEvent(new w.Event("submit",{cancelable:true}));await b.ready(150);
out.addPut=w.__calls.slice(n).some(x=>x.path==="/things/3"&&JSON.stringify(x.body)==='{"folders":["Main"]}');
pc.select("group:testsub/folders/Main");await b.ready(60);
n=w.__calls.length;main().querySelector("[data-out='1']").click();await b.ready(150);
out.removePut=w.__calls.slice(n).some(x=>x.path==="/things/1"&&JSON.stringify(x.body)==='{"folders":["Yard"]}');
// «без группы» — без действий
pc.select("group:testsub/folders/");await b.ready(60);
// «＋ <единица>» в шапке группы: новая единица сразу в этой группе
pc.select("group:testsub/folders/Yard");await b.ready(60);
d.querySelector(".pc-hd [data-new='testsub']").click();await b.ready(60);
{const nf=d.querySelector("main .pc-new-f");out.newInGroup=!!nf&&nf.elements.folders.value==="Yard";}
pc.select("group:testsub/folders/");await b.ready(60);
out.noGroupReadOnly=/without a group/i.test(main().textContent)&&/roof/.test(main().textContent)&&!main().querySelector("[data-a]");
out.neverRan=w.__pwned===undefined&&!d.querySelector("img");
out.errors=errs;
b.report(out,["errors"]);
try{fs.unlinkSync(TMP)}catch(e){}
process.exit(0);
})();
