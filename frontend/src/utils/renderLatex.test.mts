/**
 * Standalone parser smoke test. Run with:
 *
 *   node --import tsx frontend/src/utils/renderLatex.test.mts
 *
 * No test framework needed — exits non-zero on first mismatch. Intended for
 * manual regression checks against the LaTeX-vs-currency parser. The frontend
 * has no JS test runner today (see frontend/package.json), so this lives
 * alongside the implementation and is invoked ad hoc.
 */
import { parseLatexSegments } from "./renderLatex";

type Case = { name: string; input: string; expect: ReturnType<typeof parseLatexSegments> };

const cases: Case[] = [
  {
    name: "currency stays text",
    input: "losses were between $100 billion and $500 billion",
    expect: [{ kind: "text", value: "losses were between $100 billion and $500 billion" }],
  },
  {
    name: "single price stays text",
    input: "the cost was $100",
    expect: [{ kind: "text", value: "the cost was $100" }],
  },
  {
    name: "real inline math renders",
    input: "Einstein's $E = mc^2$ paradox",
    expect: [
      { kind: "text", value: "Einstein's " },
      { kind: "math", value: "E = mc^2", display: false },
      { kind: "text", value: " paradox" },
    ],
  },
  {
    name: "backslash math",
    input: "the sum $\\sum_{i=1}^n i$ converges",
    expect: [
      { kind: "text", value: "the sum " },
      { kind: "math", value: "\\sum_{i=1}^n i", display: false },
      { kind: "text", value: " converges" },
    ],
  },
  {
    name: "mixed currency + math",
    input: "spent $5 then computed $E = mc^2$ later",
    expect: [
      { kind: "text", value: "spent $5 then computed " },
      { kind: "math", value: "E = mc^2", display: false },
      { kind: "text", value: " later" },
    ],
  },
  {
    name: "display math \\[ \\]",
    input: "block: \\[a + b = c\\] done",
    expect: [
      { kind: "text", value: "block: " },
      { kind: "math", value: "a + b = c", display: true },
      { kind: "text", value: " done" },
    ],
  },
  {
    name: "display math $$ $$",
    input: "block: $$x^2 + y^2 = z^2$$ done",
    expect: [
      { kind: "text", value: "block: " },
      { kind: "math", value: "x^2 + y^2 = z^2", display: true },
      { kind: "text", value: " done" },
    ],
  },
  {
    name: "escaped dollar renders literal",
    input: "use \\$50 verbatim",
    expect: [{ kind: "text", value: "use $50 verbatim" }],
  },
  {
    name: "lonely dollar in prose stays text",
    input: "the symbol $ is currency",
    expect: [{ kind: "text", value: "the symbol $ is currency" }],
  },
  {
    name: "no false-positive across newlines",
    input: "first $foo\nsecond bar$ baz",
    expect: [{ kind: "text", value: "first $foo\nsecond bar$ baz" }],
  },
];

let failures = 0;
for (const c of cases) {
  const got = parseLatexSegments(c.input);
  const ok = JSON.stringify(got) === JSON.stringify(c.expect);
  if (!ok) {
    failures += 1;
    console.error(`FAIL  ${c.name}`);
    console.error("  input:    ", JSON.stringify(c.input));
    console.error("  expected: ", JSON.stringify(c.expect));
    console.error("  actual:   ", JSON.stringify(got));
  } else {
    console.log(`PASS  ${c.name}`);
  }
}

if (failures > 0) {
  console.error(`\n${failures} of ${cases.length} cases failed.`);
  process.exit(1);
}
console.log(`\n${cases.length} cases passed.`);
