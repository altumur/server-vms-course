// Обновление по опросу в модуле, как в консоли продукта: при тех же данных не трогает ни дерево, ни карточку (та же
// разметка, прокрутка, фокус); при новых — перерисовывает, а прокрутку, фокус и каретку в поле не сбрасывает; переход
// к другому объекту начинается сверху.
const fs=require("fs"),path=require("path");
const SRC=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"pc-poll-"+process.pid+".html");
fs.writeFileSync(TMP,`<!doctype html><div id="app"></div><script>${SRC}</script><script>window.pc=PlatformConsole.mount(document.getElementById("app"),{lang:"en",poll_s:0});</script>`);
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
b.FIX["/session"]={open:true};
b.FIX["/spec"]={name:"testsub",rows:"things",id:"numeric",fields:[{name:"name",type:"string"},{name:"note",type:"string"}]};
b.FIX["/things"]={configured:[{id:1,name:"gate",note:"abcdef"},{id:2,name:"door"}],rows:[{id:1,worker:"w-1",phase:"running"},{id:2,worker:"w-1",phase:"running"}]};
b.FIX["/servers"]={servers:{"s-1":{resource:"live",workers:[{worker:"w-1",load:2,capacity:5,state:"live"}]}},policy:{}};
b.FIX["/events"]={events:[],state:"live"};
(async()=>{
const w=b.boot();const errs=[];w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
await b.ready(600);await w.pc.ready;const d=w.document,pc=w.pc,out={};
const main=()=>d.querySelector(".pc-main"),tree=()=>d.querySelector(".pc-tree");
pc.select("unit:testsub/1");await b.ready(60);
main().scrollTop=170;tree().scrollTop=80;
const cardBefore=main().firstElementChild,rowBefore=tree().firstElementChild;
await pc.refresh();await b.ready(30);
out.mainKeepsScroll=main().scrollTop===170;
out.treeKeepsScroll=tree().scrollTop===80;
out.idlePollTouchesNothing=main().firstElementChild===cardBefore&&tree().firstElementChild===rowBefore;
// курсор в поле формы
const f=main().querySelector('input[name="note"]');f.focus();try{f.setSelectionRange(2,2)}catch(e){}
b.FIX["/things"]={configured:[{id:1,name:"gate!",note:"abcdef"},{id:2,name:"door"}],rows:[{id:1,worker:"w-1",phase:"running"},{id:2,worker:"w-1",phase:"running"}]};
await pc.refresh();await b.ready(30);
out.formFocusKept=d.activeElement===f;
out.caretKept=d.activeElement&&d.activeElement.selectionStart===2;
f.blur();
// данные изменились — разметка новая, положение то же
b.FIX["/things"]={configured:[{id:1,name:"gate!!",note:"abcdef"},{id:2,name:"door"}],rows:[{id:1,worker:"w-1",phase:"running"},{id:2,worker:"w-1",phase:"running"}]};
main().scrollTop=120;const before2=main().firstElementChild;
await pc.refresh();await b.ready(30);
out.changedRepaints=main().firstElementChild!==before2&&/gate!!/.test(d.querySelector(".pc-hd").textContent);
out.changedRepaintKeepsScroll=main().scrollTop===120;
// другой объект — сверху
main().scrollTop=150;pc.select("unit:testsub/2");await b.ready(30);
out.anotherObjectStartsAtTop=main().scrollTop===0;
out.errors=errs;
b.report(out,["errors"]);
try{fs.unlinkSync(TMP)}catch(e){}
process.exit(0);
})();
