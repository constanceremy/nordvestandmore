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
      {
        source: "/guide",
        destination: "/map",
        permanent: true,
      },
      {
        source: "/guide/:slug",
        destination: "/map/:slug",
        permanent: true,
      },
    ];
  },
};

export default nextConfig;
