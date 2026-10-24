// Вызовы модуля для страницы (P/07 Н1.5; ADR-0091 доп. (22), (24), (25), (27)): PlatformConsole.features, обещание
// pc.ready — после mount и первого прочитанного /manifest, при 401 — после входа; select(ref, {tab}) — вкладка по id из
// addTab, нет такой — карточка без смены вкладки; card.closed {ref} — при смене выбора, снятии выбора, уходе со страницы,
// и у карточки оболочки (её ref как есть). Версия модуля — 1.
const fs=require("fs"),path=require("path"),{JSDOM}=require("jsdom");
const PAGE=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.html"),"utf8");
const MOD=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const HTML=PAGE.replace(/<script src="\/platform\/console\.js\?v=1"><\/script>/,()=>`<script>${MOD}</script>`)
  .replace('PlatformConsole.mount(app)','PlatformConsole.mount(app, { lang: "ru", poll_s: 1 })');
const MANIFEST={name:"testsub",rows:"things",id:"numeric",fields:[{name:"name",type:"string"}]};
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
// state: login — нужен ли вход (до него /manifest и /session отвечают как у закрытой консоли)
function boot(state){
  const dom=new JSDOM(HTML,{runScripts:"dangerously",url:"http://localhost/",beforeParse(w){
    w.matchMedia=()=>({matches:false,addListener(){},removeListener(){},addEventListener(){},removeEventListener(){}});
    w.requestAnimationFrame=cb=>setTimeout(cb,0);
    Object.defineProperty(w,"innerWidth",{value:1600,configurable:true});
    w.__log=[];
    const answer=(status,body)=>Promise.resolve({ok:status<300,status,headers:{get:()=>"application/json"},
      json:()=>Promise.resolve(body),text:()=>Promise.resolve(JSON.stringify(body)),clone(){return this}});
    w.fetch=(url,init)=>{
      const method=(init&&init.method)||"GET",p=String(url).split("?")[0].replace(/^https?:\/\/[^/]+/,"");
      w.__log.push(method+" "+p);
      if(p==="/session"&&method==="GET")return answer(200,state.login?{open:false,login_url:"/api/login"}:{open:false,login_url:"/api/login",user:"a",until:0,via:"token",grants:[{cap:"admin",scope:"*"}]});
      if(p==="/api/login"&&method==="POST")return answer(200,{token:"t"});
      if(p==="/session"&&method==="POST"){state.login=false;return answer(200,{user:"a",until:0});}
      if(state.login)return answer(401,{error:"denied",detail:"who are you"});
      if(p==="/manifest")return answer(200,MANIFEST);
      if(p==="/things")return answer(200,{configured:[{id:1,name:"one"},{id:2,name:"two"}],rows:[]});
      return answer(404,{error:"not found"});
    };
  }});
  return dom.window;
}
const settled=(p,ms)=>Promise.race([p.then(()=>true),sleep(ms).then(()=>false)]);
(async()=>{
  const out={},errs=[];
  // 1. открытый вход: features, ready после /manifest, select с вкладкой и без, card.closed
  {
    const w=boot({login:false});w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
    await sleep(50);const pc=w.platformConsole,d=w.document;
    out.version1=w.PlatformConsole.version===1;
    out.featuresList=Array.isArray(w.PlatformConsole.features)&&["select.tab","card.closed"].every(x=>w.PlatformConsole.features.includes(x));
    out.readyIsPromise=pc.ready instanceof w.Promise||typeof pc.ready.then==="function";
    out.readyAfterManifest=await settled(pc.ready,2000)&&w.__log.includes("GET /manifest");
    out.readyGivesModule=(await pc.ready)===pc;
    const closed=[];pc.on("card.closed",e=>closed.push(e&&e.ref));
    pc.addTab("unit",{id:"logs",label:"Журнал",render:host=>{host.innerHTML='<p class="lg">журнал</p>'}});
    pc.addCard("streamaccounts",(host,ref)=>{host.innerHTML=`<h1>${ref}</h1>`});
    const cur=()=>{const b=d.querySelector(".pc-tabs button.on");return b&&b.dataset.tab};
    pc.select("unit:testsub/1",{tab:"logs"});await sleep(30);
    out.selectOpensTab=cur()==="logs"&&!!d.querySelector('.pc-tab[data-tab="logs"]:not([hidden]) .lg');
    pc.select("unit:testsub/2");await sleep(30);
    out.selectWithoutTabKeepsTab=cur()==="logs";
    out.closedOnSelectionChange=closed.length===1&&closed[0]==="unit:testsub/1";
    pc.select("unit:testsub/1",{tab:"nosuch"});await sleep(30);
    out.unknownTabKeepsTab=cur()==="logs"&&pc.selected()==="unit:testsub/1";
    pc.select("unit:testsub/1",{tab:"general"});await sleep(30);
    out.generalTab=cur()==="general";
    pc.select("streamaccounts:local");await sleep(30);
    out.shellCardDrawn=/streamaccounts:local/.test(d.querySelector(".pc-hd").textContent+d.querySelector(".pc-main").textContent);
    pc.select("unit:testsub/2");await sleep(30);
    out.closedForShellCard=closed.includes("streamaccounts:local");
    const before=closed.length;await pc.refresh();await sleep(30);
    out.noClosedOnPoll=closed.length===before;
    const sec=[...d.querySelectorAll("[data-sec]")].find(x=>x.dataset.sec&&x.dataset.sec!=="units");
    if(sec){sec.click();await sleep(30);out.closedOnDeselect=closed[closed.length-1]==="unit:testsub/2";}
    else{pc.select("unit:testsub/1");await sleep(30);out.closedOnDeselect=closed[closed.length-1]==="unit:testsub/2";}
    pc.select("unit:testsub/1");await sleep(30);
    const n=closed.length;w.dispatchEvent(new w.Event("pagehide"));
    out.closedOnPageLeave=closed.length===n+1&&closed[n]==="unit:testsub/1";
    w.close();
  }
  // 2. 401: обещание ждёт входа и разрешается после него
  {
    const state={login:true};const w=boot(state);w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
    await sleep(50);const pc=w.platformConsole,d=w.document;
    out.notReadyBefore401Login=!await settled(pc.ready,1500);
    out.loginShown=!d.querySelector(".pc-login").hidden;
    const f=d.querySelector(".pc-login-f");f.elements.user.value="a";f.elements.password.value="secret-password";
    f.requestSubmit();
    out.readyAfterLogin=await settled(pc.ready,2000);
    out.manifestReadAfterLogin=w.__log.filter(x=>x==="GET /manifest").length>=2;
    w.close();
  }
  out.errors=errs;out.noErrors=!errs.length;
  const bad=Object.entries(out).filter(([k,v])=>k!=="errors"&&v!==true);
  console.log(JSON.stringify(out,null,1));
  console.log(bad.length?"FAILED: "+bad.map(([k])=>k).join(", "):"все проверки пройдены");
  process.exit(0);
})();
