// Страница держателя домена (w2cplatform/domain/page.html, контракт модуля §10a): модуль с одним разделом «domain» и
// ничего своего. Корня нет (/manifest без rows), единиц кластера, серверов, /drain и /metrics у держателя нет — модуль их
// не спрашивает. Карточка домена: размещение и передача, доверие, тревоги, члены (держатель среди них), единицы по
// подсистемам со «вкл/выкл» по domain.edit, общие настройки по declared, правки для кластеров. Заменённый держатель
// говорит, кто держит теперь, и предлагает применить заново то, что держал один. Данные — текстом: вредные строки во
// всех полях, нажимаем всё.
const fs=require("fs"),path=require("path");
const PAGE=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","domain","page.html"),"utf8");
const MOD_PATH=path.join(__dirname,"..","..","..","Platform","07-console-module","module","console.js");
const MOD=fs.readFileSync(MOD_PATH,"utf8");
const MOD_SHA=require("crypto").createHash("sha256").update(MOD,"utf8").digest("hex");
const TMP=path.join(require("os").tmpdir(),"holder-page-"+process.pid+".html");
fs.writeFileSync(TMP,PAGE.replace(/<script src="\/platform\/console\.js\?v=1"><\/script>/,()=>`<script>${MOD}</script>`)
  .replace('{ sections: ["domain"], lang: "ru" }','{ sections: ["domain"], lang: "ru", poll_s: 0 }'));
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");

function fixtures(P,deposed){
  for(const k of Object.keys(b.FIX))delete b.FIX[k];
  const p=s=>P+s;
  b.FIX["/session"]={open:false,user:p("u"),login_url:"/api/login",until:9,via:"token",grants:[{cap:"admin",scope:"*"}]};
  b.FIX["/manifest"]={name:"",rows:null};
  b.FIX["/mounts"]={root:"",mounts:{testsub:{name:"testsub",rows:"things",id:"name",fields:[{name:"name",type:"string"},{name:"start",type:"bool"}],
    display:{unit:"штука",units:"штуки",fields:{start:"Пуск"},kinds:{"thing.lost":"штука потеряна"}},domain:{edit:["start"],view:["start"],shared:["tags","depth","on"]}}}};
  b.FIX["/domain"]={holder:"hold",as_of:1,age:0,complete:false,url:"http://hold/"+P,
    members:[{name:"hold",holder:true,state:"ok"},{name:p("m"),state:P,age:2,error:P,reaches:[P]},{name:"quiet",state:"silent",age:99}],
    term:deposed?{term:3,deposed:true,deposed_by:{holder:p("new"),term:4,url:P},
        stranded:[{path:"domain/pending/"+p("m"),key:p("k"),value:JSON.stringify({what:P})},{path:"domain/topology",key:"t",value:P}]}
      :{term:3,record:{holder:"hold",restored_from:P,restored_rev:P},backup_holders:[p("b"),"quiet"],backup:{term:3,rev:7},copies:{[p("b")]:{term:3,rev:7},quiet:{term:2,rev:40},gone:{term:3,rev:5},bad:{garbled:P}},can_hand_to:[p("to"),"quiet"]},
    trust:{installed:true,domain:P,rev:5,root:P,current:P,issuing:[P],revoked_issuing:[P],holder_has_keys:true,
      members:{[p("m")]:{admitted_key:P+"a",presented_key:P+"b",keys_rev:5},quiet:{admitted_key:"aa",presented_key:"aa",keys_rev:4},ok:{admitted_key:"cc",presented_key:"cc",keys_rev:5}}},
    units:{testsub:[{sub:"testsub",id:"1",ref:p("ref"),cluster:p("m"),worker:P,server:P,phase:P,age:1,state:"live",view:{start:true}},
                    {sub:"testsub",id:"2",ref:"cold",cluster:"quiet",phase:"",age:50,state:"silent",view:{start:false}}],[p("sub")]:[{ref:P,cluster:P,state:P,view:{[P]:P}}]},
    pending:{[p("m")]:1},outcomes:{[p("m")]:[{what:P,id:P,status:409,at:1,error:P}],quiet:[{what:"ok",status:200,at:2}]},
    topology:{rev:1,centre:"hold",star:[],via:{}},knocking:[],member_list:{rev:1,members:{}}};
  b.FIX["/domain/alarms"]={events:[{kind:"session.debug_open",member:"hold",unit:"console",t:9,person:"stand-admin",id:"x1"},{kind:"session.debug_open",member:"quiet",unit:"console",t:8,person:"stand-admin",id:"x2"},
    {kind:"session.debug_open",member:"hold",unit:"domain",t:3,person:"stand-admin",id:"x3"},{kind:P,member:p("m"),of:"testsub/1",t:1,subsystem:P,unit:P},
    {kind:"thing.lost",subsystem:"audit",unit:"audit/worker",of:"testsub/2",member:"quiet",t:0}],complete:false,sentence:P};
  b.FIX["/domain/shared"]={doc:{rev:7,term:3,at:1,by:P,shared:{testsub:{tags:[P,"b"],depth:3,on:true,rules:{a:[1],why:P}}}},delivery:{sentence:P,refused:{[p("m")]:P}},
    declared:{testsub:[{name:"tags",type:"list"},{name:"depth",type:"int"},{name:"on",type:"bool"},{name:"rules",type:"json"}],[p("sub")]:[{name:P,type:"string"}]}};
  b.FIX["/domain/handover"]={sentence:"handed"};
  b.FIX["/domain/stranded/apply"]={ok:true};
  b.FIX["/domain/testsub/things/"+encodeURIComponent(p("ref"))]={ok:true};
}

