// Серверы в модуле: метки (консоль/узел/расхождение/не прочитать, правка с вопросом, возврат к узлу), вывод из
// эксплуатации, списание (кнопка только у молчащего, причина, «запрошено», «снова отвечает», «списан», возврат),
// слот воркера (отпущен, нечитаемая аренда, завис, жив ли — неизвестно, конфликт имени), политика, bound_to.
const fs=require("fs"),path=require("path");
const SRC=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"pc-srv-"+process.pid+".html");
fs.writeFileSync(TMP,`<!doctype html><div id="app"></div><script>${SRC}</script><script>window.pc=PlatformConsole.mount(document.getElementById("app"),{lang:"en"});</script>`);
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
const W=o=>({worker:"w-1",load:1,capacity:5,state:"live",labels:"a",released:false,slot_until:1757500000,holds:[],hung:false,...o});
b.FIX["/session"]={open:true};
b.FIX["/spec"]={name:"testsub",rows:"things",id:"numeric",fields:[{name:"addr",type:"string"},{name:"labels",type:"list"},{name:"key_secret",type:"string",bound_to:["addr"]}]};
b.FIX["/things"]={configured:[{id:1,name:"one",addr:"x://1",labels:["a"],key_secret:"***"},{id:2,name:"two",addr:"x://2",labels:[],key_secret:""}],rows:[{id:1,worker:"w-1",phase:"running"}]};
b.FIX["/drain"]={draining:"",safe:true,subsystems:{}};
b.FIX["/schema"]={can_raise_to:3,builds:["b-1"],processes:{vms:{live:true},rec:{live:false}}};
b.FIX["/servers"]={policy:{servers:"shared"},servers:{
  "s-con":{resource:"live",workers:[W({})],labels:["b"],labels_node:["a"],labels_source:"console",decommissionable:false,decommission_refusal:"server s-con answers: drain it and switch it off first",decommission:null},
  "s-dead":{resource:"silent",resource_heard_at:1757490000,workers:[W({worker:"w-2",state:"stale",holds:["place-a"]})],labels:["a"],labels_source:"node",decommissionable:true,decommission:null},
  "s-asked":{resource:"silent",workers:[W({worker:"w-3"})],decommission:{by:"ann",at:1757500240,why:"burnt"},decommissioned:false,decommission_refusal:"",decommissionable:false},
  "s-back":{resource:"live",workers:[],decommission:{by:"ann",at:1,why:"x"},decommissioned:false,decommission_refusal:"server s-back answers",decommissionable:false},
  "s-gone":{resource:"silent",workers:[W({worker:"w-4",released:true,slot_until:null,slot_garbled:true})],decommission:{by:"ann",at:1,why:"burnt"},decommissioned:true,lost:[{place:"place-a",worker:"w-1"}],decommissionable:false},
  "s-quiet":{resource:"silent",door_quiet:true,workers:[],decommission:null,decommissionable:false,decommission_may_confirm_gone:true,decommission_refusal:"its door does not answer — decommission it with gone: true"},
  "s-hung":{resource:"live",labels_source:"unknown",workers:[W({worker:"w-5",hung:true,hung_since:1757500100}),W({worker:"w-6",presence_unknown:"lists no processes",hung_since:1}),W({worker:"w-7",name_conflict:{holder:"inst-a",holder_box:"box-a",contenders:[{state:"refused",hostname:"spare-7",server:"box-z"}]}})]}}};
