// Feature toggles for the dashboard UI.
// Keep the builder code in the repo but hide it by default.
export const ENABLE_BUILDER =
  typeof process.env.NEXT_PUBLIC_ENABLE_BUILDER === "string"
    ? process.env.NEXT_PUBLIC_ENABLE_BUILDER === "true"
    : false;

// Compare drawer + sidebar; also gates compare buttons in highlights.
export const ENABLE_COMPARE =
  typeof process.env.NEXT_PUBLIC_ENABLE_COMPARE === "string"
    ? process.env.NEXT_PUBLIC_ENABLE_COMPARE === "true"
    : false;
