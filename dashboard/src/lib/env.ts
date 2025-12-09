import { readEnv, readEnvNumber } from "@/lib/server/validate";

export const serverEnv = {
  bucket: readEnv("S3_BUCKET"),
  region: readEnv("S3_REGION"),
  key: readEnv("S3_KEY"),
  urlExpirySeconds: readEnvNumber("S3_URL_EXPIRY_SECONDS", 900, {
    min: 60,
    max: 86_400,
  }),
  fetchTimeoutMs: readEnvNumber("FETCH_TIMEOUT_MS", 10_000, {
    min: 1_000,
    max: 60_000,
  }),
};
