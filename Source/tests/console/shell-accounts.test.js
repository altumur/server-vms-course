// C5: the VMS owns this access card; requests pass through the real module's api().
// Exercise the DOM and HTTP boundary, including late answers, rather than its private helpers.
const assert=require("node:assert/strict"),b=require("./boot");
for(const key of Object.keys(b.FIX))delete b.FIX[key];
b.FIX["/session"]={open:true};
b.FIX["/manifest"]={name:"cam",rows:"cameras",id:"numeric",fields:[]};
b.FIX["/cameras"]={configured:[],rows:[]};
b.FIX["/servers"]={servers:{},policy:{}};
b.FIX["/domain/users"]={users:[]};
b.FIX["/domain/grants"]={grants:{}};
b.FIX["/domain/break-glass"]={clusters:{}};
const deferred=()=>{let resolve;const promise=new Promise(r=>{resolve=r});return{promise,resolve}};
const response=(status,body)=>({ok:status>=200&&status<300,status,headers:{get:()=>"application/json"},json:async()=>body});
async function until(test,message){for(let i=0;i<100;i++){if(test())return;await b.ready(10)}assert.fail(message)}
(async()=>{
  const w=b.boot(),errors=[];
  w.addEventListener("error",e=>errors.push(String(e.error||e.message)));
  try{
    await w.platformConsole.ready;
    const pc=w.platformConsole,d=w.document,original=w.fetch;
    pc.retryWaits=[];w.confirm=()=>true;
    // Turn off the independent module poll (every poll_s of the page), so the held-response assertions control repaint explicitly.
    for(let id=1;id<10000;id++)w.clearInterval(id);
    const attack=`wall\"'><img src=x onerror=window.__accountXSS=1>`;
    let metadata=[{name:"wall"},{name:attack,disabled:true,at:1700000000,by:attack,password_secret:"NEVER-RENDER"}];
    const calls=[];
    let intercept=null,passwordNumber=0;
    w.fetch=async(url,init={})=>{
      const path=String(url);
      if(!path.startsWith("/live/accounts"))return original(url,init);
      const call={method:init.method||"GET",path,body:init.body===undefined?undefined:JSON.parse(init.body),headers:init.headers||{}};
      calls.push(call);
      if(intercept){const handled=intercept(call);if(handled)return await handled}
      if(call.method==="GET")return response(200,{accounts:metadata});
      const name=path==="/live/accounts"?call.body.name:decodeURIComponent(path.slice("/live/accounts/".length).split("/")[0]);
      if(call.method==="POST"){
        if(path==="/live/accounts")metadata.push({name});
        return response(200,{account:name,password:`one-time-${++passwordNumber}-<&\"`});
      }
      if(call.method==="PUT"){
        metadata=metadata.map(row=>row.name===name?{...row,disabled:call.body.disabled}:row);
        return response(200,{account:name,disabled:call.body.disabled});
      }
      metadata=metadata.filter(row=>row.name!==name);
      return response(200,{account:name,deleted:true,grants_changed:["room-a"]});
    };
    const main=()=>d.querySelector("main"),host=()=>main().querySelector(".vms-accounts");
    const button=action=>host().querySelector(`[data-account="${action}"]`);
    const row=name=>[...host().querySelectorAll("tbody tr")].find(tr=>tr.cells[0].textContent===name);
    const action=(name,kind)=>row(name).querySelector(`[data-account="${kind}"]`);
    const input=()=>host().querySelector(".vms-account-password");
    const settled=()=>host()&&!host().querySelector('[role="status"]')&&!button("reload").disabled;
    const open=async()=>{
      const access=d.querySelector('[data-s="access"]');
      if(!access.classList.contains("on")){access.click();await b.ready(20)}
      pc.select("streamaccounts:local");await until(settled,"account list did not settle");
    };
    const submit=name=>{
      const form=host().querySelector("form");form.elements.name.value=name;
      form.elements.name.dispatchEvent(new w.Event("input"));
      form.dispatchEvent(new w.Event("submit",{cancelable:true}));
    };
    d.querySelector('[data-s="access"]').click();await b.ready(30);
    const node=d.querySelector('.pc-tree [data-ref="streamaccounts:local"]');
    assert.ok(node,"the account entry belongs to access");node.click();await until(settled,"initial list");
    assert.equal(row("wall").cells[1].textContent,"Включена","omitted false is enabled");
    assert.equal(row("wall").cells[2].textContent,"—","omitted at is absent");
    assert.equal(row("wall").cells[3].textContent,"—","omitted by is absent");
    assert.equal(row(attack).cells[3].textContent,attack);
    assert.ok(!d.querySelector("img")&&!w.__accountXSS,"metadata is escaped");
    assert.ok(!d.body.innerHTML.includes("NEVER-RENDER"),"list secrets are never rendered");

    // Only the mutation answer reveals a secret. It is absent from HTML snapshots and browser storage.
    submit("new-wall");await until(()=>settled()&&input(),"create password");
    const first=input(),firstPassword=first.value;
    assert.ok(firstPassword.startsWith("one-time-1"));
    assert.equal(first.getAttribute("value"),null);
    assert.ok(!d.body.innerHTML.includes(firstPassword));
    assert.ok(!JSON.stringify(w.localStorage).includes(firstPassword)&&!JSON.stringify(w.sessionStorage).includes(firstPassword));
    const made=calls.find(call=>call.method==="POST"&&call.path==="/live/accounts");
    assert.deepEqual(made.body,{name:"new-wall"});assert.ok(made.headers["Idempotency-Key"]);
    assert.equal(made.headers["Content-Type"],"application/json");
    host().querySelector(".vms-account-secret button").click();
    assert.equal(first.value,"");assert.equal(input(),null);
    button("reload").click();await until(settled,"reload after create");assert.equal(input(),null,"GET cannot recover the password");

    action("wall","password").click();await until(()=>settled()&&input(),"reset password");
    const reset=calls.find(call=>call.method==="POST"&&call.path==="/live/accounts/wall/password");
    assert.ok(reset.headers["Idempotency-Key"]);assert.equal(reset.body,undefined);
    const resetInput=input();assert.ok(resetInput.value.startsWith("one-time-2"));
    action("wall","toggle").click();await until(settled,"disable");
    assert.equal(resetInput.value,"");assert.equal(row("wall").cells[1].textContent,"Отключена");
    assert.deepEqual(calls.find(call=>call.method==="PUT").body,{disabled:true});
    action("wall","toggle").click();await until(settled,"enable");
    assert.deepEqual(calls.filter(call=>call.method==="PUT").at(-1).body,{disabled:false});
    w.confirm=()=>false;let before=calls.length;action("wall","delete").click();await b.ready(10);
    assert.equal(calls.length,before,"cancelled deletion sends nothing");
    w.confirm=()=>true;action("wall","delete").click();await until(settled,"delete");
    assert.ok(!row("wall"));const deleted=calls.find(call=>call.method==="DELETE");
    assert.equal(deleted.path,"/live/accounts/wall");assert.equal(deleted.body,undefined);

    // Names stay data in both HTML and URLs. Even hostile metadata cannot become a route suffix.
    action(attack,"password").click();await until(()=>settled()&&input(),"encoded reset");
    assert.ok(calls.some(call=>call.path==="/live/accounts/"+encodeURIComponent(attack)+"/password"));
    assert.equal(host().querySelector(".vms-account-secret strong").textContent,attack);
    assert.ok(!d.querySelector("img")&&!w.__accountXSS);
    const leaving=input();d.querySelector('[data-s="journal"]').click();await until(()=>leaving.value==="","leaving removes the secret");
    await open();assert.equal(input(),null);

    // Both reads and writes report refusals in the current card, without rendering server text as markup.
    for(const status of [403,409,503]){
      intercept=call=>call.method==="POST"?response(status,{detail:`refusal-${status} <img src=x onerror=bad()>`}):null;
      submit("refused-"+status);await until(()=>settled()&&host().querySelector('[role="alert"]'),"mutation refusal "+status);
      assert.ok(host().querySelector('[role="alert"]').textContent.includes("refusal-"+status));
      assert.equal(input(),null);assert.ok(!d.querySelector("img"));
    }
    intercept=call=>call.method==="GET"?response(503,{detail:"account list unavailable"}):null;
    button("reload").click();await until(()=>settled()&&host().querySelector('[role="alert"]'),"list unavailable");
    assert.equal(host().querySelectorAll("tbody tr").length,0,"unknown list does not present old metadata as current");
    assert.ok(host().textContent.includes("503: account list unavailable"));
    intercept=null;await open();

    // A late GET of a detached card cannot overwrite a newer list, including after returning to the same entry.
    const lateList=deferred();let held=false;
    intercept=call=>call.method==="GET"&&!held?(held=true,lateList.promise):null;
    pc.select("streamaccounts:local");await until(()=>held,"held GET");
    metadata=[{name:"fresh"}];await open();
    lateList.resolve(response(200,{accounts:[{name:"stale"}]}));await b.ready(30);
    assert.ok(row("fresh")&&!row("stale"));
    intercept=null;

    // Double submissions are blocked; a late mutation answer never leaks its password into another view.
    const lateWrite=deferred();let writes=0;
    intercept=call=>call.method==="POST"?(writes++,lateWrite.promise):null;
    const oldForm=host().querySelector("form");submit("late-wall");
    oldForm.dispatchEvent(new w.Event("submit",{cancelable:true}));
    await until(()=>writes===1,"one write only");
    assert.ok(button("reload").disabled,"a mutation owns the current card until its answer");
    pc.select("grants:domain");await open();
    lateWrite.resolve(response(200,{account:"late-wall",password:"LATE-SECRET"}));await b.ready(30);
    assert.equal(writes,1);assert.equal(input(),null);assert.ok(!d.body.textContent.includes("LATE-SECRET"));
    assert.ok(row("fresh"));
    assert.ok(calls.every(call=>call.path==="/live/accounts"||call.path.startsWith("/live/accounts/")));
    assert.deepEqual(errors,[]);
    console.log("shell-accounts: metadata, CRUD, one-time secret, escaping, refusals, stale reads/writes and duplicate submission passed");
  }finally{w.close()}
})().catch(error=>{console.error(error);process.exitCode=1});
