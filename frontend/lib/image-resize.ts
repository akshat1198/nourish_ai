// Downscale a photo before it goes to the vision model.
//
// Anthropic stops gaining accuracy past roughly 1568px on the long edge, so
// anything larger is paid for in tokens and latency for nothing. Re-encoding
// as JPEG keeps a phone photo in the low hundreds of KB.

const MAX_LONG_EDGE = 1568;
const JPEG_QUALITY = 0.85;

/**
 * Returns a resized JPEG, or null when the browser can't decode the file —
 * an actual .heic off an iPhone being the usual case. Callers surface that as
 * "unsupported" rather than uploading bytes the API will reject.
 */
export async function compressImage(file: File): Promise<File | null> {
  try {
    // from-image honours the EXIF rotation phones record instead of baking in;
    // without it a portrait shot reaches the model on its side.
    const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
    const scale = Math.min(1, MAX_LONG_EDGE / Math.max(bitmap.width, bitmap.height));
    const width = Math.round(bitmap.width * scale);
    const height = Math.round(bitmap.height * scale);

    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    ctx.drawImage(bitmap, 0, 0, width, height);
    bitmap.close();

    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, "image/jpeg", JPEG_QUALITY),
    );
    if (!blob) return null;
    return new File([blob], file.name.replace(/\.\w+$/, "") + ".jpg", {
      type: "image/jpeg",
    });
  } catch {
    return null;
  }
}
