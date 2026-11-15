const {chromium}=require('playwright');const assert=require('node:assert/strict');
(async()=>{const b=await chromium.launch({headless:true,executablePath:process.env.CLIPBRIDGE_BROWSER||'C:/Program Files/BraveSoftware/Brave-Browser/Application/brave.exe'});try{const c=await b.newContext();const p=await c.newPage();await p.goto(process.env.CLIPBRIDGE_PHONE_URL||'http://127.0.0.1:8787/phone');const result=await p.evaluate(async()=>{
 const {PhoneSession}=await import('./phone-transport.mjs');
 const host=new PhoneSession(),guest=new PhoneSession();
 const connected=session=>new Promise(resolve=>session.addEventListener('connected',resolve,{once:true}));
 const h=connected(host),g=connected(guest);
 await host.online('host');const captures=[];const send=host.socket.send.bind(host.socket);host.socket.send=wire=>{captures.push(new Uint8Array(wire).slice());send(wire)};
 await guest.online('guest',host.secret);await Promise.all([h,g]);
 let deliveries=0;guest.addEventListener('offer',()=>guest.accept(true));
 guest.addEventListener('received',()=>deliveries++);
 await host.send({kind:'text',text:'Private text which must never be plaintext on the relay'},new AbortController().signal);
 const privateWire=captures[captures.length-1];
 const plain=new TextDecoder().decode(privateWire);
 if(plain.includes('Private text'))throw Error('Plaintext leaked');
 const closed=new Promise(resolve=>guest.addEventListener('disconnected',event=>resolve(event.detail.message),{once:true}));
 send(privateWire);const reason=await closed;host.close();return {deliveries,reason};
});assert.equal(result.deliveries,1);assert.match(result.reason,/sequence/);console.log('Authenticated encryption hides plaintext; replay is rejected without a duplicate delivery.');}finally{await b.close()}})().catch(e=>{console.error(e);process.exitCode=1});
