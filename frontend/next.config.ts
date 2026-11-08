import type { NextConfig } from "next";
import path from "node:path";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  devIndicators: false,
  distDir: process.env.NODE_ENV === "development" ? ".next-dev" : ".next",
  outputFileTracingRoot: path.resolve(process.cwd()),
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.APPDNA_API_URL || "http://127.0.0.1:8787"}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
