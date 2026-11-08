import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  outputFileTracingRoot: process.cwd(),
  skipTrailingSlashRedirect: true,
  distDir: process.env.NODE_ENV === 'development' ? '.next-dev' : '.next',
  // Keep the API private on loopback; browsers use the same LAN origin.
  async rewrites() {
    const api = process.env.APPDNA_API_URL || "http://127.0.0.1:8787";
    return { beforeFiles: [
      { source: "/video/:path*", destination: `${api}/video/:path*` },
      { source: "/api/:path*", destination: `${api}/api/:path*` },
    ] };
  },
};

export default nextConfig;
