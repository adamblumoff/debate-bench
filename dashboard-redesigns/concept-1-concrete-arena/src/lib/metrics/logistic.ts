export type SparseExample = {
  y: number; // 1 for pro win, 0 for con win
  idx: number[]; // feature indices
  val: number[]; // corresponding values (same length as idx)
  judge_id: string;
  topic_id: string;
};

export function sigmoid(x: number): number {
  return 1 / (1 + Math.exp(-x));
}

/**
 * Simple L2-regularized logistic regression (sparse one-hot features).
 * Returns weight vector sized to `numFeatures`.
 */
export function fitLogisticRidge(
  examples: SparseExample[],
  numFeatures: number,
  {
    lambda = 1.0,
    lr = 0.1,
    iters = 120,
    penalties,
  }: {
    lambda?: number;
    lr?: number;
    iters?: number;
    penalties?: Float64Array;
  } = {},
): Float64Array {
  const w = new Float64Array(numFeatures);
  const n = examples.length || 1;
  const pen = penalties ?? new Float64Array(numFeatures).fill(lambda);

  for (let iter = 0; iter < iters; iter++) {
    const grad = new Float64Array(numFeatures);
    for (const ex of examples) {
      let z = 0;
      for (let k = 0; k < ex.idx.length; k++) {
        z += w[ex.idx[k]] * ex.val[k];
      }
      const p = sigmoid(z);
      const err = p - ex.y; // derivative of log-loss
      for (let k = 0; k < ex.idx.length; k++) {
        grad[ex.idx[k]] += err * ex.val[k];
      }
    }
    // L2 penalty
    for (let i = 0; i < numFeatures; i++) grad[i] += pen[i] * w[i];

    const step = lr / n;
    for (let i = 0; i < numFeatures; i++) w[i] -= step * grad[i];
  }

  return w;
}

export function hashFold(id: string, folds: number): number {
  let h = 0;
  for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) | 0;
  return Math.abs(h) % folds;
}
