"use client";

export function LoadState({
  status,
  error,
}: {
  status: string;
  error?: string;
}) {
  if (status === "loading")
    return <p className="text-sm text-[var(--text-muted)]">Loading metrics…</p>;
  if (status === "error")
    return <p className="text-sm text-[var(--accent)]">Error: {error}</p>;
  return null;
}
