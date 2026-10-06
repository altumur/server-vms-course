// Домен в модуле: держатель и резервная копия (на «Обзоре» сервера, как в консоли продукта), перенос сюда, члены (значки, принять просящегося с отпечатком,
// вывести), топология (черновик, запись с base_rev), тревоги со всех членов словами из display, ключи.
const fs=require("fs"),path=require("path");
const SRC=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"pc-dom-"+process.pid+".html");
fs.writeFileSync(TMP,`<!doctype html><div id="app"></div><script>${SRC}</script><script>window.pc=PlatformConsole.mount(document.getElementById("app"),{lang:"en"});</script>`);
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
const P=`x"'><img src=x onerror=window.__pwned=1>`;
b.FIX["/session"]={open:true};
b.FIX["/spec"]={name:"testsub",rows:"things",id:"numeric",fields:[],display:{kinds:{silent:"nobody sees it"}}};
b.FIX["/things"]={configured:[],rows:[]};
b.FIX["/servers"]={servers:{"s-1":{resource:"live",workers:[]}},policy:{}};
b.FIX["/domain"]={holder:"h",age:2,complete:true,member_list:{rev:3},
  members:[{name:"h",holder:true,state:"ok"},{name:"m-1",state:"ok",age:2,reaches:["v:a"],skew:1},{name:"m-2",state:"stale",age:99,error:P}],
  topology:{rev:4,centre:"",star:[],via:{"m-2":"m-1"},by:"ann"},knocking:[{name:"m-9",times:3,last:1,fingerprint:"ab:cd"}]};
b.FIX["/domain/alarms"]={complete:false,sentence:"m-2 did not answer",events:[{t:1,kind:"silent",subsystem:"testsub",member:"m-1",unit:"7",note:P}]};
b.FIX["/api/held"]={cluster:"m-1",holder:{holder:"h",term:5,url:"http://h:8070",kid:"k1",sig:"s"},term:5,keys:{doc:"{}"},backup:{term:4,rev:9}};
b.FIX["/domain/keys"]={vars:[{key:"domain/x"}]};
(async()=>{
const w=b.boot();const errs=[];w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
let asked=[];w.confirm=q=>{asked.push(q);return true};
await b.ready(600);await w.pc.ready;const d=w.document,pc=w.pc,out={};
const main=()=>d.querySelector("main").textContent;
const btn=re=>[...d.querySelectorAll(".pc-main button")].find(x=>re.test(x.textContent));
(d.querySelector('.pc-rail [data-s="units"]').click(),d.querySelector('.pc-layout').click(),d.querySelector('[data-layout="servers"]').click());await b.ready(30);
out.treeMembers=!!d.querySelector('[data-ref="member:m-1"]')&&!!d.querySelector('[data-ref="domain"]');
pc.select("server:s-1");await b.ready(30);
// где держатель и копия — из GET /api/held (дверь процесса, §10a), не /domain/held
out.holderAndBackup=/held by h · term 5/.test(main())&&/backup copy of the domain: rev 9 of term 4\./.test(main())&&!d.querySelector('.pc-main a[href="http://h:8070"]');   // the record's url is the agents' door, not a page
pc.select("domain");await b.ready(30);
out.holderInHead=/holder is h/.test(d.querySelector(".pc-hd").textContent);
const it=n=>[...d.querySelectorAll(".pc-main .it")].find(x=>x.textContent.trim().startsWith(n));
out.memberBadges=/publishes/.test(it("m-1").textContent)&&/silent 99 s/.test(it("m-2").textContent)&&/revision 3/.test(main());
out.alarmWords=/nobody sees it/.test(main())&&/m-2 did not answer/.test(main());
let n=w.__calls.length;asked=[];btn(/^Admit$/).click();await b.ready(80);
out.admitAsksFingerprint=/ab:cd/.test(asked[0]||"")&&w.__calls.slice(n).some(x=>x.path==="/domain/members"&&x.body.fingerprint==="ab:cd");
// перенос без уходящего держателя — по файлу восстановления (ADR-0031): диалог с файлом и «украден»; без файла не уходит
pc.select("server:s-1");await b.ready(30);n=w.__calls.length;btn(/Move the domain here/).click();await b.ready(30);
const dlg=d.querySelector(".pc-dialog-f");dlg.requestSubmit();await b.ready(40);
out.moveNeedsTheFile=!w.__calls.slice(n).some(x=>x.path==="/domain/move");
btn(/Move the domain here/).click();await b.ready(30);
Object.defineProperty(dlg.elements.recovery,"files",{value:[new w.File(['{"domain":"d1","root":"k"}'],"recovery.json")]});
dlg.elements.stolen.value="1";dlg.requestSubmit();await b.ready(80);
const mv=w.__calls.slice(n).find(x=>x.path==="/domain/move");
out.moveByRecoveryFile=!!mv&&mv.body.recovery==='{"domain":"d1","root":"k"}'&&mv.body.stolen===true&&Object.keys(mv.body).length===2;
// топология: m-1 звездой, записать с base_rev 4
pc.select("domain");await b.ready(30);
const star=d.querySelector('[data-tstar="m-1"]');star.checked=true;star.dispatchEvent(new w.Event("change"));
n=w.__calls.length;d.querySelector('[data-t="save"]').click();await b.ready(80);
const c=w.__calls.slice(n).find(x=>x.path==="/domain/topology");
out.topologyPut=!!c&&c.body.base_rev===4&&JSON.stringify(c.body.star)==='["m-1"]'&&c.body.via["m-2"]==="m-1";
pc.select("domain");await b.ready(30);d.querySelector('.pc-tabs [data-tab="keys"]').click();await b.ready(80);
out.keysShown=/domain\/x/.test(main())&&/Other keys/.test(main());
d.querySelector('.pc-tabs [data-tab="general"]').click();await b.ready(30);
pc.select("member:m-2");await b.ready(30);
out.memberCard=[...d.querySelectorAll(".pc-main input")].some(x=>/via relay m-1/.test(x.value))&&!!btn(/Take out of the domain/);
n=w.__calls.length;btn(/Take out of the domain/).click();await b.ready(80);
out.leaveSent=w.__calls.slice(n).some(x=>x.method==="DELETE"&&x.path==="/domain/members/m-2");
pc.select("member:h");await b.ready(30);
out.holderNoLeave=!btn(/Take out/);
out.neverRan=w.__pwned===undefined&&!d.querySelector("img");
out.errors=errs;
b.report(out,["errors"]);
try{fs.unlinkSync(TMP)}catch(e){}
process.exit(0);
})();
