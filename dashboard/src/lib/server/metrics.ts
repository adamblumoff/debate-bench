import { serverEnv } from "@/lib/env";
import { S3Client, GetObjectCommand } from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";
import { parseJsonlStream } from "@/lib/jsonl";
import { DebateRecord, DerivedData } from "@/lib/types";
import { buildDerived } from "@/lib/metrics";

const s3 = new S3Client({ region: serverEnv.region });

type MetricsPayload = {
  derived: DerivedData;
  derivedByCategory: Record<string, DerivedData>;
  meta: { debateCount: number; modelCount: number; categories: string[] };
};

let cache: { ts: number; payload: MetricsPayload } | null = null;
const defaultTtl = 5 * 60 * 1000;

async function computeMetrics(): Promise<MetricsPayload> {
  const command = new GetObjectCommand({ Bucket: serverEnv.bucket, Key: serverEnv.key });
  const url = await getSignedUrl(s3, command, { expiresIn: serverEnv.urlExpirySeconds });

  const debates = await parseJsonlStream<DebateRecord>(url);

  const derived = buildDerived(debates);

  const categorySet = new Set<string>();
  for (const d of debates) {
    if (d.transcript.topic.category) categorySet.add(d.transcript.topic.category);
  }

  const derivedByCategory: Record<string, DerivedData> = {};
  for (const category of categorySet) {
    const subset = debates.filter((d) => d.transcript.topic.category === category);
    derivedByCategory[category] = buildDerived(subset);
  }

  return {
    derived,
    derivedByCategory,
    meta: {
      debateCount: debates.length,
      modelCount: derived.models.length,
      categories: Array.from(categorySet).sort(),
    },
  };
}

async function getMetricsWithTtl(refresh: boolean, ttlMs: number) {
  if (!refresh && cache && Date.now() - cache.ts < ttlMs) {
    return cache.payload;
  }
  const payload = await computeMetrics();
  cache = { ts: Date.now(), payload };
  return payload;
}

export async function getMetrics(refresh = false, ttlMs?: number): Promise<MetricsPayload> {
  const ttl = typeof ttlMs === "number" ? ttlMs : Number(process.env.METRICS_CACHE_MS || defaultTtl);
  return getMetricsWithTtl(refresh, ttl);
}