async function run(tag,P,deposed){
  fixtures(P,deposed);
  const w=b.boot();const errs=[],asked=[];w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
  w.confirm=()=>true;w.prompt=()=>null;w.alert=()=>{};
  const f0=w.fetch;w.fetch=(u,i)=>{asked.push(String(u).split("?")[0]);return f0(u,i)};
  await b.ready(500);await w.platformConsole.ready;await b.ready(50);
  const d=w.document,pc=w.platformConsole,main=()=>d.querySelector(".pc-main"),out={},T=s=>tag+": "+s;
  const cardOf=re=>[...main().querySelectorAll(".card")].find(c=>re.test(c.querySelector(".ch").textContent));
  out[T("onlyDomainRail")]=[...d.querySelectorAll(".pc-rail [data-s]")].map(x=>x.dataset.s).join()==="domain";
  out[T("askedNothingOfACluster")]=!asked.some(u=>/^\/(servers|drain|schema|metrics|unplaceable|things|testsub\/|events|domain\/held|domain\/shared\/)/.test(u));
  if(!deposed){
    out[T("newestCopyByTermAndRev")]=[...d.querySelectorAll(".pc-main input")].some(x=>x.value==="rev 7 · срок 3");
    // копии членов против новейшей: (term, rev) — сначала срок; кому держатель её больше не носит — сказано
    const cp=n=>[...d.querySelectorAll(".pc-main .it")].find(x=>x.textContent.trim().startsWith(n))||{textContent:""};
    out[T("copiesJudgedByTermThenRev")]=!/старая копия/.test(cp(P+"b").textContent)&&/rev 40 · срок 2/.test(cp("quiet").textContent)&&/старая копия/.test(cp("quiet").textContent)&&!/больше не обновляет/.test(cp("quiet").textContent)
      &&/старая копия/.test(cp("gone").textContent)&&/держатель её больше не обновляет/.test(cp("gone").textContent)&&/строка не читается/.test(cp("bad").textContent)&&!/старая копия/.test(cp("bad").textContent);
    out[T("cardShownUnselected")]=!!d.querySelector(".pc-hd h1,.pc-main h1")&&!!cardOf(/Размещение/);
    out[T("treeRootDomainHolderAmongMembers")]=!!d.querySelector('.pc-tree [data-ref="domain"]')&&!!d.querySelector('.pc-tree [data-ref="member:hold"]')&&!!d.querySelector('.pc-tree [data-ref="member:quiet"]');
    const tr=cardOf(/Доверие/);
    out[T("trustRotationFlagged")]=!!tr&&tr.querySelectorAll(".bd.off").length===2&&/ротация не закончена/.test(tr.textContent);
    const un=cardOf(/Единицы/);
    out[T("unitsBySubsystemInItsWords")]=!!un&&/Штуки/.test(un.textContent)&&/Пуск: да/.test(un.textContent)&&/Пуск: нет/.test(un.textContent)&&/кластер молчит/.test(un.textContent);
    const al=cardOf(/Тревоги/),rows=al?[...al.querySelectorAll(".it")]:[];
    out[T("alarmsOneLinePerKindAndAbout")]=rows.length===4&&/×2/.test(rows[0].textContent)&&/· console/.test(rows[0].textContent)&&/hold, quiet/.test(rows[0].textContent)&&/как stand-admin/.test(rows[0].textContent)&&!/id=/.test(rows[0].textContent)&&/· domain/.test(rows[1].textContent)&&!/×/.test(rows[1].textContent);
    out[T("relayedKindInAnyManifestsWords")]=/штука потеряна/.test(rows[3]?rows[3].textContent:"");
    out[T("holderHeaderNoWorkersNoFooter")]=d.querySelector(".pc-hworkers").parentElement.style.display==="none"&&d.querySelector("footer").style.display==="none"&&d.querySelector(".pc-hunits-l").textContent==="Кластеры";
    const ed=cardOf(/Правки для кластеров/);
    out[T("editsPendingAndOutcomes")]=!!ed&&[...ed.querySelectorAll(".it")].some(r=>{const c=r.querySelector(".bd.wait");return !!c&&c.textContent==="1"&&r.textContent.includes(P+"m")})&&/отказ 409/.test(ed.textContent)&&/применена/.test(ed.textContent);
    // «вкл/выкл» по domain.edit: PUT /domain/testsub/things/<ref> {start: false}
    let n=w.__calls.length;const off=[...un.querySelectorAll("button")].find(x=>/Выключить/.test(x.textContent));if(off)off.click();await b.ready(80);
    const c=w.__calls.slice(n).find(x=>x.method==="PUT");
    out[T("unitSwitchByDomainEdit")]=!!c&&c.path==="/domain/testsub/things/"+encodeURIComponent(P+"ref")&&JSON.stringify(c.body)==='{"start":false}'&&!!c.key;
    // общие настройки: список по строке, число, да/нет; пустое — null
    const sh=()=>cardOf(/Общие настройки/),fld=nm=>[...sh().querySelectorAll("[data-sh]")].find(x=>x.dataset.sh===nm);
    out[T("sharedEditorByDeclared")]=!!sh()&&fld("testsub/tags").tagName==="TEXTAREA"&&fld("testsub/tags").value===P+"\nb"&&fld("testsub/depth").type==="number"&&fld("testsub/on").tagName==="SELECT";
    fld("testsub/tags").value="x\n\n y ";fld("testsub/depth").value="";fld("testsub/on").value="false";
    n=w.__calls.length;sh().querySelector('[data-a="publish"]').click();await b.ready(80);
    const s=w.__calls.slice(n).find(x=>x.method==="PUT");
    out[T("sharedPut")]=!!s&&s.path==="/domain/shared"&&s.body.base_rev===7&&JSON.stringify(s.body.shared.testsub)===JSON.stringify({tags:["x","y"],depth:null,on:false,rules:{a:[1],why:P}});
    // json-документ (сценарии домена): текст с отступами; не JSON — ничего не уходит, набранное остаётся; JSON — объектом
    const js=()=>fld("testsub/rules");
    out[T("sharedJsonAsText")]=!!js()&&js().tagName==="TEXTAREA"&&js().value===JSON.stringify({a:[1],why:P},null,2)&&!/object Object/.test(sh().textContent);
    js().value="{bad";n=w.__calls.length;sh().querySelector('[data-a="publish"]').click();await b.ready(60);
    out[T("sharedJsonInvalidNotSentKept")]=!w.__calls.slice(n).some(x=>x.method==="PUT")&&/Не JSON, ничего не отправлено/.test(sh().textContent)&&js().value==="{bad";
    js().value='{"b": 2}';n=w.__calls.length;sh().querySelector('[data-a="publish"]').click();await b.ready(80);
    const s2=w.__calls.slice(n).find(x=>x.method==="PUT");
    out[T("sharedJsonSentParsed")]=!!s2&&JSON.stringify(s2.body.shared.testsub.rules)==='{"b":2}';
    // передача: диалог с теми, кому можно, затем POST /domain/handover {to}
    n=w.__calls.length;main().querySelector('[data-a="handover"]').click();await b.ready(30);
    const dlg=d.querySelector(".pc-dialog-f");dlg.elements.to.value="quiet";dlg.requestSubmit();await b.ready(80);
    const ho=w.__calls.slice(n).find(x=>x.path==="/domain/handover");
    out[T("handoverToChosen")]=!!ho&&ho.body.to==="quiet";
    pc.select("member:"+P+"m");await b.ready(40);
    const memberTitle=d.querySelector(".pc-hd .cr-cur,.pc-hd h1");
    out[T("memberCardOpens")]=pc.selected()==="member:"+P+"m"&&!!memberTitle&&memberTitle.textContent===P+"m";
  } else {
    const t=main().textContent;
    out[T("deposedSaysWhoHolds")]=t.includes(P+"new")&&/заменён/.test(t)&&!cardOf(/Общие настройки/)&&!cardOf(/Единицы/);
    let n=w.__calls.length;const rb=main().querySelector("[data-reapply]");if(rb)rb.click();await b.ready(80);
    const r=w.__calls.slice(n).find(x=>x.path==="/domain/stranded/apply");
    out[T("reapplyByPerson")]=!!r&&r.body.path==="domain/pending/"+P+"m"&&r.body.key===P+"k"&&main().querySelectorAll("[data-reapply]").length===1;
  }
  // всё, что нажимается, — по разу; код из данных не выполняется, чужих элементов нет
  for(const el of [...d.querySelectorAll("main button, main .it, .pc-tree .n")]){try{el.dispatchEvent(new w.MouseEvent("click",{bubbles:true}))}catch(e){}
    const no=d.querySelector(".pc-dialog:not([hidden]) .pc-dialog-no");if(no)no.click()}
  await b.ready(50);
  out[T("payloadNeverRan")]=w.__pwned===undefined&&!d.querySelector("img,iframe,[onerror]");
  out[T("noInlineHandlers")]=![...d.querySelectorAll("*")].some(el=>[...el.attributes].some(a=>/^on/i.test(a.name)));
  out[T("errors")]=errs.filter(e=>!/Not implemented/.test(e)).slice(0,3);
  out[T("noErrors")]=out[T("errors")].length===0;
  w.close();
  return out;
}
// J-P07-01 positive /domain response: owner fields, not adversarial form values or renderer output.
async function runCurrentPending(){
  fixtures("",false);
  b.FIX["/domain"]={
  "as_of": 10,
  "holder": "hold",
  "complete": false,
  "age": 0,
  "members": [
    {
      "name": "hold",
      "state": "ok",
      "age": 0
    },
    {
      "name": "m1",
      "state": "ok",
      "age": 0
    },
    {
      "name": "m2",
      "state": "never",
      "age": null
    }
  ],
  "units": {
    "testsub": []
  },
  "contested": {
    "testsub": {}
  },
  "pending": {
    "hold": 0,
    "m1": 1,
    "m2": null
  },
  "outcomes": {
    "hold": [
      {
        "id": "e-000000000001",
        "status": 200,
        "result": "performed",
        "at": 3,
        "what": "set",
        "kept_at": 1
      }
    ],
    "m1": [],
    "m2": [
      {
        "id": "e-000000000002",
        "status": 409,
        "result": "refused",
        "error": "exists",
        "at": 2,
        "what": "create",
        "kept_at": 1
      }
    ]
  }
};
  const w=b.boot(),errs=[];w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
  w.confirm=()=>true;w.prompt=()=>null;w.alert=()=>{};
  await b.ready(500);await w.platformConsole.ready;await b.ready(50);
  const d=w.document,out={},T=s=>"J-P07-01: "+s;
  const ed=[...d.querySelectorAll(".pc-main .card")].find(c=>{const t=c.querySelector(".ch");return !!t&&t.textContent.includes("Правки для кластеров")});
  const rows=ed?[...ed.querySelectorAll(".it")]:[],waiting=rows.filter(r=>r.querySelector(".bd.wait"));
  const name=r=>r.children[1]&&r.children[1].firstChild?r.children[1].firstChild.textContent:null;
  const counts=new Map(waiting.map(r=>[name(r),r.querySelector(".bd.wait").textContent]));
  const outcomes=rows.filter(r=>!r.querySelector(".bd.wait"));
  const outcome=(member,what)=>outcomes.find(r=>name(r)===member+" · "+what);
  const performed=outcome("hold","set"),refused=outcome("m2","create");
  out[T("canonicalModuleBytes")]=MOD_SHA==="155b0746b075db0ac339d40c46b34896c15511a4c25cd12d2271604f82976003";
  out[T("oneCurrentCountPerMember")]=waiting.length===3&&counts.size===3;
  out[T("zeroIsVisible")]=counts.has("hold")&&counts.get("hold")==="0";
  out[T("oneIsVisible")]=counts.has("m1")&&counts.get("m1")==="1";
  out[T("unreadIsUnknown")]=counts.has("m2")&&counts.get("m2")==="неизвестно";
  out[T("performedOutcomeAtZeroPending")]=!!performed&&performed.querySelector(".bd").textContent==="применена";
  out[T("refusedOutcomeAtUnknownPending")]=!!refused&&refused.querySelector(".bd").textContent==="отказ 409"&&refused.textContent.includes("exists");
  out[T("outcomesIndependentOfPending")]=outcomes.length===2&&!outcomes.some(r=>String(name(r)).startsWith("m1 · "));
  out[T("errors")]=errs.filter(e=>!/Not implemented/.test(e)).slice(0,3);
  out[T("noErrors")]=out[T("errors")].length===0;
  w.close();return out;
}

(async()=>{
  const P=`x"'><img src=x onerror=window.__pwned=1>');window.__pwned=2;//`;
  const all={...await run("держатель",P,false),...await run("заменён",P,true),...await runCurrentPending()};
  b.report(all,Object.keys(all).filter(k=>/errors$/.test(k)));
  try{fs.unlinkSync(TMP)}catch(e){}
  process.exit(0);
})();
