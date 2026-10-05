// Архивы домена в дереве страницы VMS курса, как в консоли продукта: член домена с одной камерой (сервер-камера) стоит
// в дереве своей камерой — строки члена нет, его архивы под камерой, раскрыты с первого показа, на уровень глубже;
// свёрнутое остаётся свёрнутым после опроса. У члена с несколькими камерами — камеры, затем его архивы.
// (Члены — списком контракта модуля, камеры и архивы — units вида курса; см. shell-domain.)
const fs=require("fs"),path=require("path");
const PAGE=fs.readFileSync(path.join(__dirname,"..","..","vms","shell.html"),"utf8");
const MOD=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"shell-darc-"+process.pid+".html");
fs.writeFileSync(TMP,PAGE.replace(/<script src="\/platform\/console\.js\?v=1"><\/script>/,()=>`<script>${MOD}</script>`));
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
const u=(sub,cluster,unit,o={})=>({sub,cluster,unit,ref:"",name:"",server:cluster,worker:"w",phase:"running",worker_state:"live",...o});
b.FIX["/session"]={open:true};
b.FIX["/spec"]={name:"vms",rows:"cameras",id:"numeric",fields:[{name:"name",type:"string"}]};
b.FIX["/cameras"]={configured:[],rows:[]};
b.FIX["/servers"]={servers:{"srv-box":{resource:"live",workers:[]}},policy:{}};
b.FIX["/events"]={events:[],state:"live"};
b.FIX["/domain"]={holder:"srv",age:1,complete:true,members:[{name:"srv",holder:true,state:"ok"},{name:"cam-a",state:"ok",age:2},{name:"office",state:"ok",age:2}],
  units:[u("vms","cam-a","1",{ref:"SN-A",name:"door a"}),u("rec","cam-a","1-sd",{name:"1-sd",phase:"standby"}),
         u("vms","office","1",{ref:"SN-B",name:"hall"}),u("vms","office","2",{ref:"SN-C",name:"lobby"}),u("rec","office","SN-A")],tables:{}};
(async()=>{
const w=b.boot();const errs=[];w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
await b.ready(700);await w.platformConsole.ready;await w.platformConsole.refresh();await b.ready(50);
const d=w.document,pc=w.platformConsole,out={};
(d.querySelector('.pc-rail [data-s="units"]').click(),d.querySelector('.pc-layout').click(),d.querySelector('[data-layout="servers"]').click());await b.ready(40);
const row=r=>d.querySelector(`.pc-tree .n[data-ref="${r}"]`);
const cam=row("dc:cam-a/1"),arc=row("da:cam-a/1-sd");
out.cameraStandsForItsServer=!!cam&&!row("member:cam-a");
out.archiveRowUnderCamera=!!arc&&cam.nextElementSibling===arc;
out.oneLevelDeeper=!!arc&&parseInt(arc.style.paddingLeft)-parseInt(cam.style.paddingLeft)===14;
out.cameraHasChevron=!!cam&&cam.querySelector(".tw").textContent.trim()==="▾";
cam.querySelector(".tw").click();await b.ready(20);
out.collapses=!row("da:cam-a/1-sd");
await pc.refresh();await b.ready(40);
out.staysCollapsed=!row("da:cam-a/1-sd");
// член с несколькими камерами — своей строкой, под ней камеры, затем архивы
const off=row("member:office");
out.officeIsAMember=!!off;
off.querySelector(".tw").click();await b.ready(20);
const names=[...d.querySelectorAll(".pc-tree .n")].map(x=>x.dataset.ref);
const i=r=>names.indexOf(r);
out.camerasThenArchives=i("dc:office/1")>i("member:office")&&i("dc:office/2")>i("member:office")&&i("da:office/SN-A")>i("dc:office/2");
out.errors=errs;
b.report(out,["errors"]);
try{fs.unlinkSync(TMP)}catch(e){}
process.exit(0);
})();
