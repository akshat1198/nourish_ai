import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Frontend talks directly to the FastAPI backend (CORS-enabled), so no rewrites.
};

export default nextConfig;
