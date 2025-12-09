"use client";

export function LoadState({
  status,
  error,
}: {
  status: string;
  error?: string;
}) {
  if (status === "loading")
    return <p className="text-sm text-slate-300">Loading metrics…</p>;
  if (status === "error")
    return <p className="text-sm text-red-400">Error: {error}</p>;
  return null;
}
