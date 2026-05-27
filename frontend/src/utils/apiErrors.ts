/** Turn API / proxy error bodies into short user-facing messages (never raw HTML). */

const HTML_PREFIX = /^\s*</;

export function isHtmlErrorBody(body: string): boolean {
  return HTML_PREFIX.test(body);
}

export function isCloudflareTunnelHost(hostname = window.location.hostname): boolean {
  const h = hostname.toLowerCase();
  return h.endsWith(".trycloudflare.com") || h.includes("cloudflare");
}

export function parseApiErrorBody(body: string, status?: number): string {
  const trimmed = body.trim();
  if (!trimmed) {
    return status ? `Request failed (${status})` : "Request failed";
  }

  if (isHtmlErrorBody(trimmed)) {
    const code =
      trimmed.match(/Error code (\d{3})/i)?.[1] ??
      trimmed.match(/\|\s*(\d{3}):/i)?.[1] ??
      (status ? String(status) : "");
    const title = trimmed.match(/<title[^>]*>([^<]+)<\/title>/i)?.[1]?.trim();

    if (code === "524" || /timeout occurred/i.test(trimmed)) {
      const tunnel = isCloudflareTunnelHost();
      return tunnel
        ? "Connection timed out (Cloudflare 524). The tunnel allows ~100s per request — large PDFs or big folder uploads often hit this. Use localhost, a VM with a public IP, or upload in smaller batches."
        : "The server took too long to respond (timeout). Try again with fewer or smaller PDFs.";
    }
    if (code === "504") {
      return (
        "The server took too long to respond (504). " +
        "For very long PDFs on CPU, single-file upload may exceed the request timeout — " +
        "use the bulk-upload panel (async worker), or rebuild on GPU."
      );
    }
    if (code === "502" || code === "503") {
      return `The API is temporarily unavailable (${code}). Check that Docker / rag-api is running.`;
    }
    if (title) {
      return title.replace(/\s*\|\s*[^|]+$/i, "").trim();
    }
    return code ? `Server error (${code})` : "Server returned an HTML error page";
  }

  try {
    const parsed = JSON.parse(trimmed) as {
      error?: string;
      detail?: string | Array<{ msg?: string; loc?: unknown[] }>;
    };
    if (typeof parsed.error === "string") return parsed.error;
    if (typeof parsed.detail === "string") return parsed.detail;
    if (Array.isArray(parsed.detail)) {
      return parsed.detail
        .map((d) => (typeof d === "object" && d && "msg" in d ? String(d.msg) : String(d)))
        .join("; ");
    }
  } catch {
    /* plain text */
  }

  if (trimmed.length > 280) {
    return `${trimmed.slice(0, 277)}…`;
  }
  return trimmed;
}

export function isRetryableHttpStatus(status: number): boolean {
  return status === 429 || status === 502 || status === 503 || status === 504 || status === 524;
}
