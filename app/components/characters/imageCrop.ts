export type CropImage = { url: string; width: number; height: number };

// Read dimensions before decoding so a tiny compressed file cannot allocate an
// arbitrarily large bitmap. Only the three explicitly supported formats pass.
export async function inspectUpload(file: File): Promise<void> {
  if (file.size > 2 * 1024 * 1024) throw new Error("Choose an image smaller than 2 MB.");
  const data = new Uint8Array(await file.arrayBuffer());
  const view = new DataView(data.buffer);
  const ascii = (offset: number, length: number) => String.fromCharCode(...data.slice(offset, offset + length));
  let width = 0;
  let height = 0;
  if (data.length >= 24 && ascii(1, 3) === "PNG" && data[0] === 137 && ascii(12, 4) === "IHDR") {
    width = view.getUint32(16); height = view.getUint32(20);
  } else if (data.length >= 4 && data[0] === 255 && data[1] === 216) {
    let offset = 2;
    while (offset + 4 <= data.length) {
      if (data[offset++] !== 255) break;
      while (data[offset] === 255) offset++;
      const marker = data[offset++];
      if (marker === 217 || marker === 218) break;
      if (marker === 1 || (marker >= 208 && marker <= 215)) continue;
      if (offset + 2 > data.length) break;
      const size = view.getUint16(offset);
      if (size < 2 || offset + size > data.length) break;
      if ([192, 193, 194, 195, 197, 198, 199, 201, 202, 203, 205, 206, 207].includes(marker) && size >= 7) {
        height = view.getUint16(offset + 3); width = view.getUint16(offset + 5); break;
      }
      offset += size;
    }
  } else if (data.length >= 30 && ascii(0, 4) === "RIFF" && ascii(8, 4) === "WEBP") {
    const kind = ascii(12, 4);
    if (kind === "VP8X") {
      if (data[20] & 2) throw new Error("Choose a still image instead of an animation.");
      width = 1 + data[24] + (data[25] << 8) + (data[26] << 16);
      height = 1 + data[27] + (data[28] << 8) + (data[29] << 16);
    } else if (kind === "VP8 " && data[23] === 157 && data[24] === 1 && data[25] === 42) {
      width = view.getUint16(26, true) & 16383; height = view.getUint16(28, true) & 16383;
    } else if (kind === "VP8L" && data[20] === 47) {
      const bits = view.getUint32(21, true);
      width = (bits & 16383) + 1; height = ((bits >>> 14) & 16383) + 1;
    }
  }
  if (!width || !height) throw new Error("Choose a valid JPG, PNG, or WebP image.");
  if (width > 8192 || height > 8192 || width * height > 24_000_000) throw new Error("That image is too large. Resize it to under 24 megapixels and 8,192 pixels per side.");
  if (Math.min(width, height) < 64) throw new Error("Choose an image at least 64 pixels wide and tall.");
}

export function cropGeometry(image: CropImage, zoom: number, x: number, y: number, size: number) {
  const scale = Math.max(size / image.width, size / image.height) * zoom;
  const width = image.width * scale;
  const height = image.height * scale;
  return { width, height, left: (size - width) * x / 100, top: (size - height) * y / 100 };
}

export async function exportCrop(image: CropImage, zoom: number, x: number, y: number): Promise<string> {
  const element = new Image();
  element.src = image.url;
  await element.decode();
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = 512;
  const context = canvas.getContext("2d");
  if (!context) throw new Error("Your browser could not prepare this image. Please try again.");
  const bounds = cropGeometry(image, zoom, x, y, 512);
  context.drawImage(element, bounds.left, bounds.top, bounds.width, bounds.height);
  return canvas.toDataURL("image/png");
}
