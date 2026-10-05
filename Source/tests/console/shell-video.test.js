// Вкладка «Видео» страницы VMS курса — байты только через двери (решение владельца, без исключений). Шкала: дверь каждой
// записи камеры (/rec/where/<запись>) и двери мест из таблицы, которую называет спека rec (places.table: /rec/where/
// volumes/<том>?unit=rec/<запись>); близнецы сливаются, своя дверь записи впереди; том без держателя назван
// (X-Unreachable), «нет такого места» пропущен. Кусок — …/e<эпоха>/<from>-<to>.<source>.mp4 с ?t=. Участок с yields и
// участок резервной записи уступают основным; остаток резервной — «только в резервном», «Закрепить» — заявка основной
// записи (POST /rec/requests). Живое: первый зритель заводит поток (POST /live/streams; 409 exists — дальше), offer на
// дверь шлюза (404/503 — повтор, 401 — where заново), трубка — DELETE на двери со свежим токеном. Отметка через
// console.api; опрос не трогает плеер; выбор другого объекта кладёт трубку. (По образцу продуктового shell-video.)
const fs=require("fs"),path=require("path");
const PAGE=fs.readFileSync(path.join(__dirname,"..","..","vms","shell.html"),"utf8");
const MOD=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"shell-vid-"+process.pid+".html");
fs.writeFileSync(TMP,PAGE.replace(/<script src="\/platform\/console\.js\?v=1"><\/script>/,()=>`<script>${MOD}</script>`).replace('{lang:"ru",','{lang:"ru",poll_s:0.4,'));
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
const now=Date.now()/1000,ms=x=>Math.round(x*1000);
b.FIX["/session"]={open:true};
b.FIX["/spec"]={name:"vms",rows:"cameras",id:"numeric",fields:[{name:"name",type:"string"}],display:{kinds:{"camera.footage.lost":"камера потеряла запись"}}};
// таблица мест — не «volumes»: страница берёт её имя из спеки rec, а не пишет сама
b.FIX["/mounts"]={root:"vms",mounts:{rec:{name:"rec",rows:"recordings",id:"name",about:{sub:"vms",field:"cam"},places:{table:"disks"},fields:[{name:"cam",type:"string"}]},live:{name:"live",rows:"streams",id:"cam",about:{sub:"vms",field:"cam"},fields:[{name:"cam",type:"string"}]}}};
b.FIX["/rec/recordings"]={configured:[{id:"1",cam:"1",home:"main"},{id:"1-b",cam:"1",home:"card"}],rows:[]};
b.FIX["/rec/disks"]={disks:[{name:"main",kind:"local",server:"box-a"},{name:"old",kind:"local",server:"box-b"},{name:"gone",kind:"local",server:"box-c"},{name:"card",kind:"backup",server:"cam-a"}]};
b.FIX["/rec/keeps"]={keeps:[]};
b.FIX["/live/streams"]={configured:[],rows:[]};
b.FIX["/cameras"]={configured:[{id:1,name:"ворота"},{id:2,name:"двор"}],rows:[{id:1,worker:"w-1",phase:"running"}]};
b.FIX["/servers"]={servers:{},policy:{}};
b.FIX["/events"]={events:[{t:now-500,kind:"camera.footage.lost",subsystem:"vms",unit:"1",epoch:3,lost_s:20}],state:"live"};
(async()=>{
const w=b.boot();const errs=[];w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
w.HTMLMediaElement.prototype.play=function(){return Promise.resolve()};
// двери: запись 1 — box-a; её прежний том old — box-b; том gone без держателя; запись 1-b (резервная, на карте) — cam-a
const DOOR=(url,token)=>({door:{url,token,expires:Date.now()/1000+120,routes:["timeline","segment"]}});
const TL={
  "http://box-a:9001":[{start_ms:ms(now-600),end_ms:ms(now-300),epoch:3},{start_ms:ms(now-90),end_ms:ms(now-60),epoch:3,source:"backfill"}],
  "http://box-b:9001":[{start_ms:ms(now-900),end_ms:ms(now-700),epoch:2},{start_ms:ms(now-600),end_ms:ms(now-300),epoch:3}],   // второй — близнец: уже есть у своей двери
  "http://cam-a:9001":[{start_ms:ms(now-650),end_ms:ms(now-250),epoch:0,source:"device",yields:true}],
};
const asked=[];let liveTokens=0,whep=[],live404=1,live401=0,door401=0,streamsPost=0;const calls=[];
const J=(status,body,hdr={})=>Promise.resolve({status,ok:status<300,headers:{get:k=>hdr[k]??null},json:()=>Promise.resolve(body),text:()=>Promise.resolve(typeof body==="string"?body:JSON.stringify(body))});
const f0=w.fetch;w.fetch=(u,i)=>{const s=String(u),auth=((i||{}).headers||{}).Authorization||"",m=(i||{}).method||"GET";calls.push([m,s,auth]);
  if(s==="/rec/where/1")return J(200,DOOR("http://box-a:9001/","A1"));
  if(s==="/rec/where/1-b")return J(200,DOOR("http://cam-a:9001","C1"));
  if(s.startsWith("/rec/where/disks/old?"))return J(200,DOOR("http://box-b:9001","B1"));
  if(s.startsWith("/rec/where/disks/gone?"))return J(404,{worker:null,place:"gone",server:"box-c",door:null,unreachable:"gone@box-c"},{"X-Unreachable":"gone@box-c"});
  if(s.startsWith("/rec/where/"))return J(404,{error:"no such place"});
  const host=s.match(/^https?:\/\/[^/]+/);
  if(host&&/\/timeline\//.test(s)){if(door401&&host[0]==="http://box-a:9001"){door401--;return J(401,{error:"door",reason:"expired"})}return J(200,TL[host[0]]||[])}
  if(s==="/live/where/1"){liveTokens++;return J(200,{door:{url:"http://gw-1:9002",token:"L"+liveTokens,expires:Date.now()/1000+120,routes:["whep"]}})}
  if(s==="http://gw-1:9002/whep/1"){whep.push(auth);if(live404){live404--;return J(404,{error:"no such stream"})}if(live401){live401--;return J(401,{error:"door",reason:"expired"})}return J(201,"v=0",{Location:"/whep/session/s1"})}
  if(s.startsWith("http://gw-1:9002/whep/session/"))return J(200,{});
  if(s==="/live/streams"&&m==="POST"){streamsPost++;return streamsPost>1?J(409,{error:"exists"}):J(201,{id:"1"})}
  if(s==="/rec/requests"&&m==="POST"){asked.push(JSON.parse(i.body));return J(202,{queued:{id:"x"}})}
  return f0(u,i)};
w.RTCPeerConnection=function(){this.addTransceiver=()=>{};this.createOffer=async()=>({sdp:"v=0"});this.setLocalDescription=async d=>{this.localDescription=d};this.setRemoteDescription=async()=>{};this.close=()=>{this.closed=true};this.connectionState="connected"};
await b.ready(600);await w.platformConsole.ready;await w.eval("reloadRec()");const d=w.document,pc=w.platformConsole,out={};
const main=()=>d.querySelector("main");
pc.select("unit:vms/1");await b.ready(80);
main().querySelector('.pc-tabs [data-tab="vid"]').click();await b.ready(250);
out.tabShown=!!main().querySelector("#timeline")&&!!main().querySelector("video");
// шкала — только двери: запись, её прежний том, резервная запись; консольного /timeline нет
out.noConsoleTimeline=!calls.some(([,u])=>/^\/timeline\//.test(u))&&!calls.some(([,u])=>/^\/segment\//.test(u));
out.doorsAsked=calls.some(([,u,a])=>u.startsWith("http://box-a:9001/timeline/1?")&&a==="Bearer A1")&&calls.some(([,u,a])=>u.startsWith("http://box-b:9001/timeline/1?")&&a==="Bearer B1")&&calls.some(([,u])=>u.startsWith("/rec/where/disks/old?unit=rec%2F1"));
out.placesFromSpec=!calls.some(([,u])=>/\/volumes/.test(u));
const spans=JSON.parse(w.eval("JSON.stringify(V.spans.map(s=>({a:Math.round(s.start-"+now+"),z:Math.round(s.end-"+now+"),r:s.recording,src:s.source,y:!!s.yields,bk:!!s.backupOnly})))"));
out.twinMerged=spans.filter(s=>s.r==="1"&&s.a===-600&&s.z===-300).length===1&&spans.some(s=>s.r==="1"&&s.a===-900&&s.z===-700);
// участок устройства на резервной записи уступает основной: видны только непокрытые края
const bk=spans.filter(s=>s.r==="1-b").map(s=>[s.a,s.z]).sort((x,y)=>x[0]-y[0]);
out.backupYields=JSON.stringify(bk)==="[[-650,-600],[-300,-250]]"&&spans.filter(s=>s.r==="1-b").every(s=>s.bk);
out.backupOnlyLine=/только в резервном/.test(main().querySelector("#devline").textContent)&&!!main().querySelector("#timeline .span.backup");
out.unreachableNamed=/Недоступно: gone@box-c/.test(main().querySelector("#tlnote").textContent);
out.eventTickInWords=/камера потеряла запись/.test(main().querySelector("#timeline .tick").title);
out.eventNoteInWords=/потеряно 20 с записи на карте камеры/.test(main().querySelector("#events").textContent);
// «Закрепить»: по заявке основной записи на каждый диапазон — через console.api
calls.length=0;
main().querySelector('#devline [data-act="pin"]').click();await b.ready(80);
const pins=calls.filter(([m,u])=>m==="POST"&&u==="/rec/requests");
out.pinAsksPrimary=pins.length===2&&asked.every(x=>x.unit==="rec/1"&&x.to>x.from&&Object.keys(x).length===3);
// кусок: дверь, с которой пришёл участок; суффикс источника; токен в ?t=
w.eval("play(V.spans.findIndex(s=>s.recording==='1'&&s.source===''&&Math.round(s.start-"+now+")===-600))");await b.ready(40);
out.pieceViaDoor=main().querySelector("video").src===`http://box-a:9001/segment/1/e3/${ms(now-600)}-${ms(now-540)}.mp4?t=A1`&&main().querySelector("video").crossOrigin==="anonymous";
w.eval("play(V.spans.findIndex(s=>s.source==='backfill'))");await b.ready(40);
out.backfillSuffix=/\/segment\/1\/e3\/\d+-\d+\.backfill\.mp4\?t=A1$/.test(main().querySelector("video").src);
w.eval("play(V.spans.findIndex(s=>s.source==='device'))");await b.ready(40);
out.deviceSuffix=/^http:\/\/cam-a:9001\/segment\/1-b\/e0\/\d+-\d+\.device\.mp4\?t=C1$/.test(main().querySelector("video").src);
out.oldVolumePiece=(w.eval("play(V.spans.findIndex(s=>Math.round(s.start-"+now+")===-900))"),await b.ready(40),/^http:\/\/box-b:9001\/segment\/1\/e2\//.test(main().querySelector("video").src));
// клик по событию — проигрывание с его момента (обработчик навешан кодом, не атрибутом)
const li=main().querySelector("#events li[data-t]");
out.eventClickSeeks=!!li&&!li.hasAttribute("onclick");
// 401 от двери записи: where заново, повтор
door401=1;calls.length=0;await w.eval("loadTimeline('1')");await b.ready(80);
out.renewOn401=calls.filter(([,u])=>u.startsWith("http://box-a:9001/timeline/1")).length===2&&calls.filter(([,u])=>u==="/rec/where/1").length>=2;
// живое: первый зритель заводит поток, ждёт место (404), offer на дверь шлюза с Bearer
calls.length=0;main().querySelector("#liveBtn").click();await b.ready(2200);
out.firstViewerMakesStream=calls.some(([m,u])=>m==="POST"&&u==="/live/streams")&&!calls.some(([,u])=>/^\/whep\//.test(u));
out.offerAtDoor=whep.length===2&&whep.every(a=>/^Bearer L\d$/.test(a))&&/живое/.test(main().querySelector("#playing").textContent);
// опрос не перерисовывает карточку, пока идёт просмотр
const video=main().querySelector("video");await b.ready(900);
out.pollLeavesPlayerAlone=main().querySelector("video")===video;
// трубка — DELETE на двери шлюза
calls.length=0;w.eval("stopLive()");await b.ready(60);
out.hangUpAtDoor=calls.some(([m,u,a])=>m==="DELETE"&&u==="http://gw-1:9002/whep/session/s1"&&/^Bearer L\d$/.test(a));
// второй зритель: поток уже есть (409 exists) — дальше; 401 у шлюза — where заново, один раз
live401=1;whep=[];const lt=liveTokens;main().querySelector("#liveBtn").click();await b.ready(400);
out.existsGoesOn=streamsPost===2&&whep.length===2&&liveTokens===lt+1&&!!w.eval("V.live");
// отметка — через console.api с ключом
const mk=main().querySelector("#markForm");mk.elements.note.value="видел";let n=w.__calls.length;
mk.dispatchEvent(new w.Event("submit",{cancelable:true}));await b.ready(80);
const c=w.__calls.slice(n).find(x=>x.path==="/marks");
out.markViaApi=!!c&&c.body.note==="видел"&&c.body.unit==="vms/1"&&!("cam" in c.body)&&!!c.key;
// другой объект — трубка положена
pc.select("unit:vms/2");await b.ready(80);
out.hangsUpOnSelect=w.eval("V.live")===null;
// участок, записанный самой камерой (yields), уступает регистратору
const cut=w.eval(`JSON.stringify(yieldCut([{start:100,end:200},{start:50,end:300,yields:true},{start:400,end:500,yields:true}]).map(s=>[s.start,s.end,!!s.yields]).sort((a,b)=>a[0]-b[0]))`);
out.yieldsCut=cut==='[[50,100,true],[100,200,false],[200,300,true],[400,500,true]]';
// каждый момент — один раз (урок 24 М10B): перекрытое не ставится дважды, отсечённый спан — только если щёлкнули его;
// с момента t — куски, кончающиеся после него, первый — со смещением внутрь
out.eachMomentOnce=w.eval(`(()=>{const keep=V.spans;V.spans=[{start:0,end:120,media:1},{start:60,end:200,media:1},{start:100,end:150,media:1,fenced:true}];
  const r=JSON.stringify(piecesFrom(0,90).map(p=>[p.i,p.start,p.end,p.off]))+JSON.stringify(piecesFrom(2,0).map(p=>[p.i,p.start,p.end]));V.spans=keep;return r})()`)==="[[0,60,120,30],[1,120,180,0],[1,180,200,0]][[2,100,150]]";
out.errors=errs;
b.report(out,["errors"]);
try{fs.unlinkSync(TMP)}catch(e){}
process.exit(0);
})();
