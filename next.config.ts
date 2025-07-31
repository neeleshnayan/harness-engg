import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/v1/:path*',
        destination: `${process.env.NEXT_PUBLIC_API_URL || 'https://api.kryptonfund.com'}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
