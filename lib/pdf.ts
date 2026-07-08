import { extractText, getDocumentProxy } from "unpdf";

export interface PdfResult {
  text: string;
  pageCount: number;
  sourceType: "pdf" | "image";
}

const MAX_FILE_BYTES = 5 * 1024 * 1024;
const MAX_CHARS = 12_000;
const IMAGE_EXTENSIONS = new Set([".png", ".jpg", ".jpeg", ".bmp"]);

export class PdfError extends Error {
  constructor(message: string, public code: string) {
    super(message);
  }
}

function getExtension(filename: string) {
  const normalized = filename.toLowerCase();
  const dotIndex = normalized.lastIndexOf(".");
  return dotIndex >= 0 ? normalized.slice(dotIndex) : "";
}

function truncateText(text: string) {
  return text.length > MAX_CHARS ? `${text.slice(0, MAX_CHARS)}\n[...truncated]` : text;
}

export async function extractPdfText(
  buffer: ArrayBuffer,
  filename: string,
): Promise<PdfResult> {
  if (buffer.byteLength > MAX_FILE_BYTES) {
    throw new PdfError("File exceeds 5MB limit", "FILE_TOO_LARGE");
  }

  if (!filename.toLowerCase().endsWith(".pdf")) {
    throw new PdfError("Only .pdf files are supported", "INVALID_TYPE");
  }

  try {
    // unpdf 1.x ships a serverless PDF.js build with the worker inlined —
    // required on Vercel (no separate pdf.worker.js on the filesystem).
    const pdf = await getDocumentProxy(new Uint8Array(buffer));
    const { text, totalPages } = await extractText(pdf, { mergePages: true });
    const textStr = text.trim();

    if (!textStr) {
      throw new PdfError(
        "No extractable text found. If this is a scanned resume, upload a PNG/JPG image or paste the text.",
        "EMPTY_TEXT",
      );
    }

    return { text: truncateText(textStr), pageCount: totalPages, sourceType: "pdf" };
  } catch (err) {
    if (err instanceof PdfError) throw err;
    throw new PdfError(
      `Failed to parse PDF: ${err instanceof Error ? err.message : "unknown error"}`,
      "PARSE_ERROR",
    );
  }
}

async function extractImageText(buffer: ArrayBuffer, filename: string): Promise<PdfResult> {
  const { default: Tesseract } = await import("tesseract.js");
  const worker = await Tesseract.createWorker("eng");

  try {
    const result = await worker.recognize(Buffer.from(buffer));
    const text = result.data.text.trim();

    if (!text) {
      throw new PdfError("OCR could not find readable text. Try a sharper image or paste the resume text.", "EMPTY_TEXT");
    }

    return { text: truncateText(text), pageCount: 1, sourceType: "image" };
  } catch (err) {
    if (err instanceof PdfError) throw err;
    throw new PdfError(
      `Failed to OCR ${filename}: ${err instanceof Error ? err.message : "unknown error"}`,
      "OCR_ERROR",
    );
  } finally {
    await worker.terminate().catch(() => undefined);
  }
}

export async function extractResumeText(buffer: ArrayBuffer, filename: string): Promise<PdfResult> {
  const extension = getExtension(filename);

  if (extension === ".pdf") {
    return extractPdfText(buffer, filename);
  }

  if (IMAGE_EXTENSIONS.has(extension)) {
    if (buffer.byteLength > MAX_FILE_BYTES) {
      throw new PdfError("File exceeds 5MB limit", "FILE_TOO_LARGE");
    }
    return extractImageText(buffer, filename);
  }

  throw new PdfError("Upload a PDF, PNG, JPG, JPEG, or BMP resume.", "INVALID_TYPE");
}
