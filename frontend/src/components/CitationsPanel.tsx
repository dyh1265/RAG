import type { Citation } from "../types";

interface CitationsPanelProps {
  citations: Citation[];
  onPageSelect?: (page: number) => void;
}

export function CitationsPanel({ citations, onPageSelect }: CitationsPanelProps) {
  return (
    <details className="citations">
      <summary>Citations ({citations.length})</summary>
      <ol>
        {citations.map((cite, idx) => (
          <li key={cite.chunk_id}>
            <strong>[{idx + 1}]</strong>
            {cite.page_number != null && (
              <>
                {" "}
                {onPageSelect ? (
                  <button
                    type="button"
                    className="citation-page-link"
                    onClick={() => onPageSelect(cite.page_number!)}
                  >
                    page {cite.page_number}
                  </button>
                ) : (
                  <>page {cite.page_number}</>
                )}
                {" —"}
              </>
            )}
            {" "}
            {cite.excerpt.slice(0, 200)}
            {cite.excerpt.length > 200 ? "…" : ""}
          </li>
        ))}
      </ol>
    </details>
  );
}
