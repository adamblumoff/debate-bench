import type { NextConfig } from "next";

const enableCacheComponents = process.env.ENABLE_CACHE_COMPONENTS === "true";

const nextConfig: NextConfig = {
  /* config options here */
  reactCompiler: true,
  // Opt-in when explicitly enabled to avoid changing cache semantics by default.
  ...(enableCacheComponents ? { cacheComponents: true } : {}),
};

export default nextConfig;
