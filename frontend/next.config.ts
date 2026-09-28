import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Standalone output is only used for the Docker image (set in frontend/Dockerfile);
  // the Windows launcher runs a normal `next start`.
  output: process.env.NEXT_STANDALONE === "1" ? "standalone" : undefined,
  reactStrictMode: true,
};

export default nextConfig;
