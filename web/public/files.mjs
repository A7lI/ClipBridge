let receivedFiles = [];
let urls = [];
let nativeSaving = false;

async function saveAndroid(file, copy, say) {
  if (nativeSaving) { say('Wait for the current file to finish saving.'); return; }
  nativeSaving = true;
  const bridge = window.ClipBridgePhone;
  let ticket;
  try {
    ticket = bridge.beginSave(file.name, file.type, file.size, copy);
    if (!ticket) throw new Error('Could not start saving. Check free storage space.');
    for (let offset = 0; offset < file.size; offset += 16384) {
      const bytes = new Uint8Array(await file.slice(offset, offset + 16384).arrayBuffer());
      if (!bridge.appendSave(ticket, btoa(String.fromCharCode(...bytes)))) throw new Error('Could not save the complete file.');
      if (offset % (512 * 1024) === 0) { say(`Saving ${(offset / 1024 / 1024).toFixed(1)} of ${(file.size / 1024 / 1024).toFixed(1)} MB…`); await new Promise(resolve => setTimeout(resolve, 0)); }
    }
    if (!bridge.finishSave(ticket)) throw new Error('Could not finish saving the file.');
    say(copy ? 'Saved in Downloads/ClipBridge and copied for pasting.' : 'Saved in Downloads/ClipBridge.');
  } catch (error) { if (ticket) bridge.cancelSave(ticket); say(error.message, true); }
  finally { nativeSaving = false; }
}

export function clearFiles() {
  urls.forEach(url => URL.revokeObjectURL(url));
  urls = [];
  receivedFiles = [];
  document.getElementById('received-list').replaceChildren();
  document.getElementById('received-files').hidden = true;
}

async function asPNG(file) {
  if (file.type === 'image/png') return file;
  const url = URL.createObjectURL(file);
  try {
    const image = new Image();
    image.src = url;
    await image.decode();
    if (image.naturalWidth * image.naturalHeight > 24_000_000) throw new Error('Save this photo to Files or Photos to copy it.');
    const canvas = document.createElement('canvas');
    canvas.width = image.naturalWidth;
    canvas.height = image.naturalHeight;
    canvas.getContext('2d').drawImage(image, 0, 0);
    return await new Promise((resolve, reject) => canvas.toBlob(blob => blob ? resolve(blob) : reject(new Error('Save the photo to copy it.')), 'image/png'));
  } finally { URL.revokeObjectURL(url); }
}

export function showFiles(files, say) {
  clearFiles();
  receivedFiles = files;
  const list = document.getElementById('received-list');
  for (const file of files) {
    const row = document.createElement('div');
    row.className = 'received-file';
    const url = URL.createObjectURL(file);
    urls.push(url);
    const name = document.createElement('p');
    name.textContent = `${file.name} · ${(file.size / 1024 / 1024).toFixed(1)} MB`;
    row.append(name);
    const isImage = /^image\/(png|jpeg|webp|gif|avif|heic|heif)$/.test(file.type);
    if (isImage) {
      const image = document.createElement('img');
      image.src = url;
      image.alt = file.name;
      image.addEventListener('error', () => { image.hidden = true; }, { once: true });
      row.append(image);
      if (window.ClipBridgePhone || (navigator.clipboard?.write && window.ClipboardItem)) {
        const copy = document.createElement('button');
        copy.className = 'secondary';
        copy.textContent = 'Copy photo';
        copy.addEventListener('click', async () => {
          if (window.ClipBridgePhone) return saveAndroid(file, true, say);
          try {
            await navigator.clipboard.write([new ClipboardItem({ 'image/png': asPNG(file) })]);
            say('Photo copied. Paste it in an app that accepts images.');
          } catch { say('Use Save or share files to save the photo, then copy it from Photos or Files.', true); }
        });
        row.append(copy);
      }
    }
    const save = document.createElement('a');
    save.href = url;
    save.download = file.name;
    save.textContent = 'Download file';
    if (window.ClipBridgePhone) {
      save.textContent = 'Save to Downloads';
      save.addEventListener('click', event => { event.preventDefault(); saveAndroid(file, false, say); });
      if (!isImage) {
        const copy = document.createElement('button'); copy.textContent = 'Copy file'; copy.className = 'secondary';
        copy.addEventListener('click', () => saveAndroid(file, true, say)); row.append(copy);
      }
    }
    row.append(save);
    list.append(row);
  }
  const share = document.getElementById('share-files');
  share.hidden = !navigator.canShare?.({ files });
  share.onclick = async () => {
    try { await navigator.share({ files: receivedFiles }); }
    catch (error) { if (error.name !== 'AbortError') say('Use Download file to save each file.', true); }
  };
  document.getElementById('received-files').hidden = false;
}
