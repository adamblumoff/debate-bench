export const toPercent = (v: number) => `${(v * 100).toFixed(1)}%`;
export const toTokens = (v: number) => `${Math.round(v).toLocaleString()} tok`;
