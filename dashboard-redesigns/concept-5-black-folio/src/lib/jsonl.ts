export type JsonlOptions = {
  maxBytes?: number;
  timeoutMs?: number;
  label?: string;
};

export async function parseJsonlStream<T = unknown>(
  url: string,
  onProgress?: (count: number) => void,
  opts: JsonlOptions = {},
): Promise<T[]> {
  const {
    maxBytes = 50 * 1024 * 1024,
    timeoutMs = 15_000,
    label = "jsonl",
  } = opts;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  const res = await fetch(url, { signal: controller.signal }).finally(() =>
    clearTimeout(timer),
  );
  if (!res.ok || !res.body) {
    throw new Error(`Failed to fetch JSONL: ${res.status || "unknown"}`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let bytes = 0;
  const items: T[] = [];
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    bytes += value?.byteLength || 0;
    if (bytes > maxBytes) {
      throw new Error(`${label}_too_large`);
    }
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n");
    buffer = parts.pop() ?? "";
    for (const line of parts) {
      if (!line.trim()) continue;
      try {
        items.push(JSON.parse(line) as T);
      } catch {
        const parseError = new Error(`${label}_parse_error`);
        (parseError as { line?: string }).line = line.slice(0, 256);
        throw parseError;
      }
      if (onProgress) onProgress(items.length);
    }
  }
  if (buffer.trim()) {
    try {
      items.push(JSON.parse(buffer));
    } catch {
      const parseError = new Error(`${label}_parse_error`);
      (parseError as { line?: string }).line = buffer.slice(0, 256);
      throw parseError;
    }
    if (onProgress) onProgress(items.length);
  }
  return items;
}
