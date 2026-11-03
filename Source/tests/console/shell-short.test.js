// Оболочка корня cam после замены страницы VMS (канон VMS/01-cam/cam.shell.html; V/11.15 Н1.1; ADR-0112 доп. (19)–(22)):
// ссылка «Консоль VMS» на /backend/, модуль платформы P/07 по /platform/console.js?v=1, один mount в #app с
// sections [units, access, journal] и subsystems — подсистемы /mounts без подсистем VMS (cam, rec, live, det, detjob,
// detedge, auto, assist, exp, backend, psim-*), по возрастанию; /mounts не прочитался или не объект — []; модуль не
// версии 1 — слово в #app и без mount; ни одного обработчика в атрибуте. Модуль здесь подставной: проверяется оболочка.
const fs=require("fs"),path=require("path");const{JSDOM}=require("jsdom");
const PAGE=fs.readFileSync(path.join(__dirname,"..","..","..","VMS","01-cam","cam.shell.html"),"utf8");
const b=require("./boot");
const out={};
const markup=PAGE.replace(/<!--[\s\S]*?-->/g,"");
const inline=[...PAGE.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m=>m[1]);
out.oneInlineScript=inline.length===1;
out.moduleScript=PAGE.includes('<script src="/platform/console.js?v=1"></script>');
out.noInlineHandler=!/\son[a-z]+\s*=/i.test(markup);
// подставной модуль вместо <script src>: в jsdom сервера нет
function run({version=1,fetch}){
  const calls=[];
  const html=PAGE.replace('<script src="/platform/console.js?v=1"></script>',
    "<script>window.PlatformConsole={version:"+version+",mount:(root,opts)=>{window.__calls.push({root:root&&root.id,opts:JSON.parse(JSON.stringify(opts))});return{ready:Promise.resolve()}}};</script>");
  const dom=new JSDOM(html,{runScripts:"dangerously",url:"http://localhost/",beforeParse(w){w.__calls=calls;w.fetch=fetch}});
  return{dom,calls};
}
const json=(body,ok=true)=>()=>Promise.resolve({ok,json:()=>Promise.resolve(body)});
const settle=()=>new Promise(r=>setTimeout(r,50));
const SECTIONS='["units","access","journal"]';
(async()=>{
const errs=[];
// ссылка
{const{dom}=run({fetch:json({mounts:{}})});const a=dom.window.document.querySelector('a[href="/backend/"]');
 out.backendLink=!!a&&a.textContent.trim()==="Консоль VMS";await settle();}
// подсистемы /mounts без VMS, по возрастанию; mount ровно один раз
{const mounts={zeta:{},testsub2:{},cam:{},rec:{},live:{},det:{},detjob:{},detedge:{},auto:{},assist:{},exp:{},backend:{},"psim-acme":{},"psim-x":{},alpha:{}};
 const{calls}=run({fetch:json({root:"cam",mounts})});await settle();
 out.mountedOnce=calls.length===1;
 const c=calls[0]||{opts:{}};
 out.mountRoot=c.root==="app";
 out.mountLang=c.opts.lang==="ru";
 out.mountSections=JSON.stringify(c.opts.sections)===SECTIONS;
 out.subsystemsWithoutVMS=JSON.stringify(c.opts.subsystems)==='["alpha","testsub2","zeta"]';}
// /mounts не прочитался, не 2xx, не объект — []
for(const[name,fetch]of[["mountsRejected",()=>Promise.reject(new Error("net"))],["mountsNotOk",json({mounts:{a:{}}},false)],
                         ["mountsNotObject",json({mounts:"a"})],["mountsAbsent",json({root:"cam"})],["mountsNull",json(null)]]){
  const{calls}=run({fetch});await settle();
  out[name]=calls.length===1&&JSON.stringify(calls[0].opts.subsystems)==="[]"&&JSON.stringify(calls[0].opts.sections)===SECTIONS;
}
// модуль не версии 1 — слово в #app, mount не зовётся
{const{dom,calls}=run({version:2,fetch:json({mounts:{}})});await settle();
 const app=dom.window.document.getElementById("app");
 out.otherVersionSaid=/версии 1/.test(app.textContent)&&/2/.test(app.textContent);
 out.otherVersionNotMounted=calls.length===0;}
out.errors=errs;
b.report(out,["errors"]);
process.exit(0);
})();
