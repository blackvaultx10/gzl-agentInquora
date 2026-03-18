import path from "path";

import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  outputFileTracingRoot: path.resolve(__dirname, "../.."),
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:8002/api/v1/:path*",
      },
    ];
  },
};

export default nextConfig;
