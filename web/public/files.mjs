let receivedFiles = [];
let urls = [];

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
      if (navigator.clipboard?.write && window.ClipboardItem) {
        const copy = document.createElement('button');
        copy.className = 'secondary';
        copy.textContent = 'Copy photo';
        copy.addEventListener('click', async () => {
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
