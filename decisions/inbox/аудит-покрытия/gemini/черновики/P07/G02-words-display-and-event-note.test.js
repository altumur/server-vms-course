// Черновик G02 (P/07 Н1.5 words): вызовы оболочки display(name), eventNote(e) и addEventNote(fn)
const fs=require("fs"),path=require("path");
const SRC=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"pc-words-api-"+process.pid+".html");
fs.writeFileSync(TMP,`<!doctype html><div id="app"></div><script>${SRC}</script><script>window.pc=PlatformConsole.mount(document.getElementById("app"),{lang:"en"});</script>`);
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
b.FIX["/session"]={open:true};
b.FIX["/manifest"]={name:"testsub",rows:"things",id:"numeric",fields:[{name:"name",type:"string"}],
  display:{unit:"thing",units:"things",kinds:{"custom.ev":"Custom event"}}};
b.FIX["/things"]={configured:[{id:1,name:"one"}],rows:[]};
b.FIX["/servers"]={servers:{},policy:{}};
b.FIX["/events"]={events:[{t:10,kind:"custom.ev",subsystem:"testsub",unit:"1",detail:{code:42}}],state:"live"};

(async()=>{
  const w=b.boot(),errs=[];w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
  await w.pc.ready;await b.ready(150);
  const pc=w.pc,d=w.document,out={};
  // display(name): возвращает копию словаря display подсистемы; для неизвестной — null/пусто
  const disp=pc.display("testsub");
  out.displayReturnsWords=!!disp&&disp.unit==="thing"&&disp.units==="things";
  // addEventNote + eventNote(e): пользовательская заметка события дополняет/переопределяет описание
  pc.addEventNote(e=>e&&e.kind==="custom.ev"?"custom note #"+(e.detail&&e.detail.code):null);
  const note=pc.eventNote({kind:"custom.ev",detail:{code:42}});
  out.eventNoteReturnsCustom=/custom note #42/.test(String(note||""));
  d.querySelector('.pc-rail [data-s="journal"]').click();await b.ready(150);
  out.journalShowsCustomNote=/custom note #42/.test(d.querySelector("main").textContent);
  w.close();
  out.errors=errs;
  b.report(out,["errors"]);
  try{fs.unlinkSync(TMP)}catch(e){}
  process.exit(0);
})();
