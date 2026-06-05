import type { Citation } from "../types";

export function formatTimestamp(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const mm = m.toString().padStart(2, "0");
  const ss = s.toString().padStart(2, "0");
  if (h > 0) {
    return `${h}:${mm}:${ss}`;
  }
  return `${m}:${ss}`;
}

export interface CitationSourceInfo {
  label: string;
  href?: string;
}

export function youtubeCitationSource(cite: Citation): CitationSourceInfo | null {
  const meta = cite.metadata;
  if (!meta || meta.source_kind !== "youtube") {
    return null;
  }

  const youtubeUrl =
    typeof meta.youtube_url === "string" && meta.youtube_url ? meta.youtube_url : undefined;

  if (meta.modality === "transcript" && typeof meta.start_time === "number") {
    const start = formatTimestamp(meta.start_time);
    const end =
      typeof meta.end_time === "number" ? formatTimestamp(meta.end_time) : undefined;
    return {
      label: end ? `Transcript ${start}–${end}` : `Transcript ${start}`,
      href: youtubeUrl,
    };
  }

  if (meta.modality === "slide") {
    const slideNumber = meta.slide_number ?? cite.page_number;
    const timestamp =
      typeof meta.timestamp === "number" ? formatTimestamp(meta.timestamp) : undefined;
    if (slideNumber != null && timestamp) {
      return {
        label: `Slide ${slideNumber}, extracted around ${timestamp}`,
        href: youtubeUrl,
      };
    }
    if (slideNumber != null) {
      return { label: `Slide ${slideNumber}`, href: youtubeUrl };
    }
    return { label: "Slide", href: youtubeUrl };
  }

  return null;
}
