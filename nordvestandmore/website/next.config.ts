import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  eslint: { ignoreDuringBuilds: true },
  async redirects() {
    return [
      {
        source: "/with-us",
        destination: "/our-events",
        permanent: true,
      },
      {
        source: "/with-us/:id",
        destination: "/our-events/:id",
        permanent: true,
      },
    ];
  },
};

export default nextConfig;
