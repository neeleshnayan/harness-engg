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
  
  async rewrites() {
    return [
      {
        source: '/api/v1/:path*',
        // destination: `${process.env.NEXT_PUBLIC_API_URL || 'https://api.kryptonfund.com'}/api/v1/:path*`,
        destination: `${process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'}/api/v1/:path*`,
      },
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