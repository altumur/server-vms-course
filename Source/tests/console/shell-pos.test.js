// POS, СКУД, звук на странице VMS (канон cam.shell.html): карточка единицы устройства и операция unit (V/08.1 Н1.5); титры из журнала
// в живом и архиве (V/08.3 Н1.2 п. 10, V/03.4 Н1.3); звук живого, muted при отказе автозапуска, разговор: кнопка на «Видео» и на
// карточке spk, порядок вызовов, busy, конец при уходе (V/08.3 Н1.2 пп. 8, 9); поле микрофона записи и audio_reason (V/02.1);
// запись с stream без минут устройства (V/08.2 Н1.2); repaintTree при смене детей (V/08.1 Н1.5); смена человека: двери, показанный
// пароль, таблицы детей.
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
const now=Math.floor(Date.now()/1000),ms=t=>t*1000;
b.FIX["/session"]={open:true,user:"ann"};
b.FIX["/manifest"]={name:"cam",rows:"cameras",id:"numeric",fields:[{name:"name",type:"string"}]};
b.FIX["/mounts"]={root:"cam",mounts:{rec:{name:"rec",rows:"recordings",id:"name",about:{sub:"cam",field:"cam"},fields:[{name:"cam",type:"string"}]},live:{name:"live",rows:"streams",id:"cam",about:{sub:"cam",field:"cam"},fields:[]},assist:{name:"assist",rows:"models",id:"name",fields:[]}}};
b.FIX["/rec/recordings"]={configured:[{id:"1",cam:"1",home:"main",audio:2},{id:"1-s",cam:"1",stream:"5",home:"main"}],rows:[{id:"1",worker:"r-1",phase:"running",audio_reason:"no mic 2"}]};
b.FIX["/rec/keeps"]={keeps:[]};
b.FIX["/rec/volumes"]={rows:[{name:"main",kind:"local"}]};
b.FIX["/cameras"]={configured:[{id:1,name:"ворота",type:"camera",units_down:{"2":"lost"}},{id:2,name:"двор",type:"camera"},{id:5,main:"1",profile:"sub"},
  {id:7,name:"касса",type:"eventsrc",camera:"1",overlay_delay_ms:0,overlay_duration_sec:0,words:[{msg:"sale",color:"red",bg:"yellow"}]}],rows:[{id:1,worker:"w-1",phase:"running",units_down:{"2":"lost"}}]};
