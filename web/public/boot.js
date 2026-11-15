(() => {
  const script = document.currentScript;
  const controls = document.getElementById('app-controls');
  const notice = document.getElementById('app-loading');
  const message = document.getElementById('app-loading-message');
  const retry = document.getElementById('app-retry');
  retry.addEventListener('click', () => location.reload());
  const timer = setTimeout(() => {
    message.textContent = 'Still loading. Check your connection or retry.';
    retry.hidden = false;
  }, 12000);
  const entry = script.dataset.entry;
  if (!['app.mjs', 'phone-app.mjs'].includes(entry)) return;
  const url = new URL(entry, script.src);
  url.search = 'build=0.7.0.1';
  import(url.href).then(() => {
    clearTimeout(timer);
    controls.disabled = false;
    controls.removeAttribute('aria-busy');
    notice.hidden = true;
    document.documentElement.dataset.appReady = 'true';
  }).catch(error => {
    clearTimeout(timer);
    message.textContent = 'ClipBridge could not start. Reload the app. If it persists, update your browser.';
    retry.hidden = false;
    console.error('ClipBridge startup failed:', error);
  });
})();
