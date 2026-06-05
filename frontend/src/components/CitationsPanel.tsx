import type { Citation } from "../types";
import { youtubeCitationSource } from "../utils/citationFormat";

interface CitationsPanelProps {
  citations: Citation[];
  onPageSelect?: (page: number) => void;
}

export function CitationsPanel({ citations, onPageSelect }: CitationsPanelProps) {
  return (
    <details className="citations">
      <summary>Citations ({citations.length})</summary>
      <ol>
        {citations.map((cite, idx) => {
          const youtube = youtubeCitationSource(cite);

          return (
            <li key={cite.chunk_id}>
              <strong>[{idx + 1}]</strong>
              {youtube ? (
                <>
                  {" "}
                  {youtube.href ? (
                    <a
                      href={youtube.href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="citation-youtube-link"
                    >
                      {youtube.label}
                    </a>
                  ) : (
                    <span className="citation-youtube-label">{youtube.label}</span>
                  )}
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
                    </>
                  )}
                  {" —"}
                </>
              ) : (
                cite.page_number != null && (
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
                )
              )}
              {" "}
              {cite.excerpt.slice(0, 200)}
              {cite.excerpt.length > 200 ? "…" : ""}
            </li>
          );
        })}
      </ol>
    </details>
  );
}
