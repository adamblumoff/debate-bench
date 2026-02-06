import { readEnv, readEnvNumber } from "@/lib/server/validate";

function readOptionalBool(...names: string[]): boolean | undefined {
  for (const name of names) {
    const raw = process.env[name];
    if (raw == null || raw === "") continue;
    return ["1", "true", "yes", "on"].includes(raw.trim().toLowerCase());
  }
  return undefined;
}

export const serverEnv = {
  bucket: readEnv("AWS_S3_BUCKET_NAME", process.env.S3_BUCKET),
  region: readEnv("S3_REGION"),
  key: readEnv("S3_KEY"),
  endpoint:
    process.env.S3_ENDPOINT ||
    process.env.AWS_S3_ENDPOINT ||
    process.env.DEBATEBENCH_S3_ENDPOINT ||
    undefined,
  forcePathStyle: readOptionalBool(
    "S3_FORCE_PATH_STYLE",
    "AWS_S3_FORCE_PATH_STYLE",
    "DEBATEBENCH_S3_FORCE_PATH_STYLE",
  ),
  urlExpirySeconds: readEnvNumber("S3_URL_EXPIRY_SECONDS", 900, {
    min: 60,
    max: 86_400,
  }),
  fetchTimeoutMs: readEnvNumber("FETCH_TIMEOUT_MS", 10_000, {
    min: 1_000,
    max: 60_000,
  }),
};
