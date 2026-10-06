// Вкладка «Ключи» домена (ADR-0062): строка — ключ и ИМЕНА её полей; значение — только у публичных половин ключей
// домена (public); строка, которую вид не показывает, — причиной (withheld); объект — ключ, размер, возраст, без тела.
// Что лежит в строке, вкладка не показывает: значений, кроме public, на странице нет.
const fs=require("fs"),path=require("path");
const PAGE=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.html"),"utf8");
const MOD=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const TMP=path.join(require("os").tmpdir(),"pc-keys-"+process.pid+".html");
fs.writeFileSync(TMP,PAGE.replace(/<script src="\/platform\/console\.js\?v=1"><\/script>/,()=>`<script>${MOD}</script>`)
  .replace('PlatformConsole.mount(document.getElementById("app"))','PlatformConsole.mount(document.getElementById("app"), { lang: "ru", poll_s: 0 })'));
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
b.FIX["/session"]={open:true};
b.FIX["/spec"]={name:"testsub",rows:"things",id:"numeric",fields:[{name:"name",type:"string"}]};
b.FIX["/things"]={configured:[],rows:[]};
b.FIX["/domain"]={holder:"h",age:1,complete:true,members:[{name:"h",holder:true,state:"ok"}],topology:{rev:1}};
b.FIX["/domain/keys"]={vars:[
  {key:"domain/root",index:"7",fields:["pub","seal"],public:{pub:"ed25519:AAAA"}},
  {key:"domain/vms/primaries",index:"9",fields:["SN-A","SN-B"]},
  {key:"domain/secret-thing",withheld:"a sealed row"}],
  objects:[{key:"domain/view",size:2048,age:3}]};
(async()=>{
  const w=b.boot();const errs=[];w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
  await b.ready(400);const pc=w.platformConsole;await pc.ready;const d=w.document,out={};
  pc.select("domain");await b.ready(60);
  d.querySelector('.pc-tabs [data-tab="keys"]').click();await b.ready(120);
  const tab=d.querySelector('.pc-tab[data-tab="keys"]'),t=tab.textContent;
  const row=k=>[...tab.querySelectorAll(".dk-key")].find(x=>x.querySelector("code").textContent===k);
  out.drawnNotStuck=!/Спрашиваем консоль/.test(t)&&!!row("domain/view");
  out.fieldNamesShown=/поля: 2/.test(row("domain/vms/primaries").textContent)&&/SN-A/.test(row("domain/vms/primaries").textContent)&&!row("domain/vms/primaries").querySelector("pre");
  out.publicHalfShownOnlyIt=row("domain/root").querySelectorAll("pre").length===1&&/ed25519:AAAA/.test(row("domain/root").textContent)&&/seal/.test(row("domain/root").textContent);
  out.withheldSaysWhy=/не показана: a sealed row/.test(row("domain/secret-thing").textContent);
  out.objectByKeySizeAge=/2\.0 КБ|2048|2\.0/.test(row("domain/view").textContent)&&/3/.test(row("domain/view").textContent)&&!row("domain/view").querySelector("pre,details");
  out.errors=errs;out.noErrors=!errs.length;
  b.report(out);
  try{fs.unlinkSync(TMP)}catch(e){}
  process.exit(0);
})();
