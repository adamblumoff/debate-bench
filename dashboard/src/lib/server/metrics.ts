import { serverEnv } from "@/lib/env";
import { S3Client, GetObjectCommand } from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";
import { parseJsonlStream } from "@/lib/jsonl";
import { DebateRecord, DerivedData } from "@/lib/types";
import { buildDerived } from "@/lib/metrics";
import { resolveRun, RunConfig } from "@/lib/server/runs";
import { computeCostSummary } from "@/lib/server/costSummary";

type MetricsPayload = {
  derived: DerivedData;
  derivedByCategory: Record<string, DerivedData>;
  meta: { debateCount: number; modelCount: number; categories: string[] };
  costSummary: ReturnType<typeof computeCostSummary>;
};

type MetricsOptions = {
  includeRows?: boolean;
  includeCategories?: boolean;
};

const cache = new Map<string, { ts: number; payload: MetricsPayload }>();
const defaultTtl = 5 * 60 * 1000;

function stripRows(derived: DerivedData): DerivedData {
  return {
    ...derived,
    debateRows: [],
    judgeRows: [],
  };
}

async function computeMetrics(
  run: RunConfig,
  opts: MetricsOptions = {},
): Promise<MetricsPayload> {
  const includeCategories = opts.includeCategories !== false;

  const s3 = new S3Client({
    region: run.region,
    endpoint: serverEnv.endpoint,
    forcePathStyle: serverEnv.forcePathStyle,
  });
  const command = new GetObjectCommand({ Bucket: run.bucket, Key: run.key });
  const url = await getSignedUrl(s3, command, {
    expiresIn: serverEnv.urlExpirySeconds,
  });

  const debates = await parseJsonlStream<DebateRecord>(url, undefined, {
    timeoutMs: serverEnv.fetchTimeoutMs,
    maxBytes: 100 * 1024 * 1024,
    label: `metrics_${run.id}`,
  });

  const derived = buildDerived(debates);
  const costSummary = computeCostSummary(debates);

  const categorySet = new Set<string>();
  for (const d of debates) {
    if (d.transcript.topic.category)
      categorySet.add(d.transcript.topic.category);
  }

  const derivedByCategory: Record<string, DerivedData> = {};
  if (includeCategories) {
    for (const category of categorySet) {
      const subset = debates.filter(
        (d) => d.transcript.topic.category === category,
      );
      derivedByCategory[category] = buildDerived(subset);
    }
  }

  return {
    derived,
    derivedByCategory,
    meta: {
      debateCount: debates.length,
      modelCount: derived.models.length,
      categories: Array.from(categorySet).sort(),
    },
    costSummary,
  };
}

async function getMetricsWithTtl(
  refresh: boolean,
  ttlMs: number,
  run: RunConfig,
) {
  const key = run.id;
  const entry = cache.get(key);
  if (!refresh && entry && Date.now() - entry.ts < ttlMs) {
    return entry.payload;
  }
  const payload = await computeMetrics(run, { includeCategories: true });
  cache.set(key, { ts: Date.now(), payload });
  return payload;
}

export async function getMetrics(
  refresh = false,
  runId?: string,
  ttlMs?: number,
  opts: MetricsOptions = {},
): Promise<MetricsPayload> {
  const ttl =
    typeof ttlMs === "number"
      ? ttlMs
      : Number(process.env.METRICS_CACHE_MS || defaultTtl);
  const run = await resolveRun(runId, refresh);
  const payload = await getMetricsWithTtl(refresh, ttl, run);
  if (opts.includeRows === false) {
    const strip = (d: DerivedData) => stripRows(d);
    const derivedByCategory: Record<string, DerivedData> = {};
    for (const [k, v] of Object.entries(payload.derivedByCategory || {})) {
      derivedByCategory[k] = strip(v);
    }
    return {
      derived: strip(payload.derived),
      derivedByCategory,
      meta: payload.meta,
      costSummary: payload.costSummary,
    };
  }
  return payload;
}
