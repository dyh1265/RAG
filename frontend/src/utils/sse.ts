/** Minimal SSE reader for POST responses (EventSource only supports GET). */

export type SseHandler = (event: string, data: string) => void;

function dispatchSseBlock(block: string, onEvent: SseHandler): void {
  if (!block.trim()) return;
  let event = "message";
  const dataLines: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) {
      event = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trimStart());
    }
  }
  if (dataLines.length) {
    onEvent(event, dataLines.join("\n"));
  }
}

function drainSseBuffer(buffer: string, onEvent: SseHandler): string {
  const blocks = buffer.split("\n\n");
  const remainder = blocks.pop() ?? "";
  for (const block of blocks) {
    dispatchSseBlock(block, onEvent);
  }
  return remainder;
}

export async function readSseStream(
  response: Response,
  onEvent: SseHandler,
  signal?: AbortSignal,
): Promise<void> {
  if (!response.body) {
    throw new Error("Response has no body");
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      if (signal?.aborted) {
        throw new DOMException("Aborted", "AbortError");
      }
      const { done, value } = await reader.read();
      if (value) {
        buffer += decoder.decode(value, { stream: true });
        buffer = drainSseBuffer(buffer, onEvent);
      }
      if (done) {
        buffer += decoder.decode();
        drainSseBuffer(buffer, onEvent);
        if (buffer.trim()) {
          dispatchSseBlock(buffer, onEvent);
        }
        break;
      }
    }
  } finally {
    reader.releaseLock();
  }
}
