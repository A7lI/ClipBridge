import { qrcode } from './vendor/qrcode.mjs';

export function drawQR(canvas, value) {
  try {
    const code = qrcode(0, 'L'); code.addData(value); code.make();
    const count = code.getModuleCount(), scale = Math.max(3, Math.floor(800 / (count + 8)));
    canvas.width = canvas.height = (count + 8) * scale;
    const context = canvas.getContext('2d');
    context.fillStyle = '#fff'; context.fillRect(0, 0, canvas.width, canvas.height);
    context.fillStyle = '#000';
    for (let y = 0; y < count; y++) for (let x = 0; x < count; x++) if (code.isDark(y, x)) context.fillRect((x + 4) * scale, (y + 4) * scale, scale, scale);
    canvas.hidden = false;
  } catch { canvas.hidden = true; }
}

export function readQR(image, width, height) {
  const canvas = document.createElement('canvas');
  const scale = Math.min(1, 1600 / Math.max(width, height));
  canvas.width = Math.round(width * scale); canvas.height = Math.round(height * scale);
  const context = canvas.getContext('2d', { willReadFrequently: true });
  context.drawImage(image, 0, 0, canvas.width, canvas.height);
  const pixels = context.getImageData(0, 0, canvas.width, canvas.height);
  return window.jsQR(pixels.data, pixels.width, pixels.height)?.data;
}

export async function readQRPhoto(file) {
  const image = new Image(), url = URL.createObjectURL(file);
  try { image.src = url; await image.decode(); return readQR(image, image.naturalWidth, image.naturalHeight); }
  finally { URL.revokeObjectURL(url); }
}
