const required = (name: string): string => {
  const value = process.env[name];
  if (!value) throw new Error(`Missing required env var ${name}`);
  return value;
};

export const serverEnv = {
  bucket: required("S3_BUCKET"),
  region: required("S3_REGION"),
  key: required("S3_KEY"),
  urlExpirySeconds: Number(process.env.S3_URL_EXPIRY_SECONDS || 900),
};
