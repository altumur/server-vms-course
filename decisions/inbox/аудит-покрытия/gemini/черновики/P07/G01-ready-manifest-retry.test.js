// Черновик G01 (P/07 Н1.5 ready): если /manifest при монтировании не прочитан (сеть, 5xx),
// обещание pc.ready ждёт, а модуль перечитывает /manifest следующим опросом (poll_s) и разрешает pc.ready после успеха.
const fs=require("fs"),path=require("path"),{JSDOM}=require("jsdom");
const PAGE=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.html"),"utf8");
const MOD=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const HTML=PAGE.replace(/<script src="\/platform\/console\.js\?v=1"><\/script>/,()=>`<script>${MOD}</script>`)
  .replace('PlatformConsole.mount(app)','PlatformConsole.mount(app, { lang: "ru", poll_s: 0.25 })');
const MANIFEST={name:"testsub",rows:"things",id:"numeric",fields:[{name:"name",type:"string"}]};
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const settled=(p,ms)=>Promise.race([p.then(()=>true),sleep(ms).then(()=>false)]);

function boot(manifestPlan){
  const dom=new JSDOM(HTML,{runScripts:"dangerously",url:"http://localhost/",beforeParse(w){
    w.matchMedia=()=>({matches:false,addListener(){},removeListener(){},addEventListener(){},removeEventListener(){}});
    w.requestAnimationFrame=cb=>setTimeout(cb,0);
    w.__manifestCalls=0;
    const answer=(status,body)=>Promise.resolve({ok:status<300,status,headers:{get:()=>"application/json"},
      json:()=>Promise.resolve(body),text:()=>Promise.resolve(JSON.stringify(body)),clone(){return this}});
    w.fetch=(url,init)=>{
      const method=(init&&init.method)||"GET",p=String(url).split("?")[0].replace(/^https?:\/\/[^/]+/,"");
      if(p==="/session")return answer(200,{open:true});
      if(p==="/manifest"){
        w.__manifestCalls++;
        const step=manifestPlan.shift();
        if(step==="net")return Promise.reject(new TypeError("Failed to fetch"));
        if(step===503)return answer(503,{error:"unavailable"});
        return answer(200,MANIFEST);
      }
      if(p==="/things")return answer(200,{configured:[{id:1,name:"one"}],rows:[]});
      return answer(200,{});
    };
  }});
  return dom.window;
}

(async()=>{
  const out={},errs=[];
  const w=boot(["net",503,200]);
  w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
  await sleep(60);
  const pc=w.platformConsole;
  // Пока /manifest вернул сетевую ошибку и 503, pc.ready не разрешается
  out.notReadyOnManifestFailure=!await settled(pc.ready,120);
  // На следующем опросе (poll_s = 0.25 с) модуль перечитывает /manifest и разрешает pc.ready
  out.readyAfterPollRetry=await settled(pc.ready,1500);
  out.manifestRetried=w.__manifestCalls>=3;
  w.close();
  out.errors=errs;out.noErrors=!errs.length;
  console.log(JSON.stringify(out,null,1));
  process.exit(Object.entries(out).some(([k,v])=>k!=="errors"&&v!==true)?1:0);
})();
