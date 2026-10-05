// Модуль: создание единицы (общая форма по типам, POST, новая выбирается), пользователь и «Выйти», аварийный вход,
// «Повторить» у тоста — запись, исчерпавшая повторы, уходит снова тем же ключом.
const fs=require("fs"),path=require("path");
const SRC=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"pc-sess-"+process.pid+".html");
fs.writeFileSync(TMP,`<!doctype html><div id="app"></div><script>${SRC}</script><script>window.pc=PlatformConsole.mount(document.getElementById("app"),{lang:"en"});window.pc.retryWaits=[10,10,10];</script>`);
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
b.FIX["/session"]={open:false,user:"ann",login_url:"http://holder/api/login"};
b.FIX["/spec"]={name:"testsub",rows:"things",id:"numeric",fields:[{name:"name",type:"string"},{name:"labels",type:"list"},{name:"enabled",type:"bool",default:true}]};
b.FIX["/things"]={configured:[{id:1,name:"one"}],rows:[]};
b.FIX["/servers"]={servers:{},policy:{}};
b.FIX["/events"]={events:[],state:"live"};
(async()=>{
const w=b.boot();const errs=[];w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
let failNet=0,created=false;const sent=[];
const f0=w.fetch;w.fetch=(u,i)=>{const m=(i&&i.method)||"GET";sent.push([m,String(u),i&&i.body,((i||{}).headers||{})["Idempotency-Key"]]);
  if(m==="POST"&&u==="/things"){if(failNet>0){failNet--;return Promise.reject(new TypeError("Failed to fetch"))}created=true;b.FIX["/things"].configured.push({id:7,name:"seven"});return Promise.resolve({ok:true,status:201,json:()=>Promise.resolve({id:7,name:"seven"})})}
  if(m==="DELETE"&&u==="/session")return Promise.resolve({ok:true,status:200,json:()=>Promise.resolve({})});
  if(m==="POST"&&u==="/session/break-glass")return Promise.resolve({ok:true,status:200,json:()=>Promise.resolve({ok:true})});
  return f0(u,i)};
await b.ready(600);await w.pc.ready;const d=w.document,pc=w.pc,out={};
const main=()=>d.querySelector("main");
// пользователь и выход
out.userShown=/ann/.test(d.querySelector(".pc-uname").textContent)&&d.querySelector(".pc-logout").style.display!=="none";
// создание
pc.select(null);await b.ready(30);d.querySelector(".pc-hd [data-new='testsub']").click();await b.ready(30);
const f=main().querySelector(".pc-new-f");
out.newForm=!!f&&!!f.elements.name&&!!f.elements.labels;
f.elements.name.value="seven";f.dispatchEvent(new w.Event("submit",{cancelable:true}));await b.ready(150);
const post=sent.find(x=>x[0]==="POST"&&x[1]==="/things");
out.createPost=!!post&&JSON.parse(post[2]).name==="seven"&&JSON.parse(post[2]).enabled===true&&!!post[3];
out.newSelected=pc.selected()==="unit:testsub/7";
// «Повторить»: сеть пропала на все попытки, потом вернулась — тот же ключ
pc.select(null);await b.ready(30);d.querySelector(".pc-hd [data-new='testsub']").click();await b.ready(30);
const f2=main().querySelector(".pc-new-f");f2.elements.name.value="eight";failNet=4;
const before=sent.length;f2.dispatchEvent(new w.Event("submit",{cancelable:true}));await b.ready(250);
const err=f2.querySelector(".pc-err").textContent;
const rb=d.querySelector(".pc-toast .pc-retry");
out.retryOffered=!!rb&&/retry sends it again/.test(err);
const keys=sent.slice(before).filter(x=>x[0]==="POST"&&x[1]==="/things").map(x=>x[3]);
rb.click();await b.ready(150);
const keys2=sent.slice(before).filter(x=>x[0]==="POST"&&x[1]==="/things").map(x=>x[3]);
out.retrySameKey=keys.length===4&&keys2.length===5&&keys2.every(k=>k===keys[0]);
// выход
d.querySelector(".pc-logout").click();await b.ready(80);
out.logoutDeletes=sent.some(x=>x[0]==="DELETE"&&x[1]==="/session");
// аварийный вход
b.FIX["/session"]={open:false,login_url:"http://holder/api/login"};
w.eval("document.querySelector('.pc-login').hidden=false");d.querySelector(".pc-glass-go").click();
const gf=d.querySelector(".pc-glass-f");out.glassForm=gf.hidden===false;
gf.elements.who.value="ops";gf.elements.why.value="holder down";gf.elements.password.value="x";gf.dispatchEvent(new w.Event("submit",{cancelable:true}));await b.ready(100);
const g=sent.find(x=>x[0]==="POST"&&x[1]==="/session/break-glass");
out.glassPost=!!g&&JSON.parse(g[2]).who==="ops"&&JSON.parse(g[2]).why==="holder down";
out.errors=errs;
b.report(out,["errors"]);
try{fs.unlinkSync(TMP)}catch(e){}
process.exit(0);
})();
