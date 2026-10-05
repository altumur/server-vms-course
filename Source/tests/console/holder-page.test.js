// Страница держателя домена (w2cplatform/domain/page.html, контракт модуля §10a): модуль с одним разделом «domain» и
// ничего своего. Корня нет (/spec без rows), единиц кластера, серверов, /drain и /metrics у держателя нет — модуль их
// не спрашивает. Карточка домена: размещение и передача, доверие, тревоги, члены (держатель среди них), единицы по
// подсистемам со «вкл/выкл» по domain.edit, общие настройки по declared, правки для кластеров. Заменённый держатель
// говорит, кто держит теперь, и предлагает применить заново то, что держал один. Данные — текстом: вредные строки во
// всех полях, нажимаем всё.
const fs=require("fs"),path=require("path");
const PAGE=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","domain","page.html"),"utf8");
const MOD=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"holder-page-"+process.pid+".html");
fs.writeFileSync(TMP,PAGE.replace(/<script src="\/platform\/console\.js\?v=1"><\/script>/,()=>`<script>${MOD}</script>`)
  .replace('{ sections: ["domain"] }','{ sections: ["domain"], poll_s: 0, lang: "ru" }'));
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");

function fixtures(P,deposed){
  for(const k of Object.keys(b.FIX))delete b.FIX[k];
  const p=s=>P+s;
  b.FIX["/session"]={open:false,user:p("u"),login_url:"/api/login"};
  b.FIX["/spec"]={name:"",rows:null};
  b.FIX["/mounts"]={root:"",mounts:{testsub:{name:"testsub",rows:"things",id:"name",fields:[{name:"name",type:"string"},{name:"start",type:"bool"}],
    display:{unit:"штука",units:"штуки",fields:{start:"Пуск"}},domain:{edit:["start"],view:["start"],shared:["tags","depth","on"]}}}};
  b.FIX["/domain"]={holder:"hold",as_of:1,age:0,complete:false,url:"http://hold/"+P,
    members:[{name:"hold",holder:true,state:"ok"},{name:p("m"),state:P,age:2,error:P,reaches:[P]},{name:"quiet",state:"silent",age:99}],
    term:deposed?{term:3,deposed:true,deposed_by:{holder:p("new"),term:4,url:P},
        stranded:[{path:"domain/pending/"+p("m"),key:p("k"),value:JSON.stringify({what:P})},{path:"domain/topology",key:"t",value:P}]}
      :{term:3,record:{holder:"hold",restored_from:P,restored_rev:P},backup_holders:[p("b")],can_hand_to:[p("to"),"quiet"]},
    trust:{installed:true,domain:P,rev:5,root:P,current:P,issuing:[P],revoked_issuing:[P],holder_has_keys:true,
      members:{[p("m")]:{admitted_key:P+"a",presented_key:P+"b",keys_rev:5},quiet:{admitted_key:"aa",presented_key:"aa",keys_rev:4},ok:{admitted_key:"cc",presented_key:"cc",keys_rev:5}}},
    units:{testsub:[{sub:"testsub",id:"1",ref:p("ref"),cluster:p("m"),worker:P,server:P,phase:P,age:1,state:"live",view:{start:true}},
                    {sub:"testsub",id:"2",ref:"cold",cluster:"quiet",phase:"",age:50,state:"silent",view:{start:false}}],[p("sub")]:[{ref:P,cluster:P,state:P,view:{[P]:P}}]},
    pending:{[p("m")]:[{what:P,at:1}]},outcomes:{[p("m")]:[{what:P,id:P,status:409,at:1,error:P}],quiet:[{what:"ok",status:200,at:2}]},
    topology:{rev:1,centre:"hold",star:[],via:{}},knocking:[],member_list:{rev:1,members:{}}};
  b.FIX["/domain/alarms"]={events:[{kind:P,member:p("m"),of:"testsub/1",t:1,subsystem:P,unit:P}],complete:false,sentence:P};
  b.FIX["/domain/shared"]={doc:{rev:7,term:3,at:1,by:P,shared:{testsub:{tags:[P,"b"],depth:3,on:true}}},delivery:{sentence:P,refused:{[p("m")]:P}},
    declared:{testsub:[{name:"tags",type:"list"},{name:"depth",type:"int"},{name:"on",type:"bool"}],[p("sub")]:[{name:P,type:"string"}]}};
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
    out[T("cardShownUnselected")]=!!d.querySelector(".pc-hd h1,.pc-main h1")&&!!cardOf(/Размещение/);
    out[T("treeRootDomainHolderAmongMembers")]=!!d.querySelector('.pc-tree [data-ref="domain"]')&&!!d.querySelector('.pc-tree [data-ref="member:hold"]')&&!!d.querySelector('.pc-tree [data-ref="member:quiet"]');
    const tr=cardOf(/Доверие/);
    out[T("trustRotationFlagged")]=!!tr&&tr.querySelectorAll(".bd.off").length===2&&/ротация не закончена/.test(tr.textContent);
    const un=cardOf(/Единицы/);
    out[T("unitsBySubsystemInItsWords")]=!!un&&/Штуки/.test(un.textContent)&&/Пуск: true/.test(un.textContent)&&/кластер молчит/.test(un.textContent);
    const ed=cardOf(/Правки для кластеров/);
    out[T("editsPendingAndOutcomes")]=!!ed&&/ждёт публикации/.test(ed.textContent)&&/отказ 409/.test(ed.textContent)&&/применена/.test(ed.textContent);
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
    out[T("sharedPut")]=!!s&&s.path==="/domain/shared"&&s.body.base_rev===7&&JSON.stringify(s.body.shared.testsub)==='{"tags":["x","y"],"depth":null,"on":false}';
    // передача: диалог с теми, кому можно, затем POST /domain/handover {to}
    n=w.__calls.length;main().querySelector('[data-a="handover"]').click();await b.ready(30);
    const dlg=d.querySelector(".pc-dialog-f");dlg.elements.to.value="quiet";dlg.requestSubmit();await b.ready(80);
    const ho=w.__calls.slice(n).find(x=>x.path==="/domain/handover");
    out[T("handoverToChosen")]=!!ho&&ho.body.to==="quiet";
    pc.select("member:"+P+"m");await b.ready(40);
    out[T("memberCardOpens")]=main().textContent.includes(P+"m");
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
(async()=>{
  const P=`x"'><img src=x onerror=window.__pwned=1>');window.__pwned=2;//`;
  const all={...await run("держатель",P,false),...await run("заменён",P,true)};
  b.report(all,Object.keys(all).filter(k=>/errors$/.test(k)));
  try{fs.unlinkSync(TMP)}catch(e){}
  process.exit(0);
})();
