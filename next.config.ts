import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Enable standalone output for smaller Docker images and faster deployments
  output: 'standalone',

  // Compress output
  compress: true,

  // Optimize images
  images: {
    formats: ['image/avif', 'image/webp'],
    minimumCacheTTL: 60,
  },

  // Experimental optimizations
  experimental: {
    optimizePackageImports: [
      'lucide-react',
      'recharts',
      'framer-motion',
      '@radix-ui/react-dialog',
      '@radix-ui/react-select',
      'react-icons',
    ],
  },

  // Clark (agents): use API route proxy instead of rewrites. Rewrites can cause ECONNRESET
  // on long-running queries. The route at app/api/v1/agents/[[...path]]/route.ts
  // has a 5-min timeout and proper error handling.

  // Proxy to external backends to bypass CORS in local development
  async rewrites() {
    const apiUrl = (process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000').trim();
    const web3Url = (process.env.NEXT_PUBLIC_KRYPTON_WEB3_API_URL || 'http://127.0.0.1:8001').trim();
    const hedgeUrl = (process.env.NEXT_PUBLIC_HEDGE_FUND_API_URL || 'http://127.0.0.1:8000').trim();
    return [
      { source: '/proxy/main/:path*', destination: `${apiUrl}/:path*` },
      { source: '/proxy/web3/:path*', destination: `${web3Url}/:path*` },
      { source: '/proxy/hedge/:path*', destination: `${hedgeUrl}/:path*` },
    ];
  },

  webpack: (config, { isServer }) => {
    config.resolve.alias = {
      ...config.resolve.alias,
      '@react-native-async-storage/async-storage': false,
    };

    // Optimize bundle size - only exclude Node.js modules on client side
    if (!isServer) {
      config.resolve.fallback = {
        ...config.resolve.fallback,
        fs: false,
        net: false,
        tls: false,
        crypto: false,
        stream: false,
        url: false,
        zlib: false,
        http: false,
        https: false,
        assert: false,
        os: false,
        path: false,
      };
    }

    return config;
  },
};

export default nextConfig;