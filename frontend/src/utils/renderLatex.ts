import katex from "katex";

export type MessageSegment =
  | { kind: "text"; value: string }
  | { kind: "math"; value: string; display: boolean };

/** Split assistant/user text into plain text and LaTeX segments. */
export function parseLatexSegments(input: string): MessageSegment[] {
  const out: MessageSegment[] = [];
  let i = 0;
  let textBuf = "";

  const flushText = () => {
    if (textBuf) {
      out.push({ kind: "text", value: textBuf });
      textBuf = "";
    }
  };

  while (i < input.length) {
    if (input[i] === "$" && input[i + 1] === "$") {
      const end = input.indexOf("$$", i + 2);
      if (end !== -1) {
        flushText();
        out.push({ kind: "math", value: input.slice(i + 2, end).trim(), display: true });
        i = end + 2;
        continue;
      }
    }

    if (input.startsWith("\\[", i)) {
      const end = input.indexOf("\\]", i + 2);
      if (end !== -1) {
        flushText();
        out.push({ kind: "math", value: input.slice(i + 2, end).trim(), display: true });
        i = end + 2;
        continue;
      }
    }

    if (input.startsWith("\\(", i)) {
      const end = input.indexOf("\\)", i + 2);
      if (end !== -1) {
        flushText();
        out.push({ kind: "math", value: input.slice(i + 2, end).trim(), display: false });
        i = end + 2;
        continue;
      }
    }

    if (input[i] === "$" && input[i + 1] !== "$") {
      const end = input.indexOf("$", i + 1);
      if (end !== -1) {
        flushText();
        out.push({ kind: "math", value: input.slice(i + 1, end).trim(), display: false });
        i = end + 1;
        continue;
      }
    }

    textBuf += input[i];
    i += 1;
  }

  flushText();
  return out;
}

export function renderMathHtml(tex: string, displayMode: boolean): string {
  try {
    return katex.renderToString(tex, {
      displayMode,
      throwOnError: false,
      strict: "ignore",
      trust: false,
    });
  } catch {
    return displayMode ? `\\[${tex}\\]` : `\\(${tex}\\)`;
  }
}
