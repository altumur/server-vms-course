// Группы, сделанные здесь (как новая папка прежней консоли): «＋ группа» в шапке обзора и «＋ подгруппа» в шапке группы,
// новая группа живёт в этом браузере, пока её значение не получит единица; меню группы — подгруппа, переименовать,
// добавить сюда; у «без группы» — создать; слова — из display.tree, если есть. «Удалить» в меню единицы — по may(admin).
const fs=require("fs"),path=require("path");
const SRC=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"pc-lgrp-"+process.pid+".html");
fs.writeFileSync(TMP,`<!doctype html><div id="app"></div><script>${SRC}</script><script>window.pc=PlatformConsole.mount(document.getElementById("app"),{lang:"en",poll_s:0});</script>`);
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
b.FIX["/session"]={open:true};
b.FIX["/spec"]={name:"testsub",rows:"things",id:"numeric",fields:[{name:"name",type:"string"},{name:"folders",type:"list"}],
  display:{unit:"thing",tree:{group_by:"folders",nested_by:"/",new_root:"folder",new_sub:"subfolder",add_here:"Add a thing here",new_group_note:"Folder made — put a thing in it"}}};
b.FIX["/things"]={configured:[{id:1,name:"gate",folders:["Yard"]},{id:2,name:"roof"}],rows:[]};
b.FIX["/servers"]={servers:{},policy:{}};
(async()=>{
const w=b.boot();const errs=[];w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
w.confirm=()=>true;
await b.ready(600);await w.pc.ready;const d=w.document,pc=w.pc,out={};
const dialog=async v=>{await b.ready(20);const f=d.querySelector(".pc-dialog form");f.querySelector("input").value=v;f.dispatchEvent(new w.Event("submit",{cancelable:true}));await b.ready(40)};
const head=()=>[...d.querySelectorAll(".pc-hd .pc-acts button")].map(x=>x.textContent);
pc.select(null);await b.ready(30);
out.rootHeadButtons=head().join("|")==="＋ Folder|＋ Thing";
[...d.querySelectorAll(".pc-hd .pc-acts button")].find(x=>/Folder/.test(x.textContent)).click();await dialog("Store");
out.newGroupSelected=pc.selected()==="group:testsub/folders/Store"&&/Folder made/.test(d.querySelector(".pc-toast").textContent);
out.newGroupInTree=!!d.querySelector('.pc-tree [data-ref="group:testsub/folders/Store"]');
out.keptInBrowser=/Store/.test(w.localStorage.getItem("pc.groups")||"");
out.groupHeadButtons=head().join("|")==="＋ Subfolder|＋ Thing";
[...d.querySelectorAll(".pc-hd .pc-acts button")].find(x=>/Subfolder/.test(x.textContent)).click();await dialog("Back");
out.subGroup=pc.selected()==="group:testsub/folders/Store/Back"&&!!d.querySelector('.pc-tree [data-ref="group:testsub/folders/Store/Back"]');
// повтор имени — не заводится
[...d.querySelectorAll(".pc-hd .pc-acts button")].find(x=>/Subfolder/.test(x.textContent)); pc.select("group:testsub/folders/Store");await b.ready(20);
[...d.querySelectorAll(".pc-hd .pc-acts button")].find(x=>/Subfolder/.test(x.textContent)).click();await dialog("Back");
out.noTwin=/There is such a group already/.test(d.querySelector(".pc-toast").textContent);
// меню группы
const menu=ref=>{const n=d.querySelector(`.pc-tree .n[data-ref="${ref}"]`);n.dispatchEvent(new w.MouseEvent("contextmenu",{bubbles:true,clientX:5,clientY:5}));return[...d.querySelectorAll(".pc-menu button")]};
out.groupMenu=menu("group:testsub/folders/Yard").map(x=>x.textContent).join("|")==="Open|Add to favourites|＋ Subfolder|Rename|Add a thing here";
menu("group:testsub/folders/Yard").find(x=>x.textContent==="Add a thing here").click();await b.ready(40);
out.addHere=pc.selected()==="new:testsub"&&d.querySelector("main .pc-new-f").elements.folders.value==="Yard";
out.noGroupMenu=menu("group:testsub/folders/").map(x=>x.textContent).includes("＋ Folder");
// единица получила значение — группа больше не хранится здесь
b.FIX["/things"]={configured:[{id:1,name:"gate",folders:["Yard"]},{id:2,name:"roof",folders:["Store/Back"]}],rows:[]};
await pc.refresh();await b.ready(40);
out.prunedWhenCarried=!/Store/.test(w.localStorage.getItem("pc.groups")||"[]")&&!!d.querySelector('.pc-tree [data-ref="group:testsub/folders/Store"]');
// «Удалить» в меню единицы
d.querySelector('.pc-tree [data-tw="group:testsub/folders/Yard"]').click();await b.ready(10);
const del=menu("unit:testsub/1").find(x=>x.textContent==="Delete");
const n0=w.__calls.length;if(del)del.click();await b.ready(80);
out.unitDelete=!!del&&w.__calls.slice(n0).some(c=>c.method==="DELETE"&&c.path==="/things/1");
out.errors=errs;
b.report(out,["errors"]);
try{fs.unlinkSync(TMP)}catch(e){}
process.exit(0);
})();
