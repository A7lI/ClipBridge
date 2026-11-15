export async function prepareOffline(notify) {
  if (!('serviceWorker' in navigator)) { notify?.('Offline caching is unavailable in this browser.'); return; }
  try {
    const registration = await navigator.serviceWorker.register('./sw.js', { scope: './' });
    await navigator.serviceWorker.ready;
    if (!registration.active) throw new Error('Offline files are not ready yet.');
    notify?.('Ready for offline nearby sharing. Keep both phones on the same Wi-Fi or hotspot.');
  } catch { notify?.('Open this page online once to prepare offline nearby sharing. Online sharing is still available.'); }
}
