// Записи камеры в других кластерах домена (ADR-0061): консоль кластера камеры (член) узнаёт их из книги, которую
// несёт домен (GET /domain/vms/books/primaries — только recorded_by и recording), и спрашивает дверь записи у консоли
// того кластера через себя: GET /domain/at/<кластер>/rec/where/<запись>. Кусок — с двери держателя напрямую, мимо
// обеих консолей. Отказ того кластера — словами: 403 «на … вас не знают», 502 «консоль … не видна по сети».
// Копия продуктового vmsworker/vms/consoletest/shell-far-recordings.test.js (другое здесь — путь страницы); в курсе
// книга — источник и у кластера держателя домена: /domain/vms/state курс не отдаёт.
const fs=require("fs"),path=require("path");
const PAGE=fs.readFileSync(path.join(__dirname,"..","..","vms","vms.shell.html"),"utf8");
const MOD=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"shell-far-"+process.pid+".html");
fs.writeFileSync(TMP,PAGE.replace(/<script src="\/platform\/console\.js\?v=1"><\/script>/,()=>`<script>${MOD}</script>`).replace('{lang:"ru",','{lang:"ru",poll_s:0,'));
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
const now=Date.now()/1000,ms=x=>Math.round(x*1000);
b.FIX["/session"]={open:true};
b.FIX["/spec"]={name:"vms",rows:"cameras",id:"numeric",fields:[{name:"name",type:"string"}]};
b.FIX["/mounts"]={root:"vms",mounts:{rec:{name:"rec",rows:"recordings",id:"name",about:{sub:"vms",field:"cam"},places:{table:"volumes"},fields:[{name:"cam",type:"string"}]}}};
b.FIX["/cameras"]={configured:[{id:1,name:"demo",ref:"SN-DEMO"},{id:2,name:"x",ref:"SN-X"},{id:3,name:"y",ref:"SN-Y"},{id:4,name:"own",ref:"SN-OWN"},{id:5,name:"z",ref:"SN-Z"}],rows:[{id:1,worker:"w-1",phase:"running"}]};
b.FIX["/rec/recordings"]={configured:[{id:"1-card",cam:"1",home:"card",backup:true},{id:"SN-OWN",cam:"4",home:"card"}],rows:[]};
b.FIX["/rec/volumes"]={volumes:[{name:"card",kind:"backup",server:"cam-demo",held_by:"r-1"}]};
b.FIX["/servers"]={servers:{},policy:{}};
b.FIX["/events"]={events:[],state:"live"};
// член: вида домена нет (404), книга primaries — кто пишет камеры
b.FIX["/domain/vms/books/primaries"]={"SN-DEMO":{recorded_by:"relay-b",recording:"SN-DEMO"},"SN-X":{recorded_by:"relay-x",recording:"SN-X"},"SN-Y":{recorded_by:"relay-y",recording:"SN-Y"},"SN-OWN":{recorded_by:"cam-demo",recording:"SN-OWN"},"SN-Z":{recorded_by:"relay-z",recording:"SN-Z"}};
(async()=>{
const w=b.boot();const errs=[];w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
const calls=[];
const J=(status,body,hdr={})=>Promise.resolve({status,ok:status<300,headers:{get:k=>hdr[k]??null},json:()=>Promise.resolve(body),text:()=>Promise.resolve(JSON.stringify(body))});
const f0=w.fetch;w.fetch=(u,i)=>{const s=String(u),auth=((i||{}).headers||{}).Authorization||"";calls.push([s,auth]);
  if(s==="/rec/where/1-card")return J(200,{door:{url:"http://cam-demo:9001",token:"C1",expires:now+120}});
  if(s.startsWith("http://cam-demo:9001/timeline/"))return J(200,[]);
  if(s==="/domain/at/relay-b/rec/where/SN-DEMO")return J(200,{door:{url:"http://relay-b:9101",token:"RB",expires:now+120}});
  if(s.startsWith("http://relay-b:9101/timeline/SN-DEMO"))return J(200,[{start_ms:ms(now-600),end_ms:ms(now-300),epoch:4}]);
  if(s==="/domain/at/relay-x/rec/where/SN-X")return J(403,{error:"refused",detail:"no grant names you"});
  if(s==="/domain/at/relay-y/rec/where/SN-Y")return J(502,{error:"the member did not answer"});
  if(s==="/domain/at/relay-z/rec/where/SN-Z")return J(503,{error:"the members' list does not read"});
  if(s.startsWith("/domain/at/cam-demo/"))return J(404,{error:"not another member"});
  return f0(u,i)};
await b.ready(600);await w.platformConsole.ready;await w.platformConsole.refresh();await b.ready(80);
const d=w.document,pc=w.platformConsole,out={};
const V=()=>w.eval("V");
await w.eval("loadTimeline('1')");await b.ready(80);
const sp=V().spans;
out.farRecordingOnTheTimeline=sp.some(s=>s.recording==="SN-DEMO"&&s.where==="/domain/at/relay-b/rec/where/SN-DEMO"&&Math.round(s.start-now)===-600);
out.askedThroughThisConsole=calls.some(([u])=>u==="/domain/at/relay-b/rec/where/SN-DEMO")&&calls.some(([u,a])=>u.startsWith("http://relay-b:9101/timeline/SN-DEMO")&&a==="Bearer RB");
out.primariesFromTheBook=calls.some(([u])=>u==="/domain/vms/books/primaries");
// кусок — с двери держателя relay-b напрямую
const url=await w.eval(`(()=>{const s=V.spans.find(x=>x.recording==="SN-DEMO");return segmentURL(s,{start:s.start,end:s.start+5})})()`);
out.pieceFromTheHoldersDoor=/^http:\/\/relay-b:9101\/segment\/SN-DEMO\/e4\//.test(String(url||""));
// отказы того кластера — словами
await w.eval("loadTimeline('2')");await b.ready(60);
out.forbiddenSaid=/на relay-x вас не знают: его архив не показан/.test(V().note);
await w.eval("loadTimeline('3')");await b.ready(60);
out.unreachableSaid=/консоль relay-y не видна по сети/.test(V().note);
// своя запись, названная книгой, своя и есть: через /domain/at не спрашивается
await w.eval("loadTimeline('4')");await b.ready(60);
out.ownRecordingNotAskedAcross=!calls.some(([u])=>u.startsWith("/domain/at/cam-demo/"))&&!/отсюда не известна/.test(V().note);
await w.eval("loadTimeline('5')");await b.ready(60);
out.membersListUnreadSaid=/список членов домена здесь не читается: архив relay-z не показан/.test(V().note);
out.errors=errs;out.noErrors=!errs.length;
b.report(out);
try{fs.unlinkSync(TMP)}catch(e){}
process.exit(0);
})();
