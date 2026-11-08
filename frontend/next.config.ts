import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Keep the API private on loopback; browsers use the same LAN origin.
  async rewrites() {
    return [{ source: "/api/:path*", destination: "http://127.0.0.1:8787/api/:path*" }];
  },
};

export default nextConfig;
