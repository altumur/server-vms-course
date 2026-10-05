// Воркер, который не назвал свой сервер при спеке с placement.places.server_field (ADR-0029): пульс несёт
// server_unsaid — слово базы. Модуль показывает его меткой в строке воркера и предупреждением в карточке, без логики.
const fs=require("fs"),path=require("path");
const SRC=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"pc-unsaid-"+process.pid+".html");
fs.writeFileSync(TMP,`<!doctype html><div id="app"></div><script>${SRC}</script><script>window.pc=PlatformConsole.mount(document.getElementById("app"),{lang:"en",poll_s:0});</script>`);
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
const P=`x"'><img src=x onerror=window.__pwned=1>`;
b.FIX["/session"]={open:true};
b.FIX["/spec"]={name:"testsub",rows:"things",id:"numeric",fields:[{name:"name",type:"string"}]};
b.FIX["/things"]={configured:[],rows:[]};
b.FIX["/servers"]={servers:{"s-1":{resource:"live",workers:[{worker:"w-1",load:0,capacity:5,state:"live",server_unsaid:"this worker names no server of its own: every place it holds is let go when its hold goes unconfirmed "+P},{worker:"w-2",load:0,capacity:5,state:"live"}]}},policy:{}};
(async()=>{
const w=b.boot();const errs=[];w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
await b.ready(600);await w.pc.ready;const d=w.document,pc=w.pc,out={};
(d.querySelector('.pc-rail [data-s="units"]').click(),d.querySelector('.pc-layout').click(),d.querySelector('[data-layout="servers"]').click());await b.ready(30);
d.querySelector('.pc-tree [data-tw="server:s-1"]').click();await b.ready(20);
const row=n=>d.querySelector(`.pc-tree [data-ref="worker:${n}"]`);
out.tagOnRow=[...row("w-1").querySelectorAll(".tag")].some(t=>t.textContent==="server not named"&&/names no server/.test(t.title));
out.quietWithout=![...row("w-2").querySelectorAll(".tag")].some(t=>/not named/.test(t.textContent));
pc.select("worker:w-1");await b.ready(40);
out.cardSaysIt=/server not named: this worker names no server of its own/.test(d.querySelector("main").textContent)&&!!d.querySelector("main .nt.err");
out.neverRan=w.__pwned===undefined&&!d.querySelector("main img");
out.errors=errs;
b.report(out,["errors"]);
try{fs.unlinkSync(TMP)}catch(e){}
process.exit(0);
})();
