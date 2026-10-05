// display.tree.children: false — единицы подсистем, чей about указывает на эту, в дереве не вкладываются:
// у единицы нет стрелки, их строк нет и при поиске, а сами они видны в карточке единицы. Без флага — вложены.
const fs=require("fs"),path=require("path");
const SRC=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"pc-children-"+process.pid+".html");
fs.writeFileSync(TMP,`<!doctype html><div id="app"></div><script>${SRC}</script><script>window.pc=PlatformConsole.mount(document.getElementById("app"),{lang:"en"});</script>`);
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
b.FIX["/session"]={open:true};
b.FIX["/spec"]={name:"testsub",rows:"things",id:"numeric",fields:[{name:"name",type:"string"}],display:{tree:{children:false}}};
b.FIX["/mounts"]={root:"testsub",mounts:{sub:{name:"subthings",rows:"parts",id:"name",about:{sub:"testsub",field:"thing"},fields:[{name:"thing",type:"string"}]}}};
b.FIX["/things"]={configured:[{id:1,name:"gate"}],rows:[{id:1,worker:"w-1",phase:"running"}]};
b.FIX["/sub/parts"]={configured:[{id:"p1",thing:"1"}],rows:[]};
b.FIX["/servers"]={servers:{},policy:{}};
b.FIX["/events"]={events:[],state:"live"};
(async()=>{
const w=b.boot();const errs=[];w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
await b.ready(600);await w.pc.ready;const d=w.document,out={};
const tree=()=>d.querySelector(".pc-tree");
out.unitShown=!!tree().querySelector('[data-ref="unit:testsub/1"]');
out.noTwisty=!tree().querySelector('[data-tw="unit:testsub/1"]');
out.partNotInTree=!tree().querySelector('[data-ref="unit:subthings/p1"]');
const q=d.querySelector(".pc-q");q.value="p1";q.dispatchEvent(new w.Event("input"));
out.searchDoesNotNest=!tree().querySelector('[data-ref="unit:subthings/p1"]');
out.errors=errs;
b.report(out,["errors"]);
try{fs.unlinkSync(TMP)}catch(e){}
process.exit(0);
})();
