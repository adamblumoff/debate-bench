import { createHash } from "crypto";

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

function shouldTrustProxyHeaders(): boolean {
  const raw = process.env.TRUST_PROXY ?? process.env.RL_TRUST_PROXY;
  if (raw == null || raw === "") return true;
  return ["1", "true", "yes", "on"].includes(raw.trim().toLowerCase());
}

function parseIP(req: Request): string {
  const anyReq = req as { ip?: string | null };
  if (anyReq && typeof anyReq.ip === "string" && anyReq.ip) return anyReq.ip;
  if (!shouldTrustProxyHeaders()) return "unknown";
  const header =
    req.headers.get("x-forwarded-for") || req.headers.get("x-real-ip") || "";
  const ip = header
    .split(",")
    .map((s) => s.trim())
    .find(Boolean);
  return ip || "unknown";
}

function hashIp(ip: string): string {
  try {
    return createHash("sha256").update(ip).digest("hex").slice(0, 12);
  } catch {
    return "unknown";
  }
}

export type RateLimitResult = {
  ok: boolean;
  remaining: number;
  reset: number;
  ip: string;
  ipHash: string;
};

export type RateLimitLogger = (
  info: RateLimitResult & { name: string },
) => void;

export function rateLimit(
  req: Request,
  name: string,
  cfg?: Partial<LimitConfig>,
  logger?: RateLimitLogger,
): RateLimitResult {
  const config: LimitConfig = {
    capacity: cfg?.capacity ?? DEFAULTS.capacity,
    refillMs: cfg?.refillMs ?? DEFAULTS.refillMs,
  };

  const ip = parseIP(req);
  const key = getKey(ip, name);
  const ts = now();

  const existing = buckets.get(key);
  if (existing && ts > existing.reset) {
    buckets.delete(key);
  }
  if (!existing || ts > existing.reset) {
    const result: RateLimitResult = {
      ok: true,
      remaining: config.capacity - 1,
      reset: ts + config.refillMs,
      ip,
      ipHash: hashIp(ip),
    };
    buckets.set(key, { tokens: result.remaining, reset: result.reset });
    if (logger) logger({ name, ...result });
    return result;
  }

  if (existing.tokens <= 0) {
    const result: RateLimitResult = {
      ok: false,
      remaining: 0,
      reset: existing.reset,
      ip,
      ipHash: hashIp(ip),
    };
    if (logger) logger({ name, ...result });
    return result;
  }

  existing.tokens -= 1;
  const result: RateLimitResult = {
    ok: true,
    remaining: existing.tokens,
    reset: existing.reset,
    ip,
    ipHash: hashIp(ip),
  };
  if (logger) logger({ name, ...result });
  return result;
}
