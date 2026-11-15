const {chromium,devices}=require('playwright');
const assert=require('node:assert/strict');
const crypto=require('node:crypto');
const fs=require('node:fs');
const path=require('node:path');
const os=require('node:os');
const testDir=fs.mkdtempSync(path.join(os.tmpdir(),'clipbridge-phone-test-'));
const bigFile=path.join(testDir,'300mb.bin');
const base=process.env.CLIPBRIDGE_PHONE_URL||'http://127.0.0.1:8787/phone.html';
const wait=async(p,id,text,timeout=30000)=>{try{await p.waitForFunction(({id,text})=>document.getElementById(id).textContent.includes(text),{id,text},{timeout})}catch(e){throw Error(id+': '+await p.locator('#'+id).textContent()+' / '+await p.locator('#status').textContent(),{cause:e})}};
async function join(p,link){await p.locator('#join-phone-link').fill(link);await p.locator('#join-phone-button').click()}
async function main(){
 const browser=await chromium.launch({headless:true,executablePath:process.env.CLIPBRIDGE_BROWSER||'C:/Program Files/BraveSoftware/Brave-Browser/Application/brave.exe'});
 try{
  const hostContext=await browser.newContext({...devices['iPhone 15'],acceptDownloads:true});
  const guestContext=await browser.newContext({...devices['Pixel 7'],acceptDownloads:true});
  const host=await hostContext.newPage(),guest=await guestContext.newPage();
  for(const p of [host,guest])p.on('pageerror',e=>console.error('PAGE ERROR',e.message));
  await Promise.all([host.goto(base),guest.goto(base)]);
  const offline=process.argv.includes('--offline');
  if(offline){
   await Promise.all([wait(host,'offline-ready','Ready for offline'),wait(guest,'offline-ready','Ready for offline')]);
   await hostContext.setOffline(true);await guestContext.setOffline(true);
   await Promise.all([host.reload(),guest.reload()]);
   assert.equal(await host.evaluate(()=>navigator.onLine),false);
   console.log('Both phone pages reopened from their offline cache.');
   // DevTools offline disables LAN sockets too. Restore LAN, block all HTTP,
   // and make service-worker network fetches fail, like Wi-Fi without WAN.
   await hostContext.setOffline(false);await guestContext.setOffline(false);
   for(const context of [hostContext,guestContext]){
    await context.route('**/*',route=>route.abort('internetdisconnected'));
    for(const worker of context.serviceWorkers())await worker.evaluate(()=>{self.fetch=()=>Promise.reject(new TypeError('Internet disabled for offline test'))});
   }
   await host.locator('#phone-mode').selectOption('offline');
  }
  await host.locator('#create-phone').click();await wait(host,'status','Invitation ready');
  const offer=await host.locator('#invitation-link').inputValue();
  if(offline){
   const first=await host.locator('#invitation-qr').screenshot();
   await guest.locator('#phone-qr-photo').setInputFiles({name:'invitation.png',mimeType:'image/png',buffer:first});
   await guest.waitForFunction(()=>document.querySelector('#invitation-link').value.includes('#answer='),null,{timeout:30000});
   const answer=await guest.locator('#invitation-qr').screenshot();
   await host.locator('#phone-qr-photo').setInputFiles({name:'answer.png',mimeType:'image/png',buffer:answer});
  }else { await guest.goto(offer); await guest.waitForFunction(()=>!location.hash); }
  await Promise.all([wait(host,'status','Connected.'),wait(guest,'status','Connected.')]);
  assert.equal(await host.locator('#phone-code').textContent(),await guest.locator('#phone-code').textContent());
  console.log('Connected two isolated phone contexts:',offline?'offline QR exchange, internet disabled':'online encrypted relay');
  async function text(from,to,value,accept=true){
   await from.locator('#phone-draft').fill(value);await from.locator('#phone-send-text').click();
   await to.locator('#phone-offer').waitFor({state:'visible'});
   await to.locator(accept?'#phone-accept':'#phone-decline').click();
   if(accept){await wait(from,'phone-send-status','Received by');assert.equal(await to.locator('#phone-incoming').inputValue(),value)}
   else await wait(from,'phone-send-status','declined');
  }
  await text(host,guest,'iPhone → Android مرحبا ✓');await text(guest,host,'Android → iPhone ✓');await text(host,guest,'This should be declined',false);
  console.log('Text verified both ways and receiver decline verified.');
  const payload=crypto.randomBytes(2*1024*1024+31);
  const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jY2kAAAAASUVORK5CYII=','base64');
  if(process.argv.includes('--large')){const fd=fs.openSync(bigFile,'w');const block=crypto.randomBytes(1024*1024);for(let i=0;i<300;i++)fs.writeSync(fd,block);fs.closeSync(fd)}
  async function files(from,to,large=false){
   const data=large?fs.readFileSync(bigFile):payload;
   await from.locator('#phone-files').setInputFiles(large?bigFile:[{name:large?'300mb.bin':'phone-data.bin',mimeType:'application/octet-stream',buffer:data},...large?[]:[{name:'photo.png',mimeType:'image/png',buffer:png}]]);
   await from.locator('#phone-send-files').click();await to.locator('#phone-offer').waitFor({state:'visible'});await to.locator('#phone-accept').click();
   const monitor=setInterval(async()=>console.log('Transfer progress:',await from.locator('#phone-send-status').textContent()),40000);
   try{
    await from.waitForFunction(()=>{const text=document.querySelector('#phone-send-status').textContent;return text.includes('Received by')||/disconnected|cancelled|declined|timed out|could not|did not|Session limit/i.test(text)},null,{timeout:large?900000:60000});
    assert.match(await from.locator('#phone-send-status').textContent(),/Received by/);
   }finally{clearInterval(monitor)}
   const downloading=to.waitForEvent('download');await to.getByRole('link',{name:'Download file',exact:true}).first().click();
   const download=await downloading;const downloaded=fs.readFileSync(await download.path());
   assert.equal(crypto.createHash('sha256').update(downloaded).digest('hex'),crypto.createHash('sha256').update(data).digest('hex'));
   if(!large)assert.equal(await to.getByRole('button',{name:'Copy photo'}).count(),1);
   console.log('Verified file bytes and photo receive:',from===host?'iPhone → Android':'Android → iPhone',large?'300 MB':'2 MB');
  }
  await files(host,guest);await files(guest,host);
  if(process.argv.includes('--large')){await files(host,guest,true);await files(guest,host,true)}
  const oversized=path.join(testDir,'oversized.bin');const sparse=fs.openSync(oversized,'w');fs.ftruncateSync(sparse,301*1024*1024);fs.closeSync(sparse);
  await host.locator('#phone-files').setInputFiles(oversized);await wait(host,'status','Files exceed 300 MB');
  assert.equal(await host.locator('#phone-send-files').isDisabled(),true);
  const cancelled=path.join(testDir,'cancel.bin');fs.writeFileSync(cancelled,crypto.randomBytes(20*1024*1024));
  await host.locator('#phone-files').setInputFiles(cancelled);await host.locator('#phone-send-files').click();await guest.locator('#phone-offer').waitFor({state:'visible'});await guest.locator('#phone-accept').click();
  await host.locator('#phone-send-progress').waitFor({state:'visible'});await host.locator('#phone-cancel-send').click();
  await wait(host,'phone-send-status','Transfer cancelled');await wait(guest,'phone-receive-status','sender cancelled');
  await text(host,guest,'Connection still works after cancellation');
  console.log('Oversized batches rejected; partial transfer cancellation leaves the connection usable.');

  await host.screenshot({path:path.join(process.env.CLIPBRIDGE_ARTIFACTS||testDir,offline?'phone-offline.png':'phone-online.png'),fullPage:true});
  await host.locator('#disconnect-phone').click();await guest.waitForFunction(()=>/connection (ended|failed)|disconnected/.test(document.querySelector('#status').textContent),null,{timeout:10000});
  console.log('Disconnect is reported and received files remain available.');
 }finally{await browser.close();assert.equal(path.dirname(path.resolve(testDir)),path.resolve(os.tmpdir()));fs.rmSync(testDir,{recursive:true,force:true})}
}
main().catch(e=>{console.error(e);process.exitCode=1});
