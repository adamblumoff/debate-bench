type Bucket = { tokens: number; reset: number };

const buckets = new Map<string, Bucket>();

function now() {
  return Date.now();
}

export type LimitConfig = {
  capacity: number; // max tokens
  refillMs: number; // window duration in ms
};

const DEFAULTS: LimitConfig = { capacity: 60, refillMs: 60_000 };

function getKey(ip: string, name: string) {
  return `${name}:${ip}`;
}

function parseIP(req: Request): string {
  const header = req.headers.get("x-forwarded-for") || req.headers.get("x-real-ip") || "";
  const ip = header.split(",").map((s) => s.trim()).find(Boolean);
  return ip || "unknown";
}

export function rateLimit(req: Request, name: string, cfg?: Partial<LimitConfig>) {
  const config: LimitConfig = {
    capacity: cfg?.capacity ?? DEFAULTS.capacity,
    refillMs: cfg?.refillMs ?? DEFAULTS.refillMs,
  };

  const ip = parseIP(req);
  const key = getKey(ip, name);
  const ts = now();

  const existing = buckets.get(key);
  if (!existing || ts > existing.reset) {
    buckets.set(key, { tokens: config.capacity - 1, reset: ts + config.refillMs });
    return { ok: true, remaining: config.capacity - 1, reset: ts + config.refillMs };
  }

  if (existing.tokens <= 0) {
    return { ok: false, remaining: 0, reset: existing.reset };
  }

  existing.tokens -= 1;
  return { ok: true, remaining: existing.tokens, reset: existing.reset };
}
