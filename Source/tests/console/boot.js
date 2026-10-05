// Загрузка консоли курса в jsdom с поддельным API (копия продуктового vms/consoletest/boot.js; другое здесь — путь страницы).
const fs=require("fs");const{JSDOM}=require("jsdom");
// Страница по умолчанию — страница VMS курса, Source/vms/shell.html (корень при CONSOLE_ROOT=vms), с модулем платформы (w2cplatform/console.js), вписанным на
// место своего <script src>: в jsdom нет сервера, который его отдал бы. CONSOLE_FILE — другая страница (модуль на
// фиктивной подсистеме, платформенная страница, копия до правки).
const FILE=process.env.CONSOLE_FILE||(()=>{
  const path=require("path"),os=require("os");
  const page=fs.readFileSync(path.join(__dirname,"..","..","vms","shell.html"),"utf8"),mod=fs.readFileSync(path.join(__dirname,"..","..","w2cplatform","console.js"),"utf8");
  const tmp=path.join(os.tmpdir(),"shell-boot-"+process.pid+".html");
  fs.writeFileSync(tmp,page.replace(/<script src="\/platform\/console\.js\?v=1"><\/script>/,()=>`<script>${mod}</script>`));
  process.on("exit",()=>{try{fs.unlinkSync(tmp)}catch(e){}});
  return tmp;
})();
const FIX={
 "/spec":{subsystems:{vms:{},rec:{}}},
 "/cameras":{configured:[
   {id:"1",name:"Главный вход",source:"ipint://10.0.0.11/Hikvision/DS-2CD2143G2",enabled:true,labels:[],folders:["Офис/Вход"],priority:100,live:"always"},
   {id:"2",name:"Парковка",source:"ipint://10.0.0.12/Axis/P3245",enabled:true,labels:["vlan:cctv"],folders:["Офис/Улица","Периметр"],priority:100,live:"always"}],
  rows:[{id:"1",worker:"vms-1",running:true},{id:"2",worker:"vms-1",running:true}]},
 "/servers":{servers:{"box-a":{workers:[{worker:"vms-1",sub:"vms",capacity:50,load:2,seen:1}],resource:"live",address:"10.0.0.1"}},policy:{min:1,max:4}},
 "/resources":{"box-a":{cpu:12,mem:40}},
 "/policy":{choices:{},min:1,max:4},
 "/mounts":{rec:"/rec"},
 "/rec/volumes":{volumes:[],wanted:0,serving:0,spare:0,needed:0,suggested:[]},
 "/rec/recordings":{recordings:[]},
 "/auto/rules":{rules:[]},
 "/admin":{instance:"vmsdev"},
 "/unplaceable":[],
 "/drain":{draining:"",safe:true,subsystems:{}},
 "/schema":{}
};
function boot(opts={}){
  const dom=new JSDOM(fs.readFileSync(FILE,"utf8"),{runScripts:"dangerously",url:"http://localhost/",
    beforeParse(w){
      w.matchMedia=()=>({matches:false,addListener(){},removeListener(){},addEventListener(){},removeEventListener(){}});
      w.requestAnimationFrame=cb=>setTimeout(cb,0);
      Object.defineProperty(w,"innerWidth",{value:1600,configurable:true});
      w.__calls=[];   // что страница отправила не чтением: метод, путь, тело
      w.fetch=(url,init)=>{
        const path=String(url).split("?")[0].replace(/^https?:\/\/[^/]+/,"");
        if(init&&init.method&&init.method!=="GET")w.__calls.push({method:init.method,path,body:init.body?JSON.parse(init.body):null,key:(init.headers||{})["Idempotency-Key"]||""});
        const has=Object.prototype.hasOwnProperty.call(FIX,path);
        // Чего в наборе нет, того нет и у сервера: /domain в обычном кластере отвечает 404.
        if(!has&&!opts.miss)return Promise.resolve({ok:false,status:404,headers:{get:()=>"application/json"},
          json:()=>Promise.resolve({error:"not found"}),text:()=>Promise.resolve('{"error":"not found"}')});
        const body=has?FIX[path]:opts.miss;
        return Promise.resolve({ok:true,status:200,headers:{get:()=>"application/json"},
          json:()=>Promise.resolve(body),text:()=>Promise.resolve(JSON.stringify(body))});
      };
    }});
  return dom.window;
}
async function ready(ms=400){return new Promise(r=>setTimeout(r,ms))}
function report(out,skip=[]){
  const bad=Object.entries(out).filter(([k,v])=>k!=="errors"&&!skip.includes(k)&&v!==true);
  console.log(JSON.stringify(out,null,1));
  console.log(bad.length?"FAILED: "+bad.map(([k])=>k).join(", "):"все проверки пройдены");
}
module.exports={boot,ready,report,FIX};
