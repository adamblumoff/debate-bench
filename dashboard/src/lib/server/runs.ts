import path from "path";
import { ListObjectsV2Command, S3Client } from "@aws-sdk/client-s3";
import { serverEnv } from "@/lib/env";

export type RunConfig = {
  id: string;
  label: string;
  bucket: string;
  region: string;
  key: string;
  updated?: string;
};

type ManifestPayload = {
  runs: RunConfig[];
  defaultRunId: string;
};

const MANIFEST_TTL_MS = 5 * 60 * 1000;
const MAX_KEYS = 500;

let cache: { ts: number; payload: ManifestPayload } | null = null;

function deriveId(key: string, existing: Set<string>): string {
  const base = path.basename(key, ".jsonl");
  let id = base;
  let counter = 1;
  while (existing.has(id)) {
    counter += 1;
    id = `${base}-${counter}`;
  }
  return id;
}

function deriveLabel(key: string): string {
  const parts = key.split("/").filter(Boolean);
  const file = path.basename(key, ".jsonl");
  if (parts.length >= 2) {
    const parent = parts[parts.length - 2];
    return `${parent} • ${file}`;
  }
  return file;
}

async function listRunsFromS3(): Promise<RunConfig[]> {
  const client = new S3Client({ region: serverEnv.region });
  const runs: RunConfig[] = [];
  const seen = new Set<string>();

  let token: string | undefined;
  let fetched = 0;

  do {
    const cmd = new ListObjectsV2Command({
      Bucket: serverEnv.bucket,
      ContinuationToken: token,
      MaxKeys: MAX_KEYS,
    });
    const res = await client.send(cmd);
    token = res.IsTruncated ? res.NextContinuationToken : undefined;
    for (const obj of res.Contents || []) {
      const key = obj.Key;
      if (!key) continue;
      if (!/debates.*\.jsonl$/i.test(key)) continue;
      const id = deriveId(key, seen);
      seen.add(id);
      const updated = obj.LastModified ? obj.LastModified.toISOString().slice(0, 10) : undefined;
      runs.push({
        id,
        label: deriveLabel(key),
        bucket: serverEnv.bucket,
        region: serverEnv.region,
        key,
        updated,
      });
    }
    fetched += res.KeyCount || 0;
    // Bucket is small; still guard against runaway paging.
    if (fetched >= 5_000) break;
  } while (token);

  // Sort newest-first for UI display
  runs.sort((a, b) => {
    const ta = a.updated ? Date.parse(a.updated) : 0;
    const tb = b.updated ? Date.parse(b.updated) : 0;
    if (tb !== ta) return tb - ta;
    return a.key.localeCompare(b.key);
  });

  return runs;
}

function pickDefaultRunId(runs: RunConfig[]): string {
  if (!runs.length) return "default";
  const sorted = [...runs].sort((a, b) => {
    const ta = a.updated ? Date.parse(a.updated) : 0;
    const tb = b.updated ? Date.parse(b.updated) : 0;
    return tb - ta;
  });
  return sorted[0].id;
}

function fallbackManifest(): ManifestPayload {
  const run: RunConfig = {
    id: "default",
    label: "Default run",
    bucket: serverEnv.bucket,
    region: serverEnv.region,
    key: serverEnv.key,
  };
  return { runs: [run], defaultRunId: run.id };
}

export async function getRuns(refresh = false): Promise<ManifestPayload> {
  if (!refresh && cache && Date.now() - cache.ts < MANIFEST_TTL_MS) {
    return cache.payload;
  }
  try {
    const runs = await listRunsFromS3();
    if (!runs.length) {
      const payload = fallbackManifest();
      cache = { ts: Date.now(), payload };
      return payload;
    }
    const payload = { runs, defaultRunId: pickDefaultRunId(runs) };
    cache = { ts: Date.now(), payload };
    return payload;
  } catch {
    const payload = fallbackManifest();
    cache = { ts: Date.now(), payload };
    return payload;
  }
}

export async function resolveRun(runId?: string, refresh = false): Promise<RunConfig> {
  const manifest = await getRuns(refresh);
  if (!runId) return manifest.runs.find((r) => r.id === manifest.defaultRunId) || manifest.runs[0];
  const match = manifest.runs.find((r) => r.id === runId);
  if (!match) {
    throw new Error("unknown_run");
  }
  return match;
}
