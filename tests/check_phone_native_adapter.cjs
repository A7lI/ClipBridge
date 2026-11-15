const {chromium}=require('playwright');const assert=require('node:assert/strict');const crypto=require('node:crypto');
(async()=>{const b=await chromium.launch({headless:true,executablePath:process.env.CLIPBRIDGE_BROWSER||'C:/Program Files/BraveSoftware/Brave-Browser/Application/brave.exe'});try{const c=await b.newContext();const p=await c.newPage();await p.goto(process.env.CLIPBRIDGE_PHONE_URL||'http://127.0.0.1:8787/phone');const expected=crypto.randomBytes(512*1024+17);const result=await p.evaluate(async bytes=>{
 const saved=[];let current;
 window.ClipBridgePhone={beginSave:(name,type,size,copy)=>{current={name,type,size,copy,parts:[]};return 'ticket'},appendSave:(id,data)=>{const bytes=Uint8Array.from(atob(data),c=>c.charCodeAt(0));if(bytes.length>16384)throw Error('Unbounded native chunk');current.parts.push(bytes);return id==='ticket'},finishSave:()=>{saved.push(current);return true},cancelSave:()=>{throw Error('Unexpected save failure')}};
 const {showFiles}=await import('./files.mjs');
 showFiles([new File([new Uint8Array(bytes)],'native-file.bin',{type:'application/octet-stream'})],message=>{document.getElementById('status').textContent=message});
 document.querySelector('#received-list button').click();
 while(!saved.length)await new Promise(resolve=>setTimeout(resolve,20));
 const raw=new Blob(saved[0].parts);return {name:saved[0].name,copy:saved[0].copy,size:raw.size,bytes:Array.from(new Uint8Array(await raw.arrayBuffer()))};
},Array.from(expected));assert.equal(result.name,'native-file.bin');assert.equal(result.copy,true);assert.deepEqual(Buffer.from(result.bytes),expected);console.log('Android save/copy adapter delivers complete bytes in bounded native chunks.');}finally{await b.close()}})().catch(e=>{console.error(e);process.exitCode=1});
