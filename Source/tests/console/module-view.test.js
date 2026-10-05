// Вид модуля: полноэкранный инспектор (кнопка и Esc), граница панели тянется, обновление карточки по опросу —
// с новыми данными, но не под руками человека (поле в фокусе или изменено) и с той же прокруткой.
const fs=require("fs"),path=require("path");
const SRC=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"pc-view-"+process.pid+".html");
fs.writeFileSync(TMP,`<!doctype html><div id="app"></div><script>${SRC}</script><script>window.pc=PlatformConsole.mount(document.getElementById("app"),{lang:"en",poll_s:0.3});</script>`);
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
b.FIX["/session"]={open:true};
b.FIX["/spec"]={name:"testsub",rows:"things",id:"numeric",fields:[{name:"name",type:"string"}]};
b.FIX["/things"]={configured:[{id:1,name:"one"}],rows:[{id:1,worker:"w-1",phase:"running"}]};
b.FIX["/servers"]={servers:{},policy:{}};
b.FIX["/events"]={events:[],state:"live"};
(async()=>{
const w=b.boot();await b.ready(500);await w.pc.ready;const d=w.document,pc=w.pc,out={};
const root=d.querySelector(".pc"),main=()=>d.querySelector("main");
pc.select("unit:testsub/1");await b.ready(80);
main().querySelector(".pc-fullbtn").click();
out.fullOn=root.classList.contains("pc-full");
d.dispatchEvent(new w.KeyboardEvent("keydown",{key:"Escape"}));
out.escLeaves=!root.classList.contains("pc-full");
main().querySelector(".pc-fullbtn").click();main().querySelector(".pc-fullbtn").click();
out.sameButtonLeaves=!root.classList.contains("pc-full");
// граница панели тянется, ширина остаётся в браузере
const rsz=d.querySelector(".pc-rsz");rsz.dispatchEvent(new w.MouseEvent("mousedown",{clientX:400,bubbles:true}));
d.dispatchEvent(new w.MouseEvent("mousemove",{clientX:500}));d.dispatchEvent(new w.MouseEvent("mouseup",{}));
out.panelDrags=d.querySelector(".pc-ws").style.getPropertyValue("--aw")==="460px"&&w.localStorage.getItem("pc.aside")==="460";
// опрос обновляет карточку новыми данными
b.FIX["/things"]={configured:[{id:1,name:"one"}],rows:[{id:1,worker:"w-1",phase:"failed"}]};
await b.ready(700);
out.pollRefreshes=/Failed/.test(main().querySelector(".pc-state").textContent);
// не под руками: изменённое поле переживает опрос
const f=main().querySelector(".pc-edit");f.elements.name.value="typing…";
b.FIX["/things"]={configured:[{id:1,name:"one"}],rows:[{id:1,worker:"w-2",phase:"running"}]};
await b.ready(700);
out.typedSurvives=main().querySelector(".pc-edit").elements.name.value==="typing…";
b.report(out,[]);
try{fs.unlinkSync(TMP)}catch(e){}
process.exit(0);
})();
