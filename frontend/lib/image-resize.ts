// Downscale a photo before it goes to the vision model.
//
// Anthropic stops gaining accuracy past roughly 1568px on the long edge, so
// anything larger is paid for in tokens and latency for nothing. Re-encoding
// as JPEG keeps a phone photo in the low hundreds of KB.

const MAX_LONG_EDGE = 1568;
const JPEG_QUALITY = 0.85;

/**
 * Decode to a bitmap, reaching for the HEIC decoder only if the browser can't
 * do it natively.
 *
 * iPhones shoot HEIC and no browser decodes it, but the decoder is a ~3MB wasm
 * bundle -- far too much to load for the jpeg/png/webp that everything else
 * produces. Native decode failing is the precise signal that it's worth
 * fetching, so the import stays dynamic and the common path never pays.
 */
async function decode(file: File): Promise<ImageBitmap | null> {
  try {
    // from-image honours the EXIF rotation phones record instead of baking in;
    // without it a portrait shot reaches the model on its side.
    return await createImageBitmap(file, { imageOrientation: "from-image" });
  } catch {
    // Not a format this browser reads — try HEIC below.
  }

  try {
    const { isHeic, heicTo } = await import("heic-to");
    if (!(await isHeic(file))) return null;
    return await heicTo({
      blob: file,
      type: "bitmap",
      options: { imageOrientation: "from-image" },
    });
  } catch {
    return null;
  }
}

/**
 * Returns a resized JPEG, or null if the image can't be read at all. Callers
 * surface that as "unsupported" rather than uploading bytes the API will reject.
 */
export async function compressImage(file: File): Promise<File | null> {
  const bitmap = await decode(file);
  if (!bitmap) return null;

  try {
    const scale = Math.min(1, MAX_LONG_EDGE / Math.max(bitmap.width, bitmap.height));
    const width = Math.round(bitmap.width * scale);
    const height = Math.round(bitmap.height * scale);

    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    ctx.drawImage(bitmap, 0, 0, width, height);

    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, "image/jpeg", JPEG_QUALITY),
    );
    if (!blob) return null;
    return new File([blob], file.name.replace(/\.\w+$/, "") + ".jpg", {
      type: "image/jpeg",
    });
  } finally {
    bitmap.close();
  }
}
