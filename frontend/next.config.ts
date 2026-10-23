import type { NextConfig } from "next";

// The browser only talks to this Next.js server; /api/* is proxied to FastAPI,
// so credentials stay server-side and no CORS is needed.
const backend = process.env.SCOUTIQ_BACKEND_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  poweredByHeader: false,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Frame-Options", value: "DENY" },
        ],
      },
    ];
  },
};

export default nextConfig;
