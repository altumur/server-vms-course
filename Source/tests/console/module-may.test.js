// Права в модуле — P/07 Н1.5 may: гранты из /session прячут правку и действия, которых нет, и may() отвечает оболочке так
// же — по рангу cap и области scope (договор права common/contracts/may.md шаг 7: *, unit:<sub>/<id> единицы или её
// about-единицы, labels:L — метки about, иначе самой единицы); вне единицы — только *, view — любая строка (шаг 6);
// аварийная сессия (via break-glass, grants []) — да; без грантов да только у открытой консоли (open: true); закрытая
// или неизвестная сессия (/session не ответила) без грантов — нет. Вход: сессия закрыта и пользователя нет — окно входа.
const fs=require("fs"),path=require("path");
const SRC=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"pc-may-"+process.pid+".html");
fs.writeFileSync(TMP,`<!doctype html><div id="app"></div><script>${SRC}</script><script>window.pc=PlatformConsole.mount(document.getElementById("app"),{lang:"en"});</script>`);
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
b.FIX["/spec"]={name:"testsub",rows:"things",id:"numeric",fields:[{name:"name",type:"string"}],metrics:{}};
b.FIX["/things"]={configured:[{id:1,name:"one",labels:["a","b"]},{id:2,name:"two"}],rows:[]};
b.FIX["/mounts"]={root:"testsub",mounts:{sub:{name:"sub",rows:"parts",id:"name",about:{sub:"testsub",field:"thing"},fields:[{name:"thing",type:"string"},{name:"labels",type:"list"}]}}};
b.FIX["/sub/parts"]={configured:[{id:"p1",thing:"1",labels:["z"]},{id:"p2",thing:"2",labels:["a"]}],rows:[]};
b.FIX["/servers"]={servers:{},policy:{}};
b.FIX["/events"]={events:[],state:"live"};
async function run(session){
  b.FIX["/session"]=session;
  const w=b.boot();await b.ready(600);await w.pc.ready;return w;
}
(async()=>{
const out={};
let w=await run({open:false,user:"ann",via:"token",grants:[{cap:"view",scope:"*"},{cap:"edit",scope:"unit:testsub/2"}]});
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
out.openConsoleMayAll=w.pc.may("admin","unit:testsub/1")===true&&w.pc.may("admin",null)===true;
w=await run({open:false,login_url:"/api/login"});
out.closedNoGrantsMayNot=w.pc.may("view","unit:testsub/1")===false&&w.pc.may("view",null)===false;
b.FIX["/session"]=undefined;delete b.FIX["/session"];{const w2=b.boot();await b.ready(600);await w2.pc.ready;w=w2;}
out.unknownSessionMayNot=w.pc.may("view","unit:testsub/1")===false&&w.pc.may("view",null)===false;
w=await run({open:false,user:"ops",via:"break-glass",until:9,grants:[]});
out.breakGlassMayAll=w.pc.may("admin","unit:testsub/1")===true&&w.pc.may("admin",null)===true;
w=await run({open:false,user:"bob",via:"token",until:9,grants:[{cap:"edit",scope:"unit:testsub/1"},{cap:"admin",scope:"labels:a,b"}]});
out.aboutUnitGrant=w.pc.may("edit","unit:sub/p1")===true&&w.pc.may("edit","unit:sub/p2")===false;
out.labelsOfUnit=w.pc.may("admin","unit:testsub/1")===true&&w.pc.may("admin","unit:testsub/2")===false;
out.labelsOfAboutNotOwn=w.pc.may("admin","unit:sub/p1")===true&&w.pc.may("admin","unit:sub/p2")===false;
out.noUnitOnlyStarViewAny=w.pc.may("view",null)===true&&w.pc.may("edit",null)===false&&w.pc.may("admin","domain")===false&&w.pc.may("admin","server:s-1")===false;
b.report(out,[]);
try{fs.unlinkSync(TMP)}catch(e){}
process.exit(0);
})();
