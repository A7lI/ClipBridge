const { chromium, webkit } = require('playwright');
const assert = require('node:assert/strict');
const base = process.env.CLIPBRIDGE_WEB_URL || 'http://127.0.0.1:8787/';

(async () => {
  for (const [name, engine, options] of [
    ['Chromium', chromium, { executablePath: process.env.CLIPBRIDGE_BROWSER || 'C:/Program Files/BraveSoftware/Brave-Browser/Application/brave.exe' }],
    ['WebKit', webkit, {}],
  ]) {
    const browser = await engine.launch({ headless: true, ...options });
    try {
      for (const [file, entry, control] of [['', 'app.mjs', '#scan'], ['phone.html', 'phone-app.mjs', '#create-phone']]) {
        const context = await browser.newContext({ serviceWorkers: 'block' });
        const page = await context.newPage();
        let release;
        const pending = new Promise(resolve => { release = resolve; });
        await page.route(url => url.pathname.endsWith('/' + entry), async route => { await pending; await route.continue(); });
        await page.goto(new URL(file, base).href, { waitUntil: 'domcontentloaded' });
        assert.equal(await page.locator(control).isDisabled(), true);
        assert.equal(await page.locator('#app-loading').isVisible(), true);
        assert.equal(await page.locator('nav.switcher a').count(), 2);
        release();
        await page.waitForSelector('html[data-app-ready="true"]');
        assert.equal(await page.locator(control).isEnabled(), true);
        assert.equal(await page.locator('#app-loading').isVisible(), false);
        assert.equal(await page.locator(file ? '#phone-send-files' : '#send-selected').isDisabled(), true);
        if (file) {
          await page.locator(control).click();
          await page.waitForFunction(() => document.getElementById('status').textContent.includes('Invitation ready'));
          await page.locator('#disconnect-phone').click();
        } else {
          await page.locator('#pairing summary').click();
          assert.equal(await page.locator('#pair-link').isVisible(), true);
          const chooser = page.waitForEvent('filechooser');
          await page.locator('#choose-photo').click();
          await chooser;
        }
        await context.close();

        const failureContext = await browser.newContext({ serviceWorkers: 'block' });
        const failure = await failureContext.newPage();
        await failure.route(url => url.pathname.endsWith('/' + entry), route => route.abort());
        await failure.goto(new URL(file, base).href);
        await failure.waitForFunction(() => document.getElementById('app-loading-message').textContent.includes('could not start'));
        assert.equal(await failure.locator('#app-retry').isEnabled(), true);
        assert.equal(await failure.locator(control).isDisabled(), true);
        await failure.unrouteAll();
        await failure.locator('#app-retry').click();
        await failure.waitForSelector('html[data-app-ready="true"]');
        assert.equal(await failure.locator(control).isEnabled(), true);
        await failureContext.close();
        console.log(name, file || 'Computer', 'delayed startup, working controls, failed-load retry passed.');
      }
    } finally { await browser.close(); }
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
