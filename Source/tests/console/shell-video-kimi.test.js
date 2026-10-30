// Вкладка «Видео» по дополнению Kimi к V/08 (канон cam.shell.html): строка раздачи после 409 exists (V/08.3 Н4) — без labels
// это локальная сеть, зритель «извне» слышит «раздачу создали для другой сети», непрочитанная строка — «метки раздачи не
// прочитаны», живое не начинается; манифест rec без places — запросов мест нет (V/08.2); лента живого — по occurred;
// /events с withheld — «скрыто правами: события N единиц» на шкале и в ленте (V/08.2 Н1.3).
const fs=require("fs"),path=require("path");
const PAGE=fs.readFileSync(path.join(__dirname,"..","..","..","VMS","01-cam","cam.shell.html"),"utf8");
const MOD=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"shell-vidk-"+process.pid+".html");
fs.writeFileSync(TMP,PAGE.replace(/<script src="\/platform\/console\.js\?v=1"><\/script>/,()=>`<script>${MOD}</script>`).replace('{lang:"ru",','{lang:"ru",poll_s:0.4,'));
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
const now=Date.now()/1000;
b.FIX["/session"]={open:true};
b.FIX["/manifest"]={name:"cam",rows:"cameras",id:"numeric",fields:[{name:"name",type:"string"}]};
// rec без places: мест у записи нет, страница их не спрашивает
b.FIX["/mounts"]={root:"cam",mounts:{rec:{name:"rec",rows:"recordings",id:"name",about:{sub:"cam",field:"cam"},fields:[{name:"cam",type:"string"}]},live:{name:"live",rows:"streams",id:"cam",about:{sub:"cam",field:"cam"},fields:[{name:"cam",type:"string"}]}}};
b.FIX["/rec/recordings"]={configured:[{id:"1",cam:"1",home:"main"}],rows:[]};
b.FIX["/rec/keeps"]={keeps:[]};
b.FIX["/cameras"]={configured:[{id:1,name:"ворота"}],rows:[{id:1,worker:"w-1",phase:"running"}]};
b.FIX["/servers"]={servers:{},policy:{}};
const EV={t:now-100,occurred:now-400,kind:"motion",subsystem:"cam",unit:"1",id:"e1"};
b.FIX["/events"]={events:[EV],state:"live",withheld:["det/9","rec/4"]};
(async()=>{
const w=b.boot();const errs=[];w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
w.HTMLMediaElement.prototype.play=function(){return Promise.resolve()};
const calls=[];let streamsRow="none";   // "none" — строки нет; "fail" — GET /live/streams падает
const R=(status,body,hdr)=>({status,ok:status<300,headers:{get:k=>hdr[k]??null},json:()=>Promise.resolve(body),text:()=>Promise.resolve(typeof body==="string"?body:JSON.stringify(body)),clone:()=>R(status,body,hdr)});
const J=(status,body,hdr={})=>Promise.resolve(R(status,body,hdr));
const f0=w.fetch;w.fetch=(u,i)=>{const s=String(u),m=(i||{}).method||"GET";calls.push([m,s]);
  if(s==="/rec/where/1")return J(200,{door:{url:"http://box-a:9001",token:"A1",expires:Date.now()/1000+120,routes:["timeline","segment"]}});
  if(/^http:\/\/box-a:9001\/timeline\//.test(s))return J(200,{spans:[],unreachable:[],unavailable:[]});
  if(s==="/live/streams"&&m==="POST")return J(409,{error:"exists"});
  if(s==="/live/streams"&&m==="GET"){if(streamsRow==="fail")return J(503,{error:"unavailable"});return J(200,{configured:streamsRow==="none"?[]:[streamsRow],rows:[]})}
  if(s==="/live/where/1")return J(200,{door:{url:"http://gw-1:9002",token:"L",expires:Date.now()/1000+120,routes:["whep"]}});
  if(s.startsWith("http://gw-1:9002/whep/session/"))return J(200,{});
  if(s.startsWith("http://gw-1:9002/whep/1"))return J(201,"v=0",{Location:"/whep/session/s1"});
  return f0(u,i)};
w.RTCPeerConnection=function(){this.addTransceiver=()=>{};this.createOffer=async()=>({sdp:"v=0"});this.setLocalDescription=async d=>{this.localDescription=d};this.setRemoteDescription=async()=>{};this.close=()=>{this.closed=true};this.connectionState="connected"};
await b.ready(600);await w.platformConsole.ready;await w.eval("reloadRec()");const d=w.document,pc=w.platformConsole,out={};
const main=()=>d.querySelector("main");
pc.select("unit:cam/1");await b.ready(80);
main().querySelector('.pc-tabs [data-tab="vid"]').click();await b.ready(300);
// (8) манифест rec без places: ни таблицы мест, ни дверей мест — только дверь самой записи
out.noPlacesNoAsks=calls.some(([,u])=>u==="/rec/where/1")&&!calls.some(([,u])=>/^\/rec\/where\/[^/]+\/[^?]+\?unit=/.test(u))&&
  !calls.some(([m,u])=>m==="GET"&&/^\/rec\/(volumes|disks|undefined)$/.test(u));
// (10) withheld — названо на шкале
const evText=()=>main().querySelector("#events").textContent;
out.withheldOnTimeline=/скрыто правами: события 2 единиц/.test(evText());
// (4) 409 exists, строка раздачи без labels (локальная сеть), зритель «извне», права на перенос нет — сказано, живого нет
pc.may=()=>false;
streamsRow={id:"1"};const net=main().querySelector('[data-act="net"]');net.value="outside";net.dispatchEvent(new w.Event("change",{bubbles:true}));
const caps=[];const cap=()=>caps.join(" | ");
const watchCap=()=>{caps.length=0;const t=setInterval(()=>{const el=main().querySelector("#playing");if(el&&!caps.includes(el.textContent))caps.push(el.textContent)},5);return()=>clearInterval(t)};
let stop=watchCap();calls.length=0;main().querySelector("#liveBtn").click();await b.ready(400);stop();
out.otherNetworkSaid=/раздачу создали для другой сети/.test(cap())&&!w.eval("V.live")&&!calls.some(([m,u])=>m==="POST"&&/\/whep\//.test(u))&&!calls.some(([m])=>m==="PUT");
// строки раздачи не прочесть — метки не проверяются молча: сказано, живого нет
streamsRow="fail";net.value="local";net.dispatchEvent(new w.Event("change",{bubbles:true}));
stop=watchCap();calls.length=0;main().querySelector("#liveBtn").click();await b.ready(400);stop();
out.labelsUnreadSaid=/метки раздачи не прочитаны/.test(cap())&&!w.eval("V.live")&&!calls.some(([m,u])=>m==="POST"&&/\/whep\//.test(u));
// строка есть, сеть та же (локальная, без labels) — живое идёт; лента — по occurred, withheld — в её первой строке
streamsRow={id:"1"};
main().querySelector("#liveBtn").click();await b.ready(1200);
out.liveGoesOn=!!w.eval("V.live");
const feed=()=>main().querySelector("#livefeed");
const at=w.eval(`fmtHMS(${EV.occurred})`),written=w.eval(`fmtHMS(${EV.t})`);
const line=[...feed().querySelectorAll(".ev")].find(x=>/motion|движ/i.test(x.textContent));
out.liveFeedByOccurred=!!line&&line.textContent.includes(at)&&!line.textContent.includes(written);
out.withheldInFeed=/скрыто правами: события 2 единиц/.test(feed().firstChild.textContent);
w.eval("stopLive()");await b.ready(40);
out.errors=errs;
b.report(out,["errors"]);
try{fs.unlinkSync(TMP)}catch(e){}
process.exit(0);
})();
