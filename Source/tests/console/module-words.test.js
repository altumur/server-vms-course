// Словарь модуля W (P/07 Н1.5 words: «W — словарь модуля ru | en»): у ru и en одни и те же ключи на всех уровнях,
// каждое слово, которое модуль берёт из W (W.<ключ>, W.n.<ключ>, W.kinds[…]), есть в обоих языках и не пусто; у каждого
// вида события, который модуль описывает сам (eventNote), и у видов command / command.failed (Н1.5 commands) есть слово
// в W.kinds; слова исхода команды (выполнена, отказ, истекла, неизвестно, «поздно», «кто:») — в W.n, по-русски так, как
// их называет норма. На странице kindWord в обоих языках даёт слово словаря, не вид. Предметные слова в словаре —
// module-contract (vocabularyClean). Аудит покрытия P/07 (90661897f).
const fs=require("fs"),path=require("path"),vm=require("vm");
const SRC=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
const out={};
// словарь — литерал const WORDS = {…} модуля, вычисленный отдельно
const m=/\n  const WORDS = (\{[\s\S]*?\n  \});\n/.exec(SRC);
out.dictFound=!!m;
const WORDS=m?vm.runInNewContext("("+m[1]+")"):{};
out.twoLanguages=Object.keys(WORDS).sort().join(",")==="en,ru";
const en=WORDS.en||{},ru=WORDS.ru||{};
// одни и те же ключи на всех уровнях
// путь — список ключей (у видов в W.kinds точка внутри ключа): [путь, слово]
const paths=(o,pre)=>Object.entries(o).flatMap(([k,v])=>v&&typeof v==="object"&&!Array.isArray(v)?paths(v,pre.concat(k)):[[pre.concat(k),v]]);
const leaves={en:paths(en,[]),ru:paths(ru,[])};
const pe=new Set(leaves.en.map(([p])=>JSON.stringify(p))),pr=new Set(leaves.ru.map(([p])=>JSON.stringify(p)));
const onlyEn=[...pe].filter(x=>!pr.has(x)),onlyRu=[...pr].filter(x=>!pe.has(x));
out.sameKeys=onlyEn.length===0&&onlyRu.length===0;out.onlyEn=onlyEn.slice(0,8).join(", ");out.onlyRu=onlyRu.slice(0,8).join(", ");
const at=(o,p)=>p.split(".").reduce((x,k)=>x==null?x:x[k],o);
const said=v=>typeof v==="string"?v.trim()!=="":typeof v==="function"||Array.isArray(v)?true:v!=null;
out.noEmptyWord=leaves.en.every(([,v])=>said(v))&&leaves.ru.every(([,v])=>said(v));
// каждое слово, которое модуль берёт: W.<ключ>, W.n.<ключ> (и n.<ключ> в описании событий, где n = W.n)
const body=SRC.slice(m?m.index+m[0].length:0).replace(/^\s*\/\/.*$/gm,"");
const used=new Set([...body.matchAll(/\bW\.([A-Za-z_]\w*)(?:\.([A-Za-z_]\w*))?/g)].map(x=>x[1]==="n"&&x[2]?"n."+x[2]:x[1]));
const noteFn=(/const eventNote = e => \{([\s\S]*?)\n    \};/.exec(SRC)||[,""])[1];
for(const x of noteFn.matchAll(/\bn\.([A-Za-z_]\w*)/g))used.add("n."+x[1]);
const missing=[...used].filter(p=>p!=="kinds"&&p!=="n"&&(at(en,p)===undefined||at(ru,p)===undefined));
out.everyUsedWordInBoth=used.size>50&&missing.length===0;out.missingWords=missing.slice(0,8).join(", ");
// виды, которые модуль описывает сам (eventNote), и command / command.failed — со словом в обоих языках
const kinds=new Set(["command","command.failed",...[...noteFn.matchAll(/k === "([a-z_.]+)"/g)].map(x=>x[1])]);
const noWord=[...kinds].filter(k=>!said((en.kinds||{})[k])||!said((ru.kinds||{})[k]));
out.everyNotedKindHasWord=kinds.size>5&&noWord.length===0;out.kindsWithoutWord=noWord.join(", ");
// семьи видов в eventNote по образцу (server.decommission*, worker.hung|hung_moved|released_by_controller) — слова есть
out.kindFamiliesHaveWords=["server.decommission_requested","server.decommission_withdrawn","server.decommissioned","server.decommission_refused","worker.hung","worker.hung_moved","worker.released_by_controller"].every(k=>said((en.kinds||{})[k])&&said((ru.kinds||{})[k]));
// исход команды (Н1.5 commands: action · исход · ответ · «кто: by»; late → «поздно»)
const outcome=["performed","refusedW","expired","unknownOutcome","late","byW"];
out.outcomeWords=outcome.every(k=>said((en.n||{})[k])&&said((ru.n||{})[k]));
out.ruLateIsPozdno=/^поздно/.test((ru.n||{}).late||"");
out.ruByIsKto=(ru.n||{}).byW==="кто:";
// на странице: kindWord в обоих языках — слово словаря модуля этого языка
const TMP=path.join(require("os").tmpdir(),"pc-words-"+process.pid+".html");
process.env.CONSOLE_FILE=TMP;
const b=require("./boot");
for(const k of Object.keys(b.FIX))delete b.FIX[k];
b.FIX["/session"]={open:true};
b.FIX["/manifest"]={name:"testsub",rows:"things",id:"numeric",fields:[{name:"name",type:"string"}]};
b.FIX["/things"]={configured:[],rows:[]};
b.FIX["/servers"]={servers:{},policy:{}};
(async()=>{
const errs=[];
for(const lang of ["en","ru"]){
  fs.writeFileSync(TMP,`<!doctype html><div id="app"></div><script>${SRC}</script><script>window.pc=PlatformConsole.mount(document.getElementById("app"),{lang:"${lang}"});</script>`);
  const w=b.boot();w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
  await w.pc.ready;await b.ready(100);
  const dict=WORDS[lang].kinds||{};
  out["kindWord_"+lang]=Object.keys(dict).length>5&&Object.keys(dict).every(k=>w.pc.kindWord({kind:k})===dict[k]&&dict[k]!==k);
  w.close();
}
out.errors=errs;
b.report(out,["errors","onlyEn","onlyRu","missingWords","kindsWithoutWord"]);
try{fs.unlinkSync(TMP)}catch(e){}
process.exit(0);
})();
