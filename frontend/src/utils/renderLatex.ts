import katex from "katex";

export type MessageSegment =
  | { kind: "text"; value: string }
  | { kind: "math"; value: string; display: boolean };

const DIGIT = /[0-9]/;

/**
 * Pandoc-style inline-math rules, tightened for chat LLM output.
 *
 * A "$" opens inline math only when:
 *   - the next character exists and is not whitespace, AND
 *   - the next character is not a digit (rules out currency: `$100`)
 *
 * The matching "$" closes inline math only when:
 *   - the previous character is not whitespace, AND
 *   - the next character (if any) is not a digit
 *
 * The math span must not contain a newline.
 *
 * These rules let real LaTeX like `$E = mc^2$` or `$\sum_{i=1}^n i$` through
 * while leaving currency strings like `between $100 billion and $500 billion`
 * as plain text. They also reject false-positive pairs created by mixing
 * currency and prose in the same line.
 */
function tryParseInlineMath(
  input: string,
  start: number,
): { content: string; nextIndex: number } | null {
  if (input[start] !== "$") return null;
  const opener = start + 1;
  const after = input[opener];
  if (after === undefined || after === "$") return null;
  if (after === " " || after === "\t" || after === "\n") return null;
  if (DIGIT.test(after)) return null;

  for (let j = opener; j < input.length; j += 1) {
    const c = input[j];
    if (c === "\n") return null;
    if (c !== "$") continue;
    const prev = input[j - 1];
    if (prev === " " || prev === "\t") continue;
    const next = input[j + 1];
    if (next !== undefined && DIGIT.test(next)) continue;
    return { content: input.slice(opener, j).trim(), nextIndex: j + 1 };
  }
  return null;
}

/** Display math `$$...$$` — looser than inline because `$$` in prose is rare. */
function tryParseDisplayDollar(
  input: string,
  start: number,
): { content: string; nextIndex: number } | null {
  if (input[start] !== "$" || input[start + 1] !== "$") return null;
  const end = input.indexOf("$$", start + 2);
  if (end === -1) return null;
  return { content: input.slice(start + 2, end).trim(), nextIndex: end + 2 };
}

function tryParseDelimitedMath(
  input: string,
  start: number,
  open: string,
  close: string,
): { content: string; nextIndex: number } | null {
  if (!input.startsWith(open, start)) return null;
  const end = input.indexOf(close, start + open.length);
  if (end === -1) return null;
  return {
    content: input.slice(start + open.length, end).trim(),
    nextIndex: end + close.length,
  };
}

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
    if (input[i] === "\\" && input[i + 1] === "$") {
      textBuf += "$";
      i += 2;
      continue;
    }

    const dd = tryParseDisplayDollar(input, i);
    if (dd) {
      flushText();
      out.push({ kind: "math", value: dd.content, display: true });
      i = dd.nextIndex;
      continue;
    }

    const bracket = tryParseDelimitedMath(input, i, "\\[", "\\]");
    if (bracket) {
      flushText();
      out.push({ kind: "math", value: bracket.content, display: true });
      i = bracket.nextIndex;
      continue;
    }

    const paren = tryParseDelimitedMath(input, i, "\\(", "\\)");
    if (paren) {
      flushText();
      out.push({ kind: "math", value: paren.content, display: false });
      i = paren.nextIndex;
      continue;
    }

    const inline = tryParseInlineMath(input, i);
    if (inline) {
      flushText();
      out.push({ kind: "math", value: inline.content, display: false });
      i = inline.nextIndex;
      continue;
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
