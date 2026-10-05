// Права в модуле: гранты из /session прячут правку и действия, которых нет, и may() отвечает оболочке так же;
// без грантов may() — да (решает сервер). Вход: сессия закрыта и пользователя нет — окно входа.
const fs=require("fs"),path=require("path");
const SRC=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"pc-may-"+process.pid+".html");
fs.writeFileSync(TMP,`<!doctype html><div id="app"></div><script>${SRC}</script><script>window.pc=PlatformConsole.mount(document.getElementById("app"),{lang:"en"});</script>`);
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
b.FIX["/spec"]={name:"testsub",rows:"things",id:"numeric",fields:[{name:"name",type:"string"}],metrics:{}};
b.FIX["/things"]={configured:[{id:1,name:"one"},{id:2,name:"two"}],rows:[]};
b.FIX["/servers"]={servers:{},policy:{}};
b.FIX["/events"]={events:[],state:"live"};
async function run(session){
  b.FIX["/session"]=session;
  const w=b.boot();await b.ready(600);await w.pc.ready;return w;
}
(async()=>{
const out={};
let w=await run({open:false,user:"ann",grants:[{cap:"view",scope:"*"},{cap:"edit",scope:"unit:testsub/2"}]});
const pc=w.pc,d=w.document;
out.mayView=pc.may("view","unit:testsub/1")===true;
out.mayNotEdit1=pc.may("edit","unit:testsub/1")===false;
out.mayEdit2=pc.may("edit","unit:testsub/2")===true;
out.mayNotAdmin=pc.may("admin","unit:testsub/2")===false;
pc.select("unit:testsub/1");await b.ready(100);
const btns=()=>[...d.querySelectorAll(".pc-main button")].map(x=>x.textContent).join("|");
out.viewOnlyNoSave=!/Save|Delete/.test(btns())&&d.querySelector(".pc-edit input[name=name]").disabled;
pc.select("unit:testsub/2");await b.ready(100);
out.editHasSaveNoDelete=/Save/.test(btns())&&!/Delete/.test(btns());
out.loggedInNoLoginBox=d.querySelector(".pc-login").hidden===true;
w=await run({open:false,login_url:"http://holder/api/login"});
out.loginShown=w.document.querySelector(".pc-login").hidden===false;
w=await run({open:true});
out.noGrantsMayAll=w.pc.may("admin","unit:testsub/1")===true;
b.report(out,[]);
try{fs.unlinkSync(TMP)}catch(e){}
process.exit(0);
})();
