// «Не размещены»: единицы без воркера — каждая со своим «почему» из /unplaceable (метки, которые не покрывает ни
// один живой воркер, или живых воркеров нет), и сети серверов; то же «почему» — в «Размещении» карточки единицы.
const fs=require("fs"),path=require("path");
const SRC=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"pc-unpl-"+process.pid+".html");
fs.writeFileSync(TMP,`<!doctype html><div id="app"></div><script>${SRC}</script><script>window.pc=PlatformConsole.mount(document.getElementById("app"),{lang:"en"});</script>`);
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
b.FIX["/session"]={open:true};
b.FIX["/spec"]={name:"testsub",rows:"things",id:"numeric",fields:[{name:"name",type:"string"},{name:"labels",type:"list"}],display:{units:"things"}};
b.FIX["/things"]={configured:[{id:1,name:"gate",labels:["vlan:x"]},{id:2,name:"door"},{id:3,name:"roof"}],rows:[{id:3,worker:"w-1",phase:"running"}]};
b.FIX["/unplaceable"]=[{id:1,labels:["vlan:x"],workers_live:2}];
b.FIX["/servers"]={servers:{"s-1":{resource:"live",labels:["vlan:a"],labels_source:"console",workers:[{worker:"w-1",load:1,capacity:5,state:"live"}]}},policy:{}};
b.FIX["/events"]={events:[],state:"live"};
(async()=>{
const w=b.boot();const errs=[];w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
await b.ready(600);await w.pc.ready;const d=w.document,pc=w.pc,out={};
const main=()=>d.querySelector("main");
(d.querySelector('.pc-rail [data-s="units"]').click(),d.querySelector('.pc-layout').click(),d.querySelector('[data-layout="servers"]').click());await b.ready(30);
out.rowInTree=/2/.test((d.querySelector('.pc-tree [data-ref="unplaced"] .cnt')||{}).textContent||"");
pc.select("unplaced");await b.ready(60);
const it=n=>[...main().querySelectorAll(".it")].find(x=>x.textContent.includes(n));
out.listed=!!it("gate")&&!!it("door")&&!it("roof")&&/Things without a worker/.test(main().textContent);
out.whyLabels=/none of the 2 live workers covers the labels: vlan:x/.test(it("gate").textContent)&&!/live workers/.test(it("door").textContent);
out.serversNets=/vlan:a/.test(it("s-1").textContent)&&/set in the console/.test(it("s-1").textContent);
it("gate").click();await b.ready(60);
out.opensUnit=pc.selected()==="unit:testsub/1"&&/Not placed: none of the 2 live workers/.test(main().textContent);
out.errors=errs;
b.report(out,["errors"]);
try{fs.unlinkSync(TMP)}catch(e){}
process.exit(0);
})();
