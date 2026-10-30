// Модуль: возврат после входа (P/07 Н1.5 return; P/06.5 Н2 «Вход на оболочке»): только ровно /<sub>/ своего каталога, иначе на /.
const fs=require("fs"),path=require("path");
const SRC=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"pc-return-"+process.pid+".html");
// location.replace в jsdom не исполняется и не подменяется: страница теста зовёт вместо него свой приёмник
const GO="window.location.replace(",PAGE=SRC.split(GO).join("window.__go(");
if(PAGE===SRC)throw new Error("the module no longer calls "+GO);
fs.writeFileSync(TMP,`<!doctype html><div id="app"></div><script>window.__went=[];window.__go=u=>window.__went.push(String(u))</script><script>${PAGE}</script><script>window.pc=PlatformConsole.mount(document.getElementById("app"),{lang:"en",subsystems:["testsub"]})</script>`);
process.on("exit",()=>{try{fs.unlinkSync(TMP)}catch(e){}});
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
const man=(name,rows)=>({name,rows,id:"numeric",fields:[{name:"name",type:"string"}]});
b.FIX["/manifest"]=man("testsub","things");
b.FIX["/mounts"]={root:"testsub",mounts:{backend:man("backend","instances")}};
b.FIX["/things"]={configured:[],rows:[]};
b.FIX["/backend/instances"]={configured:[],rows:[]};
b.FIX["/servers"]={servers:{},policy:{}};
const ANON={open:false,login_url:"/api/login"},IN={open:false,login_url:"/api/login",user:"ann",until:9,via:"token",grants:[{cap:"admin",scope:"*"}]};
// вход окном модуля на странице с этим query; куда страница ушла
async function login(search,mode){
  b.FIX["/session"]=ANON;
  const w=b.boot({url:"http://localhost/"+search});
  const f0=w.fetch;
  w.fetch=(u,i)=>{const m=(i&&i.method)||"GET";
    if(m==="POST"&&(u==="/api/login"||u==="/session/break-glass")){b.FIX["/session"]=IN;return Promise.resolve({ok:true,status:200,json:()=>Promise.resolve({token:"t"})})}
    if(m==="POST"&&u==="/session")return Promise.resolve({ok:true,status:200,json:()=>Promise.resolve({})});
    return f0(u,i)};
  await b.ready(300);
  const d=w.document,f=d.querySelector(mode==="glass"?".pc-glass-f":".pc-login-f");
  f.dispatchEvent(new w.Event("submit",{cancelable:true}));
  await b.ready(300);
  return w.__went;
}
const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
(async()=>{
const out={};
out.mounted=same(await login("?return=/backend/"),["/backend/"]);
out.root=same(await login("?return=/testsub/"),["/testsub/"]);
out.glass=same(await login("?return=/backend/","glass"),["/backend/"]);
out.percentSlash=same(await login("?return=%2Fbackend%2F"),["/backend/"]);
out.outsideCatalog=same(await login("?return=/nosuch/"),["/"]);
out.absolute=same(await login("?return=https://evil.example/"),["/"]);
out.schemeRelative=same(await login("?return=//evil/"),["/"]);
out.percentDots=same(await login("?return=/%2e%2e/"),["/"]);
out.dots=same(await login("?return=/backend/../"),["/"]);
out.noSlash=same(await login("?return=/backend"),["/"]);
out.tail=same(await login("?return=/backend/x"),["/"]);
out.repeated=same(await login("?return=/backend/&return=/testsub/"),["/"]);
out.empty=same(await login("?return="),["/"]);
out.noParameter=same(await login(""),[]);
b.report(out);
process.exit(0);
})();
