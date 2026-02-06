const ID_RE = /^[a-z0-9._\/-]+$/i;

export class ValidationError extends Error {
  status: number;
  detail?: string;
  constructor(message: string, status = 400, detail?: string) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

export function readEnv(name: string, fallback?: string): string {
  const value = process.env[name] ?? fallback;
  if (value == null || value === "") {
    throw new Error(`Missing required env var ${name}`);
  }
  return value;
}

export function readEnvNumber(
  name: string,
  fallback: number,
  opts: { min?: number; max?: number } = {},
): number {
  const raw = process.env[name];
  const parsed = raw == null || raw === "" ? fallback : Number(raw);
  if (!Number.isFinite(parsed)) return fallback;
  if (typeof opts.min === "number" && parsed < opts.min) return opts.min;
  if (typeof opts.max === "number" && parsed > opts.max) return opts.max;
  return parsed;
}

export function fetchWithTimeout(
  url: string,
  init: RequestInit = {},
  timeoutMs = 10_000,
  label = "fetch",
) {
  const controller = new AbortController();
  const timersignal = setTimeout(() => controller.abort(), timeoutMs);
  const signal = controller.signal;
  if (init.signal) {
    const outer = init.signal;
    outer.addEventListener("abort", () => controller.abort(), { once: true });
  }

  return fetch(url, { ...init, signal })
    .finally(() => clearTimeout(timersignal))
    .catch((err) => {
      if (err?.name === "AbortError") {
        throw new Error(`${label}_timeout`);
      }
      throw err;
    });
}

export function sanitizeIds(raw: string[], max = 50): string[] {
  const ids = Array.from(new Set(raw.map((s) => s.trim()).filter(Boolean)));
  if (ids.length > max) {
    throw new ValidationError("too_many_ids", 400);
  }
  for (const id of ids) {
    if (!ID_RE.test(id)) {
      throw new ValidationError("invalid_id", 400, id);
    }
  }
  return ids;
}

export function pickOrFallback<T extends string>(
  value: unknown,
  allowed: readonly T[],
  fallback: T,
): T {
  return typeof value === "string" &&
    (allowed as readonly string[]).includes(value)
    ? (value as T)
    : fallback;
}