(async()=>{
const w=b.boot();const errs=[];w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
let asked=[];w.confirm=q=>{asked.push(q);return true};
await b.ready(600);await w.pc.ready;const d=w.document,pc=w.pc,out={};
const main=()=>d.querySelector("main").textContent;
const btn=re=>[...d.querySelectorAll(".pc-main button")].find(x=>re.test(x.textContent));
const click=async re=>{const x=btn(re);if(x){x.click();await b.ready(80)}return!!x};
(d.querySelector('.pc-rail [data-s="units"]').click(),d.querySelector('.pc-layout').click(),d.querySelector('[data-layout="servers"]').click());await b.ready(30);
out.policyShown=d.querySelector(".pc-policy").value==="shared";
// обзор кластера, пока ничего не выбрано: счётчики, версия раскладки (/schema), кто молчит, политика пишется
out.clusterCard=/Cluster/.test(d.querySelector("main").textContent)&&[...d.querySelectorAll("main input")].some(x=>/3 · builds: b-1/.test(x.value))&&/Silent: rec/.test(d.querySelector("main").textContent)&&/servers in the cluster/.test(d.querySelector(".pc-hd").textContent);
{const n0=w.__calls.length;const ps=d.querySelector(".pc-policy");ps.value="distinct";ps.dispatchEvent(new w.Event("change"));await b.ready(100);
out.policyPut=w.__calls.slice(n0).some(x=>x.method==="PUT"&&x.path==="/policy"&&x.body.servers==="distinct");}
pc.select("server:s-con");await b.ready(30);
out.labelsConsoleAndNode=/set in the console/.test(main())&&/the node says: a/.test(main());
out.decomRefusal=!btn(/^Decommission$/)&&/cannot be decommissioned: server s-con answers/.test(main());
out.drainHelp=/for a server that comes back/.test(main());
// метки: что переедет, говорит платформа (GET …/labels?labels= → would_move, ссылки <sub>/<id> всех подсистем); вопрос
// называет их словами страницы, а чужие — ссылкой; PUT, и тост называет will_move
b.FIX["/servers/s-con/labels"]={server:"s-con",labels:["b"],labels_source:"console",would_move:["testsub/1","other/7-a"],will_move:["testsub/1"]};
const gets=[];{const f0=w.fetch;w.fetch=(u,i)=>{if(!i||!i.method||i.method==="GET")gets.push(String(u));return f0(u,i)}}
d.querySelector(".pc-lab-in").value="b";let n=w.__calls.length;asked=[];await click(/^Save$/);
out.labelsAskWhatThePlatformSays=gets.includes("/servers/s-con/labels?labels=b")&&asked.length===1&&/no longer reach: one, other\/7-a/.test(asked[0]);
out.labelsToastNamesWhatMoves=/moving 1: one/.test(d.querySelector(".pc-toast").textContent);
out.labelsPut=w.__calls.slice(n).some(x=>x.method==="PUT"&&x.path==="/servers/s-con/labels"&&JSON.stringify(x.body.labels)==='["b"]');
pc.select("server:s-con");await b.ready(30);n=w.__calls.length;await click(/Back to the node/);
out.labelsBack=w.__calls.slice(n).some(x=>x.method==="DELETE"&&x.path==="/servers/s-con/labels");
// вывод
pc.select("server:s-con");await b.ready(30);n=w.__calls.length;await click(/^Drain$/);
out.drainPost=w.__calls.slice(n).some(x=>x.method==="POST"&&x.path==="/drain");
// списание
pc.select("server:s-dead");await b.ready(30);
out.silentOffersDecom=!!btn(/^Decommission$/)&&/last heard/.test(main());
n=w.__calls.length;await click(/^Decommission$/);
out.decomPost=w.__calls.slice(n).some(x=>x.method==="POST"&&x.path==="/servers/s-dead/decommission");
pc.select("server:s-asked");await b.ready(30);
out.askedShown=/decommission requested/.test(main())&&/ann/.test(main())&&!!btn(/Give the server back/);
pc.select("server:s-back");await b.ready(30);
out.answersAgain=/answers again/.test(main());
pc.select("server:s-gone");await b.ready(30);
out.goneLost=/decommissioned/.test(main())&&/lost with the server: place-a \(w-1\)/.test(main());
n=w.__calls.length;await click(/Give the server back/);
out.decomDelete=w.__calls.slice(n).some(x=>x.method==="DELETE"&&x.path==="/servers/s-gone/decommission");
pc.select("server:s-quiet");await b.ready(30);
out.goneOffered=/physically gone/.test(main())&&/sees the decommission and stops/.test(main())&&/door does not answer/.test(main())&&btn(/^Decommission$/).disabled;
const gcb=d.querySelector(".pc-gone-cb");gcb.checked=true;gcb.dispatchEvent(new w.Event("change"));
n=w.__calls.length;await click(/^Decommission$/);
out.gonePosted=w.__calls.slice(n).some(x=>x.path==="/servers/s-quiet/decommission"&&x.body.gone===true);
pc.select("server:s-hung");await b.ready(30);
out.labelsUnknown=/cannot be read/.test(main());
// слот воркера
pc.select("worker:w-4");await b.ready(30);
out.releasedGarbled=/released/.test(main())&&/cannot be read/.test(main());
pc.select("worker:w-5");await b.ready(30);
out.hung=/hung/.test(main())&&/two writers/.test(main());
pc.select("worker:w-6");await b.ready(30);
out.presence=/alive or not — unknown/.test(main())&&/lists no processes/.test(main());
pc.select("worker:w-7");await b.ready(30);
out.nameConflict=/Name conflict: the name is held by inst-a/.test(main())&&/refused: the name is taken — spare-7 \(box-z\)/.test(main());
out.noWorkerActions=![...d.querySelectorAll(".pc-main button:not(.pc-star):not(.pc-fullbtn)")].length;
// bound_to: сменили addr при заданном ключе — без нового ключа не уходит
d.querySelector('.pc-rail [data-s="units"]').click();
pc.select("unit:testsub/1");await b.ready(80);
const f=d.querySelector(".pc-edit");f.elements.addr.value="x://9";n=w.__calls.length;f.dispatchEvent(new w.Event("submit",{cancelable:true}));await b.ready(60);
out.boundBlocks=w.__calls.length===n&&/key_secret: is bound to a field you changed/.test(f.querySelector(".pc-err").textContent);
f.elements.key_secret.value="new";f.dispatchEvent(new w.Event("submit",{cancelable:true}));await b.ready(80);
const c=w.__calls.slice(n).find(x=>x.method==="PUT");
out.boundSendsBoth=!!c&&c.body.addr==="x://9"&&c.body.key_secret==="new";
pc.select("unit:testsub/2");await b.ready(80);
const f2=d.querySelector(".pc-edit");f2.elements.addr.value="x://8";n=w.__calls.length;f2.dispatchEvent(new w.Event("submit",{cancelable:true}));await b.ready(80);
out.boundNotSetNoDemand=w.__calls.slice(n).some(x=>x.method==="PUT"&&x.body.addr==="x://8");
out.errors=errs;
b.report(out,["errors"]);
try{fs.unlinkSync(TMP)}catch(e){}
process.exit(0);
})();
