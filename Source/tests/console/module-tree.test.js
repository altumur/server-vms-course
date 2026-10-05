// Дерево модуля: поиск (имя, id, поля), вложенные единицы раскрываются при совпадении, избранное
// (звезда на карточке, панель под деревом, переход в нужный раздел, переживает перезагрузку), колонки из
// display.tree.columns (секрет маской, список через запятую, поле статуса), группировка по полю-списку.
const fs=require("fs"),path=require("path");
const SRC=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"pc-tree-"+process.pid+".html");
fs.writeFileSync(TMP,`<!doctype html><div id="app"></div><script>${SRC}</script><script>window.pc=PlatformConsole.mount(document.getElementById("app"),{lang:"en"});</script>`);
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
b.FIX["/session"]={open:true};
b.FIX["/spec"]={name:"testsub",rows:"things",id:"numeric",fields:[{name:"name",type:"string"},{name:"labels",type:"list"},{name:"folders",type:"list"},{name:"key_secret",type:"string"}],display:{units:"things",tree:{group_by:"folders",columns:[{field:"phase",title:"state"},{field:"labels",title:"nets",width:10},{field:"key_secret",title:"key"}]}}};
b.FIX["/mounts"]={root:"testsub",mounts:{sub:{name:"subthings",rows:"parts",id:"name",about:{sub:"testsub",field:"thing"},fields:[{name:"thing",type:"string"}]}}};
b.FIX["/things"]={configured:[{id:1,name:"gate",labels:["a","b"],folders:["Yard"],key_secret:"***"},{id:2,name:"door",labels:[],folders:["Hall"],key_secret:""},{id:3,name:"roof",labels:[],folders:[]}],
  rows:[{id:1,worker:"w-1",phase:"running"},{id:2,worker:"w-1",phase:"failed"}]};
b.FIX["/sub/parts"]={configured:[{id:"zebra-part",thing:"3"}],rows:[]};
b.FIX["/servers"]={servers:{"s-1":{resource:"live",workers:[{worker:"w-1",load:2,capacity:5,state:"live"}]}},policy:{}};
b.FIX["/events"]={events:[],state:"live"};
(async()=>{
let w=b.boot();await b.ready(600);await w.pc.ready;let d=w.document,pc=w.pc;const out={};
const tree=()=>d.querySelector(".pc-tree");
const refs=()=>[...tree().querySelectorAll("[data-ref]")].map(x=>x.dataset.ref).filter(r=>r.startsWith("unit:"));
out.groupedByFolders=/Yard/.test(tree().textContent)&&/Hall/.test(tree().textContent);
tree().querySelector('[data-tw="group:testsub/folders/Yard"]').click();
const row1=tree().querySelector('[data-ref="unit:testsub/1"]');
out.columns=!!row1&&[...row1.querySelectorAll(".n-tags .tag")].map(x=>x.textContent).join("|")==="running|a, b|***"&&row1.querySelectorAll(".n-tags .tag")[1].title==="nets";
const q=d.querySelector(".pc-q");
q.value="door";q.dispatchEvent(new w.Event("input"));
out.searchByName=refs().join(",")==="unit:testsub/2";
q.value="zebra";q.dispatchEvent(new w.Event("input"));
out.searchOpensParent=refs().includes("unit:testsub/3")&&refs().includes("unit:subthings/zebra-part");
q.value="nothing-like-this";q.dispatchEvent(new w.Event("input"));
out.nothingFound=/nothing found/.test(tree().textContent);
q.value="";q.dispatchEvent(new w.Event("input"));
// избранное
pc.select("unit:testsub/1");await b.ready(80);
d.querySelector("main .pc-star").click();await b.ready(20);
out.favListed=/gate/.test(d.querySelector(".pc-favs .fav-panel-list").textContent)&&d.querySelector("main .pc-star").textContent==="★";
(d.querySelector('.pc-rail [data-s="units"]').click(),d.querySelector('.pc-layout').click(),d.querySelector('[data-layout="servers"]').click());await b.ready(20);
pc.select("server:s-1");await b.ready(30);d.querySelector("main .pc-star").click();await b.ready(20);
d.querySelector('[data-fav="unit:testsub/1"]').click();await b.ready(80);
out.favJumpsSection=d.querySelector('.pc-rail [data-s="units"]').classList.contains("on")&&pc.selected()==="unit:testsub/1";
const stored=w.localStorage.getItem("pc.favs.v1");
out.favStored=/unit:testsub\/1/.test(stored)&&/server:s-1/.test(stored);
b.report(out,[]);
try{fs.unlinkSync(TMP)}catch(e){}
process.exit(0);
})();
