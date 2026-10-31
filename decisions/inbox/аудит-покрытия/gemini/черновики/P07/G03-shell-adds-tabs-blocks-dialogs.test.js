// Черновик G03 (P/07 Н1.5 adds, Н1.6 adds): addSection, addAction, dialog, confirm,
// addTab для видов server | worker | member | domain и флаг busy, addBlock для видов member | domain
const fs=require("fs"),path=require("path");
const SRC=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"pc-shell-adds-"+process.pid+".html");
fs.writeFileSync(TMP,`<!doctype html><div id="app"></div><script>${SRC}</script><script>window.pc=PlatformConsole.mount(document.getElementById("app"),{lang:"en",poll_s:0.3});</script>`);
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
b.FIX["/session"]={open:true};
b.FIX["/manifest"]={name:"testsub",rows:"things",id:"numeric",fields:[{name:"name",type:"string"}]};
b.FIX["/things"]={configured:[{id:1,name:"one"}],rows:[{id:1,worker:"w-1",server:"s-1",phase:"running"}]};
b.FIX["/servers"]={servers:{"s-1":{resource:"live",workers:[{worker:"w-1",load:1,capacity:5,state:"live"}]}},policy:{}};
b.FIX["/domain"]={holder:"hold",members:[{name:"hold",holder:true,state:"ok"},{name:"m-1",state:"ok"}],units:{}};
b.FIX["/domain/alarms"]={events:[]};

(async()=>{
  const w=b.boot(),errs=[];w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
  const pc=w.pc;
  let busyFlag=false,actionRef=null;
  pc.addSection({id:"custom-sec",label:"CustomSec",icon:"folder",after:"units",render:host=>{host.innerHTML="<p class='csec'>custom section body</p>"}});
  pc.addTab("unit",{id:"busy-tab",label:"BusyTab",busy:()=>busyFlag,render:host=>{host.innerHTML="<span class='bt'>t</span>"}});
  for(const kind of ["server","worker","member","domain"]){
    pc.addTab(kind,{id:"t-"+kind,label:"Tab-"+kind,render:(host,ref)=>{host.innerHTML=`<p class="tk-${kind}">${ref}</p>`}});
  }
  for(const kind of ["member","domain"]){
    pc.addBlock(kind,{id:"b-"+kind,render:(host,ref)=>{host.innerHTML=`<div class="bk-${kind}">block:${ref}</div>`}});
  }
  pc.addAction("unit",{label:"PingUnit",run:ref=>{actionRef=ref}});
  await pc.ready;await b.ready(150);
  const d=w.document,main=()=>d.querySelector("main"),out={};
  // 1. addSection рисует кнопку в рейке и открывает раздел
  const secBtn=d.querySelector('.pc-rail [data-s="custom-sec"]');
  out.sectionAdded=!!secBtn&&/CustomSec/.test(secBtn.textContent);
  if(secBtn)secBtn.click();await b.ready(60);
  out.sectionRendered=!!main().querySelector(".csec");
  d.querySelector('.pc-rail [data-s="units"]').click();await b.ready(60);
  // 2. addAction на карточке единицы и busy() у вкладки addTab
  pc.select("unit:testsub/1");await b.ready(60);
  const actBtn=[...d.querySelectorAll(".pc-hd button, .pc-main button")].find(x=>/PingUnit/.test(x.textContent));
  if(actBtn)actBtn.click();
  out.actionRan=actionRef==="unit:testsub/1";
  pc.select("unit:testsub/1",{tab:"busy-tab"});await b.ready(40);
  const btBefore=main().querySelector(".bt");
  busyFlag=true;
  b.FIX["/things"]={configured:[{id:1,name:"one-changed"}],rows:[{id:1,worker:"w-1",server:"s-1",phase:"running"}]};
  await pc.refresh();await b.ready(40);
  out.busySkipsRepaint=main().querySelector(".bt")===btBefore;
  busyFlag=false;
  // 3. addTab для server, worker, member, domain и addBlock для member, domain
  for(const [kind,ref] of [["server","server:s-1"],["worker","worker:testsub/w-1"],["member","member:m-1"],["domain","domain"]]){
    pc.select(ref);await b.ready(50);
    if(kind==="member"||kind==="domain")out["block_"+kind]=!!main().querySelector(".bk-"+kind);
    pc.select(ref,{tab:"t-"+kind});await b.ready(50);
    out["tab_"+kind]=!!main().querySelector(".tk-"+kind);
  }
  // 4. dialog(title, fields, ok) и confirm(...)
  let dlgVals=null;
  pc.dialog("Ask",[{name:"q",label:"Question",value:"v1"}],vals=>{dlgVals=vals});
  await b.ready(30);
  const df=d.querySelector(".pc-dialog form");
  if(df){df.elements.q.value="v2";df.dispatchEvent(new w.Event("submit",{cancelable:true}));}
  await b.ready(50);
  out.dialogSubmitted=!!dlgVals&&dlgVals.q==="v2";
  out.confirmCallable=typeof pc.confirm==="function";
  w.close();
  out.errors=errs;
  b.report(out,["errors"]);
  try{fs.unlinkSync(TMP)}catch(e){}
  process.exit(0);
})();
