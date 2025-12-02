export type PricingRow = {
  model_id: string;
  provider: string;
  input_per_million: number;
  output_per_million: number;
};

export type PricingSnapshot = {
  updated: string;
  currency: string;
  rows: PricingRow[];
};

export const pricingSnapshot: PricingSnapshot = {
  updated: "2025-11-30",
  currency: "USD",
  rows: [
    { model_id: "gpt-4.1", provider: "openrouter", input_per_million: 30, output_per_million: 60 },
    { model_id: "claude-3.5-sonnet", provider: "openrouter", input_per_million: 15, output_per_million: 15 },
    { model_id: "gemini-1.5-pro", provider: "openrouter", input_per_million: 18, output_per_million: 36 },
    { model_id: "gpt-4o-mini", provider: "openrouter", input_per_million: 3, output_per_million: 6 },
    { model_id: "qwen2.5-72b", provider: "openrouter", input_per_million: 1.8, output_per_million: 2.2 },
    { model_id: "llama-3.1-70b", provider: "openrouter", input_per_million: 1.2, output_per_million: 1.6 },
  ],
};

export const fetchPricing = async (url: string): Promise<PricingSnapshot> => {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`pricing fetch failed: ${res.status}`);
  const json = await res.json();
  return json as PricingSnapshot;
};
