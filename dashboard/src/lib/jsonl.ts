export async function parseJsonlStream<T = unknown>(
  url: string,
  onProgress?: (count: number) => void
): Promise<T[]> {
  const res = await fetch(url);
  if (!res.ok || !res.body) {
    throw new Error(`Failed to fetch JSONL: ${res.status}`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  const items: T[] = [];
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n");
    buffer = parts.pop() ?? "";
    for (const line of parts) {
      if (!line.trim()) continue;
      items.push(JSON.parse(line) as T);
      if (onProgress) onProgress(items.length);
    }
  }
  if (buffer.trim()) {
    items.push(JSON.parse(buffer));
    if (onProgress) onProgress(items.length);
  }
  return items;
}
