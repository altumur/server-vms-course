// Хранимый XSS (ревью курса, блокер 2) на странице VMS курса — модуле и оболочке. Всё, что приходит с сервера, может
// задать кто-то, у кого прав меньше, чем у того, кто откроет страницу: здесь каждое строковое поле ответов — вредная
// строка, которая пытается выйти из текста, из атрибута, из строки внутри обработчика, или несёт <script>. Обход: обе
// раскладки панели, каждая строка дерева, каждая вкладка, всё, что нажимается, разделы и меню строк. Код из данных не
// выполняется ни разу, чужих элементов в разметке нет, данные видны текстом. (По образцу продуктового; фикстуры —
// ответы курса: тома с held_by, удержания с name, вид домена с units и tables.)
const fs=require("fs"),path=require("path");
const PAGE=fs.readFileSync(path.join(__dirname,"..","..","vms","vms.shell.html"),"utf8");
const MOD=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"shell-xss-"+process.pid+".html");
fs.writeFileSync(TMP,PAGE.replace(/<script src="\/platform\/console\.js\?v=1"><\/script>/,()=>`<script>${MOD}</script>`).replace('{lang:"ru",','{lang:"ru",poll_s:0,'));
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
async function sweep(P,tag){
for(const k of Object.keys(b.FIX))delete b.FIX[k];
const p=s=>P+s;
b.FIX["/session"]={open:true,user:p("u"),until:1790800000,login_url:"http://srv:8070/api/login"};
b.FIX["/spec"]={name:"vms",rows:"cameras",id:"numeric",fields:[{name:"name",type:"string"},{name:"source",type:"url"},{name:"labels",type:"list"},{name:"folders",type:"list"},{name:"cred_secret",type:"string"}],
  display:{unit:"камера",units:"камеры",kinds:{[P]:P,"io.input":P},tree:{group_by:"folders",nested_by:"/"},form:[{title:"Размещение",placement:true,state:true,fields:["name","source","labels","folders","cred_secret"]}]}};
b.FIX["/mounts"]={root:"vms",mounts:{rec:{name:"rec",rows:"recordings",id:"name",about:{sub:"vms",field:"cam"},places:{table:"volumes"},fields:[{name:"cam",type:"string"}],display:{kinds:{[P]:P}}},live:{name:"live",rows:"streams",id:"cam",about:{sub:"vms",field:"cam"},fields:[{name:"cam",type:"string"}]}}};
b.FIX["/cameras"]={configured:[{id:1,name:P,source:"driverpack://"+encodeURIComponent(P)+"/10.0.0.11/ch/1",enabled:true,labels:[P],folders:[p("f")+"/"+p("g")],ref:p("ref"),cred_secret:"***"},{id:2,name:P,source:P,enabled:false,labels:[],folders:[]}],
  rows:[{id:1,worker:p("w"),phase:"failed",epoch:P,why:P,warning:P,device_state:"opening",live_url:P}]};
b.FIX["/servers"]={servers:{[p("s")]:{resource:P,resource_url:P,labels:[P],labels_source:"console",space:{total:9e9,free:1e9},workers:[{worker:p("w"),capacity:50,load:1,labels:P,state:P,released:false,slot_until:1,holds:[P],hung:true,hung_since:1,presence_unknown:P,
  name_conflict:{holder:P,holder_box:P,contenders:[{state:P,box:P,hostname:P,server:P,for_s:1}]}}],
  decommission:{by:P,at:1,why:P},decommission_refusal:P,decommission_warning:P,decommissionable:false,lost:[{place:P,worker:P}]}},policy:{servers:"shared"}};
b.FIX["/schema"]={can_raise_to:P,builds:[P],processes:{[P]:{live:false}}};
b.FIX["/unplaceable"]=[{id:2,labels:[P],workers_live:1}];
b.FIX["/rec/volumes"]={volumes:[{name:p("v"),server:p("s"),kind:"local",url:P,enabled:true,held_by:P,quota_bytes:1e9,access_key:P},{name:p("n"),kind:"network",url:P,enabled:true,quota_bytes:1e9},{name:p("b"),server:p("s"),kind:"backup",url:P,enabled:true,quota_bytes:1e9}]};
b.FIX["/rec/recordings"]={configured:[{id:p("r"),cam:"1",home:p("v"),retention_days:P,enabled:true},{id:p("r2"),cam:"1",home:p("b"),retention_days:3,enabled:false,when:P}],rows:[{id:p("r"),worker:P,server:P,why:P,phase:"running"}]};
b.FIX["/rec/keeps"]={keeps:[{name:p("k"),cam:"1",from:1,to:2,note:P,by:P,at:1,recordings:[p("r")]}]};
b.FIX["/live/streams"]={configured:[],rows:[]};
b.FIX["/events"]={events:[{t:3,subsystem:"rec",kind:"volume.missing",unit:"rec/1",class:"alarm",volume:P,server:P,recorder:P,detail:P,note:P},{t:2,subsystem:"rec",kind:"card.failing",state:P,error:P,unit:P},{t:1,subsystem:P,kind:P,unit:P,note:P},
  {t:4,subsystem:"auto",kind:"fired",unit:"auto/"+p("sc"),actions:P}],state:P};
b.FIX["/domain"]={holder:"srv",url:"http://srv/"+P,as_of:1,age:1,complete:false,
  members:[{name:"srv",holder:true,state:"ok"},{name:p("m"),state:P,age:2,error:P,reaches:[P]},{name:p("cam"),state:"ok",age:2}],
  units:{vms:[{sub:"vms",id:"1",cluster:p("cam"),unit:"1",ref:p("ref2"),name:P,server:P,worker:P,phase:P,state:P,age:1,view:{name:P,enabled:true},worker_state:P,as_of:P},
              {sub:"vms",id:P,cluster:p("m"),unit:P,ref:P,name:P,state:"live",age:1,view:{name:P},worker_state:"live"},{sub:"vms",id:"2",cluster:p("m"),unit:"2",ref:p("r3"),name:P,state:P,view:{[P]:P}}],
         rec:[{sub:"rec",id:p("rec"),cluster:p("cam"),unit:p("rec"),name:P,worker:P,server:P,phase:P,state:"stale",worker_state:"stale",as_of:P}]},
  tables:{"vms/crossings":{[p("ref2")]:P,[P]:P}},
  topology:{rev:1,centre:"srv",star:[],via:{[p("cam")]:p("m")},by:P},knocking:[{name:p("kn"),times:P,last:1,fingerprint:P}],member_list:{rev:1,members:{[p("m")]:{how:P,since:1}}}};
b.FIX["/domain/alarms"]={events:[{kind:P,member:p("m"),of:"vms/1",t:1,subsystem:P,unit:P,alive_via:P}],complete:false,sentence:P};
b.FIX["/api/held"]={cluster:"srv",holder:{holder:P,term:P,url:P},term:P,keys:{current:P},backup:{rev:P}};
b.FIX["/domain/keys"]={vars:[{key:"domain/"+P,items:{[P]:P},index:P}],objects:[{key:"domain/members/"+P,size:1,body:{x:P}}],error:P};
b.FIX["/domain/users"]={users:[{name:p("u"),how:"password",by:P,at:1},{name:p("u2"),how:"oidc",disabled:true}]};
b.FIX["/domain/grants"]={grants:{domain:[{subject:p("u"),cap:"admin",scope:"*",by:P}],[p("m")]:[{subject:p("u"),cap:"view",scope:"unit:vms/"+P,by:P}]}};
b.FIX["/domain/break-glass"]={clusters:{[p("m")]:{set_at:1}}};
b.FIX["/domain/shared/vms"]={sub:"vms",rev:P,fields:{folders:{groups:[p("site")],from:P}}};
b.FIX["/auto/scenarios"]={configured:[{id:p("sc"),name:P,when:[{sub:P,kind:P,unit:P,match:{[P]:P}}],then:[{sub:"vms",action:"output",unit:P,port:P},{sub:P,action:P,x:P}],enabled:true,within:P}],rows:[{id:p("sc"),phase:"refused",why:P,unfit:[P],worker:P}]};
b.FIX["/det/spec"]={name:"det"};

const w=b.boot();const errs=[];w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
w.prompt=()=>null;w.confirm=()=>false;w.alert=()=>{};w.HTMLMediaElement.prototype.play=function(){return Promise.resolve()};
w.RTCPeerConnection=function(){this.addTransceiver=()=>{};this.createOffer=async()=>({sdp:"v=0"});this.setLocalDescription=async d=>{this.localDescription=d};this.close=()=>{}};
await b.ready(800);await w.platformConsole.ready;
const d=w.document,pc=w.platformConsole,out={};
const own=new Set([...d.querySelectorAll("img,script,iframe,object,embed")]);
const pwned=()=>w.__pwned!==undefined;
const foreign=()=>[...d.querySelectorAll("img,script,iframe,object,embed")].filter(x=>!own.has(x)).length+d.querySelectorAll("[onerror],[onload]").length;
const views=[];let clicked=0;
const calm=()=>{try{w.eval("typeof closeConfirm==='function'&&closeConfirm()")}catch(e){}
  const no=d.querySelector(".pc-dialog:not([hidden]) .pc-dialog-no");if(no)no.click();const m=d.querySelector(".pc-menu");if(m)m.classList.remove("open")};
// everything that answers a click in the card and its head, one by one; a click that leads elsewhere is followed by
// a way back to the card, and the next one is taken afresh (the card is drawn anew)
const clickables=()=>[...d.querySelectorAll("main button, main .it, main [onclick], main .cr-link")].filter(x=>!/pc-del|pc-logout|liveBtn/.test(x.className+" "+x.id));
async function visit(label){
  views.push(label);
  const ref=pc.selected(),n=Math.min(clickables().length,40);
  for(let i=0;i<n;i++){
    const el=clickables()[i];if(!el)break;
    try{el.dispatchEvent(new w.MouseEvent("click",{bubbles:true}));clicked++}catch(e){}
    calm();
    if(ref&&pc.selected()!==ref){try{pc.select(ref)}catch(e){}}
  }
  await b.ready(20);
  if(pwned()||foreign()){out["чисто: "+label]=false;const x=[...d.querySelectorAll("img,script,iframe,object,embed")].find(y=>!own.has(y))||d.querySelector("[onerror],[onload]");if(x)out["где: "+label]=(x.parentElement?.outerHTML||"").slice(0,300)}
}
const openAll=()=>{for(let i=0;i<4;i++)d.querySelectorAll(".pc-tree [data-tw]").forEach(t=>{if(t.textContent==="▸")t.click()})};
for(const lay of ["units","servers"]){
  d.querySelector('.pc-rail [data-s="units"]').click();d.querySelector(".pc-layout").click();d.querySelector(`[data-layout="${lay}"]`).click();await b.ready(40);
  openAll();await visit("дерево "+lay);
  for(const ref of [...d.querySelectorAll(".pc-tree .n[data-ref]")].map(x=>x.dataset.ref)){
    try{pc.select(ref)}catch(e){errs.push("select "+ref.slice(-6)+": "+e.message)}
    await b.ready(40);
    const tabs=[...d.querySelectorAll("main .pc-tabs button")].map(x=>x.dataset.tab);
    for(const t of tabs.length?tabs:[null]){const x=t&&d.querySelector(`main .pc-tabs [data-tab="${t}"]`);if(x)x.click();await b.ready(40);await visit(ref.slice(0,6)+" "+(t||""))}
    calm();
  }
}
for(const s of ["access","rules","journal"]){
  const x=d.querySelector(`.pc-rail [data-s="${s}"]`);if(!x)continue;x.click();await b.ready(150);await visit("раздел "+s);
  for(const ref of [...d.querySelectorAll(".pc-tree .n[data-ref]")].map(y=>y.dataset.ref)){try{pc.select(ref)}catch(e){}await b.ready(30);await visit(s+" "+ref.slice(0,6))}
}
d.querySelector('.pc-rail [data-s="units"]').click();await b.ready(30);openAll();
for(const el of [...d.querySelectorAll(".pc-tree .n[data-ref]")].slice(0,20)){
  el.dispatchEvent(new w.MouseEvent("contextmenu",{bubbles:true,clientX:5,clientY:5}));
  for(const b2 of [...d.querySelectorAll(".pc-menu button")]){try{b2.click();clicked++}catch(e){}calm()}
}
await visit("меню строки");
out.payloadNeverRan=!pwned();
out.noForeignElements=foreign()===0;
out.payloadShownAsText=d.body.textContent.includes(P)||[...d.querySelectorAll("input")].some(x=>x.value.includes(P));
out.visited=views.length;out.clicked=clicked;
out.enoughCoverage=views.length>=20&&clicked>=150;
out.errors=errs.filter(e=>!/Not implemented|prompt|confirm/.test(e)).slice(0,5);
const res={};for(const [k,v] of Object.entries(out))res[tag+": "+k]=v;
return res;
}
(async()=>{
  const a=await sweep(`x"'><img src=x onerror=window.__pwned=1>');window.__pwned=2;//`,"разметка");
  const c=await sweep(`x');window.__pwned=3;//`,"обработчик");
  const n=await sweep(`<script>window.__pwned="script"</script><img src=x onerror="window.__pwned='img'">');window.__pwned='js';//`,"заметка");
  const all={...a,...c,...n},skip=Object.keys(all).filter(k=>/visited|clicked|errors|где/.test(k));
  b.report(all,skip);
  try{fs.unlinkSync(TMP)}catch(e){}
  process.exit(0);
})();
