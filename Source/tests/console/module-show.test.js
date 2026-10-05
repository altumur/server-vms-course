// servers.show (контракт §8): таблицы подсистемы на «Обзоре» сервера — строки, у которых `by` равно имени сервера,
// колонки словами display.fields, секрет маской; страница, закрывшая место своим блоком (addBlock covers), таблицу
// не получает.
const fs=require("fs"),path=require("path");
const SRC=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
function page(covers){const TMP=path.join(require("os").tmpdir(),"pc-show-"+process.pid+(covers?"c":"")+".html");
  fs.writeFileSync(TMP,`<!doctype html><div id="app"></div><script>${SRC}</script><script>window.pc=PlatformConsole.mount(document.getElementById("app"),{lang:"en",poll_s:0});${covers?`window.pc.addBlock("server",{id:"mine",covers:"testsub/places",render:h=>{h.innerHTML="<div class='mine'>mine</div>"}});`:""}</script>`);return TMP}
const b=require("./boot");
function fix(){for(const k of Object.keys(b.FIX))delete b.FIX[k];
b.FIX["/session"]={open:true};
b.FIX["/spec"]={name:"testsub",rows:"things",id:"numeric",fields:[{name:"name",type:"string"}],servers:{show:[{table:"places",by:"server",title:"places",columns:["name","size","key_secret"]}]},display:{fields:{size:"Size"}}};
b.FIX["/things"]={configured:[],rows:[]};
b.FIX["/places"]={places:[{name:"p-1",server:"s-1",size:5,key_secret:"***"},{name:"p-2",server:"s-2",size:7}]};
b.FIX["/servers"]={servers:{"s-1":{resource:"live",workers:[]}},policy:{}};}
(async()=>{const out={};
for(const covers of [false,true]){
  fix();process.env.CONSOLE_FILE=page(covers);delete require.cache[require.resolve("./boot")];const bb=require("./boot");Object.assign(bb.FIX,b.FIX);
  const w=bb.boot();await bb.ready(600);await w.pc.ready;const d=w.document;
  w.pc.select("server:s-1");await bb.ready(80);const m=d.querySelector("main");
  if(!covers){const t=m.querySelector('.pc-show[data-table="testsub/places"]');
    out.tableShown=!!t&&/Places/.test(t.textContent)&&/p-1/.test(t.textContent)&&!/p-2/.test(t.textContent);
    out.wordsFromDisplay=!!t&&[...t.querySelectorAll("th")].map(x=>x.textContent).join("|")==="name|Size|key_secret";
    out.secretMasked=!!t&&/\*\*\*/.test(t.textContent);}
  else{out.coveredNotDrawn=!m.querySelector(".pc-show")&&!!m.querySelector(".mine");}
}
b.report(out,[]);process.exit(0);
})();
