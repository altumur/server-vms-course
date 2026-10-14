// C5: a worker-owned object table keeps its existing read-only server display, with no mutation controls or calls.
const fs=require("fs"),path=require("path");
const SRC=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"pc-worker-table-"+process.pid+".html");
fs.writeFileSync(TMP,`<!doctype html><div id="app"></div><script>${SRC}</script><script>window.pc=PlatformConsole.mount(document.getElementById("app"),{lang:"en",poll_s:0});</script>`);
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const key of Object.keys(b.FIX))delete b.FIX[key];
b.FIX["/session"]={open:true};
b.FIX["/spec"]={name:"testsub",rows:"things",id:"numeric",fields:[{name:"name",type:"string"}],
  servers:{show:[{table:"entries",by:"server",title:"Discovered",columns:["name","size","identity"]}]}};
b.FIX["/things"]={configured:[],rows:[]};
b.FIX["/servers"]={servers:{"s-1":{workers:[],resource:"live"}},policy:{}};
b.FIX["/entries"]={entries:[{name:"one",server:"s-1",size:7,identity:"serial-one"},
  {name:"other",server:"s-2",size:9,identity:"serial-other"}]};
(async()=>{
  const w=b.boot(),errors=[];w.addEventListener("error",e=>errors.push(String(e.error||e.message)));
  await b.ready(400);await w.pc.ready;w.pc.select("server:s-1");await b.ready(100);
  const table=w.document.querySelector('.pc-show[data-table="testsub/entries"]');
  const out={readStillShown:!!table&&/Discovered/.test(table.textContent)&&/serial-one/.test(table.textContent)&&/7/.test(table.textContent),
    otherServerExcluded:!!table&&!/serial-other/.test(table.textContent),
    noMutationControls:!!table&&!table.querySelector("form,input,textarea,select,button"),
    noMutationRequests:!w.__calls.some(call=>call.path.startsWith("/entries")),noErrors:errors.length===0,errors};
  b.report(out);fs.unlinkSync(TMP);w.close();process.exit(Object.values(out).some(value=>value===false)?1:0);
})();