b.FIX["/servers"]={servers:{},policy:{}};
const CH={children:[{name:"h-spk-3",camera:"1",device:"h",type:"spk",number:3},{name:"h-spk-9",camera:"1",device:"h",type:"spk",number:9},{name:"h-mic-1",camera:"1",device:"h",type:"mic",number:1}]};
const DU={device_units:[{name:"h-2",camera:"1",type:"acfa_lock",n:2,template:"lock",title:"Дверь склада",address:"10",enabled:true,revision:4}]};
for(const p of ["","/cam"]){b.FIX[p+"/children"]=CH;b.FIX[p+"/child_settings"]={child_settings:[]};b.FIX[p+"/device_units"]=DU}
const EVENTS={};let talkAnswers=[],talkDeleted=[];
(async()=>{
const w=b.boot(),errs=[];w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
const order=[],plays=[];let playRefusals=0;
w.HTMLMediaElement.prototype.play=function(){plays.push(this.muted);if(playRefusals>0){playRefusals--;return Promise.reject(new Error("NotAllowedError"))}return Promise.resolve()};
w.__peers=[];
w.RTCPeerConnection=function(){w.__peers.push(this);this.tr=[];this.addTransceiver=k=>this.tr.push(k);this.addTrack=t=>{this.track=t};this.createOffer=async()=>({sdp:"v=0"});this.setLocalDescription=async d=>{this.localDescription=d};this.setRemoteDescription=async()=>{};this.close=()=>{this.closed=true};this.connectionState="connected"};
const track={stopped:0,stop(){this.stopped++}};let micRefused=false;
Object.defineProperty(w.navigator,"mediaDevices",{value:{getUserMedia:async c=>{order.push("mic");if(micRefused)throw new Error("denied");return{getTracks:()=>[track],c}}},configurable:true});
const R=(status,body,hdr={})=>({status,ok:status<300,headers:{get:k=>hdr[k]??null},json:()=>Promise.resolve(body),text:()=>Promise.resolve(typeof body==="string"?body:JSON.stringify(body)),clone:()=>R(status,body,hdr)});
const J=(status,body,hdr)=>Promise.resolve(R(status,body,hdr));
const calls=[];const f0=w.fetch;
w.fetch=(u,i)=>{const s=String(u),m=(i||{}).method||"GET";calls.push([m,s,(i||{}).body]);
  if(s.startsWith("/events?")){const k=decodeURIComponent((s.match(/unit=([^&]+)/)||[])[1]||"");if(k in EVENTS)return EVENTS[k].status?J(EVENTS[k].status,{error:"denied"}):J(200,{events:EVENTS[k],state:"live"})}
  if(s==="/rec/where/1")return J(200,{door:{url:"http://box-a:9001",token:"A",expires:Date.now()/1000+120,routes:["timeline"]}});
  if(s==="/rec/where/1-s")return J(200,{door:{url:"http://box-s:9001",token:"S",expires:Date.now()/1000+120,routes:["timeline"]}});
  if(s.startsWith("/rec/where/"))return J(404,{error:"no such place"});
  if(s.startsWith("http://box-a:9001/timeline/"))return J(200,{spans:[],unreachable:[],unavailable:[]});
  if(s.startsWith("http://box-s:9001/timeline/"))return J(200,{spans:[{start_ms:ms(now-300),end_ms:ms(now-200),epoch:1}],unreachable:[],unavailable:[]});
  if(s==="/live/where/1"){order.push("where");return J(200,{door:{url:"http://gw:9002",token:"L",expires:Date.now()/1000+120,routes:["whep"]}})}
  if(s==="/live/streams"&&m==="POST"){order.push("streams");return J(409,{error:"exists"})}
  if(s==="/live/streams")return J(200,{rows:[],configured:[{id:"1",cam:"1"}]});
  if(/\/cam\/requests$|^\/requests$/.test(s)&&m==="POST"){order.push("request:"+i.body);return J(202,{queued:{id:"x"}})}
  if(s.startsWith("http://gw:9002/whep/1"))return J(201,"v=0",{Location:"/whep/session/v1"});
  if(s==="http://gw:9002/talk/1/3"){order.push("talk");const a=talkAnswers.shift();return a[0]===201?J(201,"v=0",{Location:"/talk/session/t1"}):J(a[0],a[1])}
  if(s.startsWith("http://gw:9002/talk/session/")&&m==="DELETE"){talkDeleted.push(s);return J(200,{})}
  if(s.startsWith("http://gw:9002/whep/session/"))return J(200,{});
  if(s==="/session/break-glass"&&m==="POST")return J(200,{ok:true});
  if(/device_units$/.test(s)&&m==="POST")return J(200,{revision:5});
  if(s.startsWith("/rec/recordings/")&&m==="PUT")return J(200,{revision:2});
  return f0(u,i)};
await b.ready(600);await w.platformConsole.ready;const pc=w.platformConsole,d=w.document,out={};
await w.eval("reloadRec()");await w.eval("readChildren()");await b.ready(60);
const main=()=>d.querySelector("main");const toast=()=>d.querySelector(".pc-toast").textContent;
// --- карточка единицы и операция unit
pc.select("dunit:h-2");await b.ready(120);
const uc=main().textContent,ucv=[...main().querySelectorAll("input")].map(x=>x.value);
out.unitCardShows=/Дверь склада/.test(uc)&&["Дверь","2","lock","ворота","корень","Дверь склада","10"].every(x=>ucv.includes(x));
out.unitDownInWords=/нет связи/.test(uc);
main().querySelector('[data-act="perform"]').click();await b.ready(60);
out.emptyOperationNoRequest=!order.some(x=>x.startsWith("request:"));
main().querySelector("#unitOp").value=" open ";main().querySelector('[data-act="perform"]').click();await b.ready(80);
out.unitOperationAsked=order.some(x=>x==='request:{"unit":"1","action":"unit","n":2,"operation":"open"}');
order.length=0;
main().querySelector("#unitTitle").value="Новая";main().querySelector('[data-act="save"]').click();await b.ready(100);
const saved=calls.filter(([m,u])=>m==="POST"&&/device_units$/.test(u)).map(x=>JSON.parse(x[2]));
out.unitSaveKeepsTheRow=saved.length===1&&saved[0].title==="Новая"&&saved[0].type==="acfa_lock"&&saved[0].n===2&&saved[0].template==="lock"&&saved[0].address==="10"&&saved[0].enabled===true&&!("revision" in saved[0]);
// --- живое: дорожка звука, autoplay
pc.select("unit:cam/1");await b.ready(80);main().querySelector('.pc-tabs [data-tab="vid"]').click();await b.ready(250);
main().querySelector("#liveBtn").click();await b.ready(300);
const peer=w.__peers[w.__peers.length-1];
out.audioTrackAsked=JSON.stringify(peer.tr)==='["video","audio"]';
const player=()=>main().querySelector("#player");
playRefusals=1;plays.length=0;peer.ontrack({streams:[{id:"s1"}]});await b.ready(30);
out.mutedWhenAutoplayRefused=player().muted===true&&JSON.stringify(plays)==="[false,true]";
playRefusals=0;plays.length=0;peer.ontrack({streams:[{id:"s2"}]});await b.ready(30);
out.soundWhenAutoplayAllowed=player().muted===false&&JSON.stringify(plays)==="[false]";
// --- титры: живое
const lineA={id:"t1",t:now,kind:"text",lines:["<b>чек</b>","итого 5"],word:"sale"},lineBad={id:"t2",t:now+1,kind:"text",lines:"строка"};
EVENTS["cam/7"]=[lineA,lineBad];
await w.eval("pollTitles('1')");await b.ready(40);
const tb=()=>main().querySelector("#titles");
out.titleIsTextNotMarkup=!!tb()&&tb().textContent==="<b>чек</b>\nитого 5"&&!tb().querySelector("b");
out.titleColours=!!tb().firstChild&&tb().firstChild.style.color==="red"&&tb().firstChild.style.background==="yellow";
out.badLineNoTitle=tb().textContent==="<b>чек</b>\nитого 5";
tb().textContent="";await w.eval("pollTitles('1')");await b.ready(40);
out.titleOnce=tb().textContent==="";
EVENTS["cam/7"]={status:403};await w.eval("pollTitles('1')");await b.ready(40);
out.noRightNoTitle=tb().textContent==="";
w.eval(`showTitle({overlay_duration_sec:1},{lines:["кратко"]})`);out.titleShown=tb().textContent==="кратко";await b.ready(1100);out.titleGoesByDuration=tb().textContent==="";
w.eval(`showTitle({words:[{msg:"x",color:"red"}]},{lines:["без слова"],word:"y"})`);out.noSuchWordNoColour=tb().firstChild.style.color==="";w.eval("clearTitle()");
w.eval("stopLive()");await b.ready(40);
// --- титры: архив, по времени кадра, occurred, задержка
EVENTS["cam/7"]=[{id:"a1",t:1050,occurred:1005,kind:"text",lines:["первый"]},{id:"a2",t:1060,kind:"text",lines:["второй"]}];
calls.length=0;await w.eval("(async()=>{const c=(UNITS.cam||[]).find(u=>u.type==='eventsrc');c.overlay_delay_ms=2000;await archiveTitles('1',{start:1000,end:1100},V.gen);c.overlay_delay_ms=0})()");
out.archiveAsksThePiece=calls.some(([,u])=>u===`/events?from=1000&to=1100&kind=text&unit=${encodeURIComponent("cam/7")}`);
const at=t=>{Object.defineProperty(player(),"currentTime",{value:t,configurable:true,writable:true});player().ontimeupdate();return tb().textContent};
out.archiveByFrameTime=at(6)===""&&at(7)==="первый"&&at(61)==="первый"&&at(62)==="второй";
player().ontimeupdate=null;w.eval("clearTitle()");
// --- разговор
out.talkOnVideoFirstSpeaker=(b=>!!b&&b.dataset.n==="3"&&b.textContent==="Говорить")(main().querySelector("#talkBtn"));
talkAnswers=[[404,{error:"not yet"}],[201]];order.length=0;
main().querySelector("#talkBtn").click();await b.ready(1900);
out.talkOrder=JSON.stringify(order)===JSON.stringify(["mic",'request:{"unit":"1","action":"talk","port":3}',"streams","talk","talk"]);   // дверь /live/where/1 ещё держится с живого
out.talkOn=main().querySelector("#talkBtn").textContent==="Закончить разговор";
const tp=w.__peers[w.__peers.length-1];out.talkSendsTheMic=tp.track===track;
pc.select("unit:cam/2");await b.ready(120);
out.talkEndsOnLeaving=track.stopped===1&&tp.closed===true&&talkDeleted.length===1&&talkDeleted[0]==="http://gw:9002/talk/session/t1"&&!w.eval("T.on");
// динамик занят: слова, микрофон закрыт
pc.select("unit:cam/1");await b.ready(80);main().querySelector('.pc-tabs [data-tab="vid"]').click();await b.ready(250);
talkAnswers=[[409,{error:"busy"}]];main().querySelector("#talkBtn").click();await b.ready(200);
out.talkBusyInWords=/Динамик занят/.test(toast())&&track.stopped===2&&!w.eval("T.on");
micRefused=true;main().querySelector("#talkBtn").click();await b.ready(100);micRefused=false;
out.noMicInWords=/Браузер не дал микрофон/.test(toast())&&track.stopped===2;
// карточка spk
pc.select("child:h-spk-9");await b.ready(120);
out.talkOnSpeakerCard=(b=>!!b&&b.dataset.n==="9"&&b.dataset.owner==="1")(main().querySelector("#talkBtn"));
pc.select("child:h-mic-1");await b.ready(120);out.noTalkOnMicCard=!main().querySelector("#talkBtn");
// --- поле микрофона записи, audio_reason
pc.select("unit:cam/1");await b.ready(80);main().querySelector('.pc-tabs [data-tab="rec"]').click();await b.ready(250);
const tabRec=()=>main().querySelector('[data-tab="rec"].pc-tab');
out.audioReasonSaid=/звук не пишется: no mic 2/.test(tabRec().textContent);
const mic=()=>tabRec().querySelector('input[data-act="audio"][data-rec="1"]');
out.micFieldShown=!!mic()&&mic().value==="2";
calls.length=0;mic().value="1.5";mic().dispatchEvent(new w.Event("change"));await b.ready(60);
out.micFieldRefusesFraction=/целый номер/.test(toast())&&!calls.some(([m])=>m==="PUT");
mic().value="4";mic().dispatchEvent(new w.Event("change"));await b.ready(120);
const puts=calls.filter(([m,u])=>m==="PUT"&&u==="/rec/recordings/1");out.micFieldWrites=puts.length===1&&puts[0][2]==='{"audio":4}';
// --- запись с stream: минут устройства нет, строки устройства и «Закрепить» нет
main().querySelector('.pc-tabs [data-tab="vid"]').click();await b.ready(300);
const sp=JSON.parse(w.eval("JSON.stringify(V.spans.filter(s=>s.recording==='1-s').map(s=>[s.stream,s.source]))"));
out.streamRecordingNoDevice=JSON.stringify(sp)==='[["5",""]]'&&!main().querySelector('#devline [data-act="pin"]');
// --- repaintTree при смене детей, не без смены
let repaints=0;const rt=pc.repaintTree;pc.repaintTree=()=>{repaints++;return rt()};
await w.eval("readChildren()");out.noRepaintWithoutChange=repaints===0;
for(const p of ["","/cam"])b.FIX[p+"/device_units"]={device_units:[...DU.device_units,{name:"h-3",camera:"1",type:"relay",n:3,template:"r",enabled:true}]};
await w.eval("readChildren()");out.repaintOnChange=repaints===1;
pc.repaintTree=rt;
// --- смена человека
const session=async user=>{b.FIX["/session"]={open:false,user,login_url:"http://holder/api/login"};
  w.eval("document.querySelector('.pc-login').hidden=false");if(d.querySelector(".pc-glass-f").hidden)d.querySelector(".pc-glass-go").click();
  const f=d.querySelector(".pc-glass-f");f.elements.who.value="ops";f.elements.why.value="x";f.elements.password.value="x";f.dispatchEvent(new w.Event("submit",{cancelable:true}));await b.ready(150)};
await session("ann");   // первое слово модуля панели: кто вошёл
w.eval(`keepDoor("/x",{door:{url:"http://a",token:"t",expires:Date.now()/1000+100}});
  (()=>{const h=document.createElement("div");h.className="live-account-secret";const i=document.createElement("input");i.value="секрет";h.appendChild(i);document.body.appendChild(h);accountPassword=i;window.__shown=i})()`);
await session("ann");
out.sameUserGoesOn=w.eval("!!DOORS['/x']&&CHILDREN!==null")===true&&w.__shown.value==="секрет";
w.eval(`CHILDREN=[{name:"прежний"}];DEV_UNITS=[{name:"прежний"}];`);
await session("bob");
out.otherUserForgets=w.eval("!DOORS['/x']&&!(CHILDREN||[]).some(c=>c.name==='прежний')&&!(DEV_UNITS||[]).some(c=>c.name==='прежний')")===true&&w.__shown.value===""&&!d.querySelector(".live-account-secret");
// --- без права edit: операции и разговора нет, правка отключена
b.FIX["/session"]={open:false,user:"vi",until:9e9,via:"token",grants:[{cap:"view",scope:"*"}]};
for(const p of ["","/cam"])b.FIX[p+"/device_units"]=DU;
const w2=b.boot();w2.addEventListener("error",e=>errs.push(String(e.error||e.message)));await b.ready(600);await w2.platformConsole.ready;
await w2.eval("readChildren()");await b.ready(60);const m2=()=>w2.document.querySelector("main");
w2.platformConsole.select("dunit:h-2");await b.ready(120);
out.viewNoOperation=!!m2().querySelector("#unitTitle")&&!m2().querySelector("#unitOp")&&!m2().querySelector('[data-act="save"]')&&m2().querySelector("#unitTitle").disabled;
w2.platformConsole.select("unit:cam/1");await b.ready(80);m2().querySelector('.pc-tabs [data-tab="vid"]').click();await b.ready(250);
out.viewNoTalk=!m2().querySelector("#talkBtn");
out.errors=errs;
b.report(out,["errors"]);
process.exit(0);
})();
