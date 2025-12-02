// Dev-only instrumentation to prevent the Next dev overlay from choking on Sets
// when serializing server console payloads. We sanitize console.error args so
// any Set becomes a plain array before hitting the client error stream.
export async function register() {
  if (process.env.NODE_ENV !== "development") return;

  const origError = console.error;

  const sanitize = (val: unknown): unknown => {
    if (val instanceof Set) return Array.from(val);
    if (Array.isArray(val)) return val.map(sanitize);
    if (val && typeof val === "object") {
      const out: Record<string, unknown> = {};
      for (const [k, v] of Object.entries(val as Record<string, unknown>)) {
        out[k] = v instanceof Set ? Array.from(v) : v;
      }
      return out;
    }
    return val;
  };

  console.error = (...args: unknown[]) => {
    origError(...(args.map(sanitize) as []));
  };
}
