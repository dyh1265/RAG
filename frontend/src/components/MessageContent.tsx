import { Fragment, useMemo } from "react";
import "katex/dist/katex.min.css";
import { parseLatexSegments, renderMathHtml } from "../utils/renderLatex";

interface MessageContentProps {
  content: string;
}

export function MessageContent({ content }: MessageContentProps) {
  const segments = useMemo(() => parseLatexSegments(content), [content]);

  return (
    <div className="message-content">
      {segments.map((segment, index) => {
        if (segment.kind === "math") {
          return (
            <span
              key={`math-${index}`}
              className={segment.display ? "math-display" : "math-inline"}
              dangerouslySetInnerHTML={{
                __html: renderMathHtml(segment.value, segment.display),
              }}
            />
          );
        }

        return (
          <Fragment key={`text-${index}`}>
            {segment.value.split("\n").map((line, lineIndex, lines) => (
              <Fragment key={lineIndex}>
                {line}
                {lineIndex < lines.length - 1 && <br />}
              </Fragment>
            ))}
          </Fragment>
        );
      })}
    </div>
  );
}
